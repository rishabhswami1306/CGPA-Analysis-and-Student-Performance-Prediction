import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError
from werkzeug.utils import secure_filename

from utils.db import get_db
from utils.decorators import role_required, faculty_subject_authorized
from utils.validators import MarksUpdateSchema
from utils.audit_logger import log_audit_event
from utils.grade_calculator import (
    compute_semester_sgpa, compute_subject_total, calculate_grade_point, compute_subject_internal
)
from utils.bulk_uploader import (
    parse_upload_file, validate_and_prepare_batch, commit_faculty_bulk_upload, generate_bulk_template
)
from ml_engine.inference import predict_student_analytics

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")


@faculty_bp.route("/dashboard", methods=["GET"])
@role_required(["faculty", "admin"])
def dashboard_view():
    """Faculty portal showing only assigned subjects and student enrollment."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    assigned_subjects = user.get("assigned_subjects", []) if user else []

    # If Admin, show all ongoing Sem 5 subjects
    if user.get("role") == "admin":
        assigned_subjects = db.academic_records.distinct("subjects.subject_code", {"semester": 5}) or ["ML-II", "IS", "DAA", "CCN", "CCS", "CI", "AJL", "EM"]

    # Fetch summary for assigned subjects (focused on ongoing Semester 5)
    subject_summaries = []
    for code in assigned_subjects:
        records = list(db.academic_records.find({"semester": 5, "subjects.subject_code": code}))
        sub_name = code
        tt1_scores = []
        for r in records:
            for s in r.get("subjects", []):
                if s.get("subject_code") == code:
                    sub_name = s.get("subject_name", code)
                    if s.get("tt1_score") is not None:
                        tt1_scores.append(float(s.get("tt1_score", 0.0)))
        
        avg_score = round(sum(tt1_scores) / len(tt1_scores), 1) if tt1_scores else 0.0
        pass_count = sum(1 for sc in tt1_scores if sc >= 8.0)  # Pass mark for internal 20
        pass_pct = round((pass_count / len(tt1_scores)) * 100.0, 1) if tt1_scores else 100.0

        subject_summaries.append({
            "subject_code": code,
            "subject_name": sub_name,
            "enrolled_students": len(records),
            "average_marks": avg_score,
            "pass_percentage": pass_pct
        })

    # 2x2 Risk Quadrant Computation (Point 8)
    cohort_records = list(db.academic_records.find({"semester": 5}))
    attendance_map = {a["student_prn"]: a.get("percentage", 80.0) for a in db.attendance_records.find({})}
    users_map = {u["prn_roll"]: u for u in db.users.find({"role": "student"})}

    quadrant_stars = []            # High marks (>= 15), High att (>= 75)
    quadrant_engagement = []       # High marks (>= 15), Low att (< 75)
    quadrant_tutoring = []         # Low marks (< 15), High att (>= 75)
    quadrant_critical = []         # Low marks (< 15), Low att (< 75)

    seen_students = set()
    for rec in cohort_records:
        prn = rec.get("student_prn")
        if not prn or prn in seen_students:
            continue
        
        stu_subs = rec.get("subjects", [])
        relevant_subs = [s for s in stu_subs if s.get("subject_code") in assigned_subjects] if user.get("role") != "admin" else stu_subs
        if not relevant_subs:
            continue

        seen_students.add(prn)
        stu_user = users_map.get(prn, {})
        stu_name = stu_user.get("name", prn)
        att = float(attendance_map.get(prn, rec.get("attendance_percentage", 80.0)))
        
        tt_scores = [float(s.get("tt1_score", 15.0)) for s in relevant_subs if s.get("tt1_score") is not None]
        avg_tt = round(float(sum(tt_scores) / len(tt_scores)), 1) if tt_scores else 15.0

        student_entry = {
            "prn": prn,
            "name": stu_name,
            "attendance": att,
            "avg_tt": avg_tt,
            "subjects": [s.get("subject_code") for s in relevant_subs]
        }

        if att >= 75.0 and avg_tt >= 15.0:
            quadrant_stars.append(student_entry)
        elif att < 75.0 and avg_tt >= 15.0:
            quadrant_engagement.append(student_entry)
        elif att >= 75.0 and avg_tt < 15.0:
            quadrant_tutoring.append(student_entry)
        else:
            quadrant_critical.append(student_entry)

    risk_quadrants = {
        "stars": quadrant_stars,
        "engagement_risk": quadrant_engagement,
        "tutoring_needed": quadrant_tutoring,
        "critical_risk": quadrant_critical,
        "counts": {
            "stars": len(quadrant_stars),
            "engagement": len(quadrant_engagement),
            "tutoring": len(quadrant_tutoring),
            "critical": len(quadrant_critical),
            "total": len(seen_students)
        }
    }

    recent_interventions = list(db.interventions.find({"faculty_prn": current_prn}).sort("timestamp", -1).limit(6)) if "interventions" in db.list_collection_names() or hasattr(db, "interventions") else []

    return render_template(
        "faculty/faculty_dashboard.html",
        user=user,
        assigned_subjects=assigned_subjects,
        subject_summaries=subject_summaries,
        risk_quadrants=risk_quadrants,
        recent_interventions=recent_interventions
    )


@faculty_bp.route("/intervene", methods=["POST"])
@role_required(["faculty", "admin"])
def record_intervention():
    """Records and dispatches a pedagogical intervention for an at-risk student."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    
    data = request.get_json(silent=True) or request.form.to_dict()
    student_prn = data.get("student_prn")
    intervention_type = data.get("intervention_type", "remedial_packet")
    subject_code = data.get("subject_code", "GENERAL")
    notes = data.get("notes", "Faculty intervention logged via early-warning matrix.")

    if not student_prn:
        if request.is_json:
            return jsonify({"status": "error", "message": "student_prn is required"}), 400
        flash("Student PRN is required.", "danger")
        return redirect(url_for("faculty.dashboard_view"))

    intervention_doc = {
        "student_prn": student_prn,
        "faculty_prn": current_prn,
        "faculty_name": user.get("name", "Faculty Instructor"),
        "intervention_type": intervention_type,
        "subject_code": subject_code,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "DISPATCHED"
    }

    db.interventions.insert_one(intervention_doc)
    intervention_doc.pop("_id", None)

    log_audit_event(
        actor_prn=current_prn,
        actor_role=user.get("role", "faculty") if user else "faculty",
        action="DISPATCH_INTERVENTION",
        target_student_prn=student_prn,
        details={"type": intervention_type, "subject": subject_code}
    )

    if request.is_json:
        return jsonify({"status": "success", "message": f"Intervention successfully dispatched to {student_prn}", "data": intervention_doc}), 201
    
    flash(f"Intervention ({intervention_type}) successfully dispatched to {student_prn}.", "success")
    return redirect(url_for("faculty.dashboard_view"))


@faculty_bp.route("/grade-entry", methods=["GET", "POST"])
@role_required(["faculty", "admin"])
def grade_entry_view():
    """Grade entry interface for assigned subjects in ongoing Semester 5."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    assigned_subjects = user.get("assigned_subjects", []) if user else []

    if user.get("role") == "admin":
        assigned_subjects = db.academic_records.distinct("subjects.subject_code", {"semester": 5}) or ["ML-II", "IS", "DAA", "CCN", "CCS", "CI", "AJL", "EM"]

    selected_subject = request.args.get("subject_code") or (assigned_subjects[0] if assigned_subjects else "ML-II")
    # DEFAULT TO ONGOING SEMESTER 5
    selected_sem = int(request.args.get("semester", 5))

    # Fetch students enrolled in this subject and semester
    students_data = []
    if selected_subject:
        # Enforce server-side authorization
        if user.get("role") != "admin" and selected_subject not in assigned_subjects:
            flash(f"Unauthorized: You are not assigned to grade subject {selected_subject}.", "danger")
            return redirect(url_for("faculty.dashboard_view"))

        records = list(db.academic_records.find({
            "semester": selected_sem,
            "subjects.subject_code": selected_subject
        }))

        for rec in records:
            prn = rec.get("student_prn")
            student_user = db.users.find_one({"prn_roll": prn}) or {}
            target_sub = next((s for s in rec.get("subjects", []) if s.get("subject_code") == selected_subject), {})
            
            tt1 = float(target_sub.get("tt1_score", 0.0))
            tt2 = float(target_sub.get("tt2_score", 0.0))
            tt_conv = target_sub.get("tt_converted", round((tt1 + tt2) / 4.0, 2))
            apt = float(target_sub.get("aptitude_score", 0.0))
            skat = float(target_sub.get("skat_score", 0.0))
            ta = float(target_sub.get("teacher_assessment_score", 0.0))
            mock = float(target_sub.get("mock_interview_score", 0.0))
            pres = float(target_sub.get("presentation_score", 0.0))
            internal = target_sub.get("internal_score", round(tt_conv + apt + skat + ta + mock + pres, 2))

            students_data.append({
                "student_prn": prn,
                "student_name": student_user.get("name", prn),
                "branch": student_user.get("branch", ""),
                "semester": selected_sem,
                "subject_code": selected_subject,
                "tt1_score": tt1,
                "tt2_score": tt2,
                "tt_converted": tt_conv,
                "aptitude_score": apt,
                "skat_score": skat,
                "teacher_assessment_score": ta,
                "mock_interview_score": mock,
                "presentation_score": pres,
                "internal_score": internal,
                "ese_score": float(target_sub.get("ese_score", 0.0)),
                "total_marks": float(target_sub.get("total_marks", internal if selected_sem == 5 else 0.0)),
                "grade_point": target_sub.get("grade_point", 0.0),
                "grade_letter": target_sub.get("grade_letter", "Pending" if selected_sem == 5 else "P"),
                "attendance_percentage": rec.get("attendance_percentage", 80.0)
            })

    return render_template(
        "faculty/grade_entry.html",
        assigned_subjects=assigned_subjects,
        selected_subject=selected_subject,
        selected_sem=selected_sem,
        students_data=students_data
    )


@faculty_bp.route("/submit-grade", methods=["POST"])
@role_required(["faculty", "admin"])
@faculty_subject_authorized
def submit_grade():
    """
    Submits or updates marks for a student in an assigned subject.
    Supports 60 ESE + 40 Internal (15 TT, 5 Apt, 5 SKAT, 5 TA, 5 Mock, 5 Pres).
    Emits real-time SocketIO event and updates prediction cache.
    """
    payload = request.get_json() if request.is_json else request.form.to_dict()
    schema = MarksUpdateSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    prn = data["student_prn"]
    sem = data["semester"]
    subject_code = data["subject_code"]
    current_prn = get_jwt_identity()

    db = get_db()
    record = db.academic_records.find_one({"student_prn": prn, "semester": sem})
    if not record:
        return jsonify({"error": f"No semester {sem} record found for student {prn}"}), 404

    subjects = record.get("subjects", [])
    target_idx = next((i for i, s in enumerate(subjects) if s.get("subject_code") == subject_code), None)
    
    if target_idx is None:
        return jsonify({"error": f"Subject {subject_code} not found in student {prn} semester {sem} record"}), 404

    before_state = dict(subjects[target_idx])

    # Update scores from payload
    for field in [
        "tt1_score", "tt2_score", "aptitude_score", "skat_score",
        "teacher_assessment_score", "mock_interview_score", "presentation_score", "ese_score"
    ]:
        if field in data:
            subjects[target_idx][field] = float(data[field])

    # Deterministically calculate internal & subject total
    tt1 = float(subjects[target_idx].get("tt1_score", 0.0))
    tt2 = float(subjects[target_idx].get("tt2_score", 0.0))
    apt = float(subjects[target_idx].get("aptitude_score", 0.0))
    sk = float(subjects[target_idx].get("skat_score", 0.0))
    ta = float(subjects[target_idx].get("teacher_assessment_score", 0.0))
    mock = float(subjects[target_idx].get("mock_interview_score", 0.0))
    pres = float(subjects[target_idx].get("presentation_score", 0.0))
    ese = float(subjects[target_idx].get("ese_score", 0.0))

    tt_conv = round((tt1 + tt2) / 4.0, 2)
    has_subcomponents = any(v > 0 for v in [apt, sk, ta, mock, pres]) or tt1 > 20.0 or tt2 > 20.0
    if not has_subcomponents and (ese > 60.0 or float(subjects[target_idx].get("max_ese", 60.0)) == 80.0):
        # Legacy fallback
        total = compute_subject_total(tt1=tt1, tt2=tt2, ese=ese, max_ese=80.0)
        internal = (tt1 + tt2) / 2.0
    else:
        internal = compute_subject_internal(tt1, tt2, apt, sk, ta, mock, pres)
        total = compute_subject_total(
            tt1=tt1, tt2=tt2, ese=ese, max_ese=60.0,
            aptitude=apt, skat=sk, teacher_assessment=ta,
            mock_interview=mock, presentation=pres,
            internal_score=internal
        )
    gp, letter = calculate_grade_point(total)

    subjects[target_idx]["tt_converted"] = tt_conv
    subjects[target_idx]["internal_score"] = internal
    subjects[target_idx]["total_marks"] = total
    subjects[target_idx]["grade_point"] = gp
    subjects[target_idx]["grade_letter"] = letter

    # Update attendance if passed
    if "attendance_percentage" in data:
        record["attendance_percentage"] = float(data["attendance_percentage"])

    # Deterministically recalculate Semester SGPA if completed, or maintain ongoing state
    is_ongoing = (sem == 5 and record.get("is_completed") is False)
    if is_ongoing and float(subjects[target_idx].get("ese_score", 0.0)) == 0.0:
        new_sgpa = None
        new_backlogs = 0
    else:
        new_sgpa, new_backlogs, total_credits = compute_semester_sgpa(subjects)

    record["sgpa"] = new_sgpa
    record["active_backlogs"] = new_backlogs
    record["subjects"] = subjects
    record["updated_at"] = datetime.now(timezone.utc)

    # Save to MongoDB
    db.academic_records.update_one(
        {"_id": record["_id"]},
        {"$set": {
            "subjects": subjects,
            "sgpa": new_sgpa,
            "active_backlogs": new_backlogs,
            "attendance_percentage": record["attendance_percentage"],
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    # Recalculate predictions in real-time (ML model updates predicted Sem 5 SGPA using new TT marks)
    new_predictions = predict_student_analytics(prn, force_recalculate=True)
    pred_sgpa_display = new_predictions.get("predicted_next_sgpa", "N/A")

    # Audit log
    log_audit_event(
        actor_prn=current_prn,
        actor_role="faculty",
        action="EDIT_MARKS",
        target_student_prn=prn,
        before=before_state,
        details=f"Subject {subject_code} marks updated: Internal={internal}/40 (TT Conv={tt_conv}, Apt={apt}, SKAT={sk}, TA={ta}, Mock={mock}, Pres={pres}), ESE={ese}/60, Total={total}/100. Sem 5 SGPA: {pred_sgpa_display}"
    )

    # Emit real-time SocketIO event to the student's personal channel
    try:
        from app import socketio
        socketio.emit(
            "academic_update",
            {
                "student_prn": prn,
                "semester": sem,
                "subject_code": subject_code,
                "new_sgpa": new_sgpa,
                "predictions": new_predictions,
                "updated_at": datetime.now(timezone.utc).isoformat()
            },
            room=f"student_{prn}"
        )
    except Exception as e:
        # SocketIO emit failure shouldn't fail REST call
        pass

    return jsonify({
        "message": f"Marks updated successfully for {prn} ({subject_code}).",
        "updated_subject": subjects[target_idx],
        "tt_converted": tt_conv,
        "internal_score": internal,
        "total_marks": total,
        "new_sgpa": new_sgpa,
        "new_backlogs": new_backlogs,
        "predicted_sem5_sgpa": new_predictions.get("predicted_next_sgpa") if new_predictions else None,
        "predictions": new_predictions
    }), 200


@faculty_bp.route("/bulk-upload", methods=["GET", "POST"])
@role_required(["faculty", "admin"])
def bulk_upload_view():
    """
    Bulk marks and attendance uploader for faculty.
    Accepts CSV or Excel (.xlsx, .xls) files to update Unit Test marks (TT1, TT2, internal components)
    and Attendance registers / bunks.
    Cleanly removes and overwrites previous records for the uploaded subject/students,
    recalculates totals, SGPA, bunk safety margins, and ML forecast,
    and updates student portals in real-time.
    """
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    is_admin = (user.get("role") == "admin") if user else False
    assigned_subjects = user.get("assigned_subjects", []) if user else []

    all_sem5_subjects = db.academic_records.distinct("subjects.subject_code", {"semester": 5}) or [
        "ML-II", "IS", "DAA", "CCN", "CCS", "CI", "AJL", "EM"
    ]
    if is_admin or not assigned_subjects:
        authorized_subjects = all_sem5_subjects
    else:
        authorized_subjects = assigned_subjects

    if request.method == "GET":
        return render_template(
            "faculty/bulk_upload.html",
            user=user,
            assigned_subjects=authorized_subjects,
            all_subjects=all_sem5_subjects,
            selected_subject=authorized_subjects[0] if authorized_subjects else "ML-II",
            selected_sem=5,
            preview=None
        )

    # POST handling:
    # Check if this is a commit of previously staged rows (from hidden JSON input)
    staged_payload = request.form.get("staged_rows_json")
    commit_action = request.form.get("commit", "false").lower() == "true"
    overwrite_mode = request.form.get("overwrite_mode", "true").lower() == "true"

    if staged_payload and commit_action:
        try:
            staged_rows = json.loads(staged_payload)
            result = commit_faculty_bulk_upload(
                staged_rows=staged_rows,
                actor_prn=current_prn,
                actor_role="admin" if is_admin else "faculty",
                overwrite_mode=overwrite_mode
            )
            flash(
                f"Successfully committed and overwritten previous records for {result['records_overwritten']} subject entries across {result['students_updated']} students! Student portals and AI models have been updated live.",
                "success"
            )
            return render_template(
                "faculty/bulk_upload.html",
                user=user,
                assigned_subjects=authorized_subjects,
                all_subjects=all_sem5_subjects,
                selected_subject=authorized_subjects[0] if authorized_subjects else "ML-II",
                selected_sem=5,
                preview=None,
                commit_summary=result
            )
        except Exception as e:
            flash(f"Failed to commit batch: {str(e)}", "danger")
            return redirect(url_for("faculty.bulk_upload_view"))

    # File upload handling
    if "file" not in request.files:
        flash("No file part provided in upload request.", "danger")
        return redirect(url_for("faculty.bulk_upload_view"))

    file = request.files["file"]
    if not file or file.filename == "":
        flash("Please select a valid CSV or Excel file to upload.", "danger")
        return redirect(url_for("faculty.bulk_upload_view"))

    filename = secure_filename(file.filename)
    ext = filename.lower().split(".")[-1]
    if ext not in ["csv", "xlsx", "xls"]:
        flash("Unsupported file format. Please upload a .csv, .xlsx, or .xls spreadsheet.", "danger")
        return redirect(url_for("faculty.bulk_upload_view"))

    upload_type = request.form.get("upload_type", "combined")
    default_sem = int(request.form.get("semester", 5))
    default_sub = request.form.get("default_subject", authorized_subjects[0] if authorized_subjects else "ML-II")
    direct_commit = request.form.get("direct_commit", "false").lower() == "true"

    try:
        df = parse_upload_file(file, filename)
    except Exception as e:
        flash(f"Spreadsheet parsing error: {str(e)}", "danger")
        return redirect(url_for("faculty.bulk_upload_view"))

    batch_result = validate_and_prepare_batch(
        df=df,
        upload_type=upload_type,
        default_semester=default_sem,
        default_subject=default_sub,
        authorized_subjects=authorized_subjects if not is_admin else None,
        is_admin=is_admin
    )

    if not batch_result["is_valid"] and batch_result.get("fatal_error"):
        flash(f"Validation Failure: {batch_result['fatal_error']}", "danger")
        return render_template(
            "faculty/bulk_upload.html",
            user=user,
            assigned_subjects=authorized_subjects,
            all_subjects=all_sem5_subjects,
            selected_subject=default_sub,
            selected_sem=default_sem,
            preview=batch_result
        )

    # If direct commit is requested and there are no validation errors
    if direct_commit and batch_result["is_valid"]:
        result = commit_faculty_bulk_upload(
            staged_rows=batch_result["staged_rows"],
            actor_prn=current_prn,
            actor_role="admin" if is_admin else "faculty",
            overwrite_mode=overwrite_mode
        )
        flash(
            f"Successfully updated and overwritten previous records for {result['records_overwritten']} subject entries across {result['students_updated']} students! Student portals and AI models have been updated live.",
            "success"
        )
        return render_template(
            "faculty/bulk_upload.html",
            user=user,
            assigned_subjects=authorized_subjects,
            all_subjects=all_sem5_subjects,
            selected_subject=default_sub,
            selected_sem=default_sem,
            preview=None,
            commit_summary=result
        )

    # Render dry-run preview table with diffs and confirmation button
    return render_template(
        "faculty/bulk_upload.html",
        user=user,
        assigned_subjects=authorized_subjects,
        all_subjects=all_sem5_subjects,
        selected_subject=default_sub,
        selected_sem=default_sem,
        preview=batch_result,
        staged_rows_json=json.dumps(batch_result["staged_rows"]),
        upload_type=upload_type,
        overwrite_mode=overwrite_mode
    )


@faculty_bp.route("/bulk-upload/template", methods=["GET"])
@role_required(["faculty", "admin"])
def download_bulk_template():
    """Generates and downloads pre-filled CSV or Excel templates for faculty upload."""
    upload_type = request.args.get("type", "tt_marks")
    fmt = request.args.get("format", "csv")
    subject_code = request.args.get("subject_code", "ML-II")
    semester = int(request.args.get("semester", 5))

    buf, filename, mimetype = generate_bulk_template(
        upload_type=upload_type,
        output_format=fmt,
        subject_code=subject_code,
        semester=semester
    )

    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )

