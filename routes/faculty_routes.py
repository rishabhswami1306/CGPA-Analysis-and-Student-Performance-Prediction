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
from utils.pdf_result_parser import parse_batch_pdfs, commit_result_records, parse_result_pdf, get_student_year_context
from ml_engine.train_models import retrain_all_models
from ml_engine.inference import predict_student_analytics

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")


SUBJECT_METADATA = {
    "ML-II": {"name": "Machine Learning II", "credits": 4},
    "IS": {"name": "Information Security", "credits": 3},
    "DAA": {"name": "Design & Analysis of Algorithms", "credits": 4},
    "CCN": {"name": "Computer Communication & Networks", "credits": 4},
    "CCS": {"name": "Cloud Computing & Services", "credits": 4},
    "CI": {"name": "Competitive Intelligence", "credits": 1},
    "AJL": {"name": "Advanced Java Lab", "credits": 2},
    "EM": {"name": "Honors – Engineering Mathematics", "credits": 2},
    "CMPM": {"name": "Honors – Computational Photography & Media", "credits": 2},
}


@faculty_bp.route("/dashboard", methods=["GET"])
@role_required(["faculty", "admin"])
def dashboard_view():
    """Faculty continuous assessment and pedagogical triage hub."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    assigned_subjects = user.get("assigned_subjects", []) if user else []

    # If Admin, show all ongoing Sem 5 subjects
    if user and user.get("role") == "admin":
        assigned_subjects = db.academic_records.distinct("subjects.subject_code", {"semester": 5}) or [
            "ML-II", "IS", "DAA", "CCN", "CCS", "CI", "AJL", "EM"
        ]

    # Fetch summary for assigned subjects (focused on ongoing Semester 5)
    subject_summaries = []
    all_assigned_tt1_scores = []
    
    for code in assigned_subjects:
        records = list(db.academic_records.find({"semester": 5, "subjects.subject_code": code}))
        meta = SUBJECT_METADATA.get(code, {})
        sub_name = meta.get("name", code)
        tt1_scores = []
        tt2_scores = []
        for r in records:
            for s in r.get("subjects", []):
                if s.get("subject_code") == code:
                    if s.get("subject_name"):
                        sub_name = s.get("subject_name")
                    if s.get("tt1_score") is not None:
                        tt1_scores.append(float(s.get("tt1_score", 0.0)))
                    if s.get("tt2_score") is not None and float(s.get("tt2_score", 0.0)) > 0:
                        tt2_scores.append(float(s.get("tt2_score", 0.0)))
        
        all_assigned_tt1_scores.extend(tt1_scores)
        avg_score = round(sum(tt1_scores) / len(tt1_scores), 1) if tt1_scores else 0.0
        max_score = round(max(tt1_scores), 1) if tt1_scores else 0.0
        min_score = round(min(tt1_scores), 1) if tt1_scores else 0.0
        pass_count = sum(1 for sc in tt1_scores if sc >= 12.0)  # Pass mark for TT out of 30 (40%)
        pass_pct = round((pass_count / len(tt1_scores)) * 100.0, 1) if tt1_scores else 100.0

        distinction_count = sum(1 for sc in tt1_scores if sc >= 24.0)  # >= 80% of 30
        first_class_count = sum(1 for sc in tt1_scores if 18.0 <= sc < 24.0)  # 60% - 79% of 30
        pass_class_count = sum(1 for sc in tt1_scores if 12.0 <= sc < 18.0)  # 40% - 59% of 30
        fail_count = sum(1 for sc in tt1_scores if sc < 12.0)  # < 40% of 30

        subject_summaries.append({
            "subject_code": code,
            "subject_name": sub_name,
            "credits": meta.get("credits", 3),
            "enrolled_students": len(records),
            "average_marks": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "pass_percentage": pass_pct,
            "pass_count": pass_count,
            "tt2_entered_count": len(tt2_scores),
            "distribution": {
                "distinction": distinction_count,
                "first_class": first_class_count,
                "pass_class": pass_class_count,
                "fail": fail_count
            }
        })

    # Cohort Data & Maps
    cohort_records = list(db.academic_records.find({"semester": 5}))
    att_docs = list(db.attendance_records.find({}))
    attendance_map = {a["student_prn"]: a.get("percentage", 80.0) for a in att_docs}
    att_detail_map = {a["student_prn"]: a for a in att_docs}
    users_map = {u["prn_roll"]: u for u in db.users.find({"role": "student"})}

    quadrant_stars = []            # High marks (>= 15), High att (>= 75)
    quadrant_engagement = []       # High marks (>= 15), Low att (< 75)
    quadrant_tutoring = []         # Low marks (< 15), High att (>= 75)
    quadrant_critical = []         # Low marks (< 15), Low att (< 75)

    student_roster = []
    defaulters_list = []
    seen_students = set()

    for rec in cohort_records:
        prn = rec.get("student_prn")
        if not prn or prn in seen_students:
            continue
        
        stu_subs = rec.get("subjects", [])
        relevant_subs = [s for s in stu_subs if s.get("subject_code") in assigned_subjects] if (user and user.get("role") != "admin") else stu_subs
        if not relevant_subs:
            continue

        seen_students.add(prn)
        stu_user = users_map.get(prn, {})
        stu_name = stu_user.get("name", prn)
        att_doc = att_detail_map.get(prn, {})
        att = float(attendance_map.get(prn, rec.get("attendance_percentage", 80.0)))
        roll_no = att_doc.get("roll_no") or stu_user.get("roll_no") or prn[-3:]
        
        tt_scores = [float(s.get("tt1_score", 15.0)) for s in relevant_subs if s.get("tt1_score") is not None]
        avg_tt = round(float(sum(tt_scores) / len(tt_scores)), 1) if tt_scores else 15.0

        # Primary / subject specific breakdown
        sub_marks_map = {}
        for s in relevant_subs:
            sub_marks_map[s.get("subject_code")] = {
                "tt1": s.get("tt1_score"),
                "tt2": s.get("tt2_score"),
                "tt_converted": s.get("tt_converted"),
                "internal": s.get("internal_score"),
                "grade_letter": s.get("grade_letter", "Pending")
            }

        # Determine Quadrant
        if att >= 75.0 and avg_tt >= 15.0:
            quadrant_id = "stars"
            quadrant_label = "Star Performer"
        elif att < 75.0 and avg_tt >= 15.0:
            quadrant_id = "engagement_risk"
            quadrant_label = "Engagement Risk"
        elif att >= 75.0 and avg_tt < 15.0:
            quadrant_id = "tutoring_needed"
            quadrant_label = "Needs Tutoring"
        else:
            quadrant_id = "critical_risk"
            quadrant_label = "Critical Risk"

        student_entry = {
            "prn": prn,
            "name": stu_name,
            "roll_no": roll_no,
            "attendance": att,
            "avg_tt": avg_tt,
            "subjects": [s.get("subject_code") for s in relevant_subs],
            "sub_marks": sub_marks_map,
            "quadrant": quadrant_id,
            "quadrant_label": quadrant_label,
            "first_subject_code": relevant_subs[0].get("subject_code") if relevant_subs else (assigned_subjects[0] if assigned_subjects else "IS"),
            "first_subject_tt1": relevant_subs[0].get("tt1_score") if relevant_subs else None,
            "first_subject_tt2": relevant_subs[0].get("tt2_score") if relevant_subs else None,
            "first_subject_internal": relevant_subs[0].get("internal_score") if relevant_subs else None
        }

        if quadrant_id == "stars":
            quadrant_stars.append(student_entry)
        elif quadrant_id == "engagement_risk":
            quadrant_engagement.append(student_entry)
        elif quadrant_id == "tutoring_needed":
            quadrant_tutoring.append(student_entry)
        else:
            quadrant_critical.append(student_entry)

        student_roster.append(student_entry)

        # Check Defaulter (< 75% attendance)
        if att < 75.0:
            tot_att = att_doc.get("total_attended", 0)
            tot_cond = att_doc.get("total_conducted", 0)
            needed = max(0, int(3 * tot_cond - 4 * tot_att)) if tot_cond > 0 else 5
            defaulters_list.append({
                "prn": prn,
                "name": stu_name,
                "roll_no": roll_no,
                "attendance": att,
                "total_attended": tot_att,
                "total_conducted": tot_cond,
                "lectures_needed": needed,
                "avg_tt": avg_tt
            })

    # Sort defaulters by lowest attendance first
    defaulters_list.sort(key=lambda x: x["attendance"])
    # Sort roster by roll number or PRN
    student_roster.sort(key=lambda x: x["prn"])

    # High level Cohort Statistics
    cohort_att_values = [s["attendance"] for s in student_roster]
    avg_cohort_att = round(sum(cohort_att_values) / len(cohort_att_values), 1) if cohort_att_values else 75.0
    avg_cohort_tt = round(sum(all_assigned_tt1_scores) / len(all_assigned_tt1_scores), 1) if all_assigned_tt1_scores else 0.0
    overall_pass_count = sum(1 for sc in all_assigned_tt1_scores if sc >= 12.0)
    overall_pass_rate = round(overall_pass_count / len(all_assigned_tt1_scores) * 100.0, 1) if all_assigned_tt1_scores else 100.0

    cohort_stats = {
        "total_students": len(seen_students),
        "assigned_subjects_count": len(assigned_subjects),
        "avg_attendance": avg_cohort_att,
        "avg_tt1": avg_cohort_tt,
        "defaulters_count": len(defaulters_list),
        "critical_count": len(quadrant_critical),
        "stars_count": len(quadrant_stars),
        "overall_pass_rate": overall_pass_rate
    }

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

    # Chart datasets
    distinction_tot = sum(1 for sc in all_assigned_tt1_scores if sc >= 24.0)
    first_tot = sum(1 for sc in all_assigned_tt1_scores if 18.0 <= sc < 24.0)
    pass_tot = sum(1 for sc in all_assigned_tt1_scores if 12.0 <= sc < 18.0)
    fail_tot = sum(1 for sc in all_assigned_tt1_scores if sc < 12.0)

    chart_data = {
        "score_dist": {
            "labels": ["Needs Support (<12)", "Pass Class (12–17.9)", "First Class (18–23.9)", "Distinction (24–30)"],
            "data": [fail_tot, pass_tot, first_tot, distinction_tot]
        },
        "quadrants": {
            "labels": ["★ Stars", "⚠ Engagement Risk", "✎ Needs Tutoring", "⛔ Critical Risk"],
            "data": [len(quadrant_stars), len(quadrant_engagement), len(quadrant_tutoring), len(quadrant_critical)]
        }
    }

    # Recent interventions with student names
    raw_interventions = list(db.interventions.find({"faculty_prn": current_prn}).sort("timestamp", -1).limit(10)) if "interventions" in db.list_collection_names() or hasattr(db, "interventions") else []
    recent_interventions = []
    for iv in raw_interventions:
        st_p = iv.get("student_prn")
        st_u = users_map.get(st_p, {})
        recent_interventions.append({
            "student_prn": st_p,
            "student_name": st_u.get("name", st_p),
            "intervention_type": iv.get("intervention_type"),
            "subject_code": iv.get("subject_code"),
            "notes": iv.get("notes"),
            "timestamp": iv.get("timestamp"),
            "status": iv.get("status", "DISPATCHED")
        })

    return render_template(
        "faculty/faculty_dashboard.html",
        user=user,
        assigned_subjects=assigned_subjects,
        subject_summaries=subject_summaries,
        cohort_stats=cohort_stats,
        student_roster=student_roster,
        defaulters_list=defaulters_list,
        risk_quadrants=risk_quadrants,
        chart_data=chart_data,
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
            tt_conv = round((min(30.0, max(0.0, tt1)) + min(30.0, max(0.0, tt2))) / 4.0, 2)
            apt = float(target_sub.get("aptitude_score", 0.0))
            skat = float(target_sub.get("skat_score", 0.0))
            ta = float(target_sub.get("teacher_assessment_score", 0.0))
            mock = float(target_sub.get("mock_interview_score", 0.0))
            pres = float(target_sub.get("presentation_score", 0.0))
            internal = compute_subject_internal(tt1, tt2, apt, skat, ta, mock, pres)
            ese = float(target_sub.get("ese_score", 0.0))
            total_marks = round(min(100.0, internal + ese), 2)

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
                "ese_score": ese,
                "total_marks": total_marks,
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


def _get_registered_students_with_records(db):
    """Fetches all registered students with current year, semester, and completed academic history."""
    students_cursor = db.users.find(
        {"role": "student"},
        {
            "prn_roll": 1,
            "name": 1,
            "email": 1,
            "branch": 1,
            "current_year": 1,
            "current_semester": 1,
            "roll_no": 1,
            "class_name": 1,
            "cgpa": 1,
        }
    ).sort("roll_no", 1)
    students = list(students_cursor)
    for s in students:
        s["_id"] = str(s["_id"])
        year_ctx = get_student_year_context(s)
        s["year_num"] = year_ctx["year_num"]
        s["year_label"] = year_ctx["year_label"]
        s["default_semesters"] = year_ctx["default_semesters"]
        # Fetch completed semester records for this student
        recs = list(db.academic_records.find(
            {"student_prn": s["prn_roll"]},
            {"semester": 1, "sgpa": 1, "cgpa": 1, "credits_earned": 1, "is_real_marksheet": 1, "subjects": 1}
        ).sort("semester", 1))
        s["existing_semesters"] = [
            {
                "semester": int(r.get("semester", 1)),
                "sgpa": float(r.get("sgpa", 0.0) or 0.0),
                "cgpa": float(r.get("cgpa", 0.0) or 0.0),
                "credits": int(r.get("credits_earned", 0) or 0),
                "courses_count": len(r.get("subjects") or []),
                "is_real": bool(r.get("is_real_marksheet", False))
            }
            for r in recs
        ]
    return students


@faculty_bp.route("/api/registered-students", methods=["GET"])
@role_required(["faculty", "admin"])
def get_registered_students_api():
    """API returning registered student profiles with their year and completed semester records."""
    db = get_db()
    students = _get_registered_students_with_records(db)
    return jsonify({"status": "success", "count": len(students), "students": students})


@faculty_bp.route("/upload-results-pdf", methods=["GET", "POST"])
@role_required(["faculty", "admin"])
def upload_results_pdf():
    """Faculty endpoint for uploading student result marksheet PDFs section-wise with upcoming ML predictions."""
    db = get_db()
    current_prn = get_jwt_identity()

    if request.method == "GET":
        students = _get_registered_students_with_records(db)
        selected_prn = request.args.get("student_prn")
        selected_student = next((s for s in students if s["prn_roll"] == selected_prn), None) if selected_prn else None
        return render_template(
            "admin/upload_results_pdf.html",
            preview=None,
            students=students,
            students_json=json.dumps(students),
            selected_student=selected_student,
            prediction=None,
            committed=False
        )

    action = request.form.get("action", "parse")
    purge_legacy = request.form.get("purge_legacy", "true").lower() in ("true", "1", "on", "yes")

    # ---------------------------------------------------------
    # Mode 1: Section-Wise Upload for a Selected Registered Student
    # ---------------------------------------------------------
    if action in ("parse_sectionwise", "upload_and_predict", "upload_single_semester"):
        student_prn = request.form.get("student_prn", "").strip()
        auto_commit = request.form.get("auto_commit", "true").lower() in ("true", "1", "on", "yes") or (action in ("upload_and_predict", "upload_single_semester"))
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.is_json
            or request.form.get("ajax") == "true"
        )

        student_user = db.users.find_one({"prn_roll": student_prn})
        if not student_user:
            if is_ajax:
                return jsonify({"status": "error", "message": "Selected registered student was not found."}), 404
            flash("Selected registered student was not found.", "danger")
            return redirect(url_for("faculty.upload_results_pdf"))

        student_name = student_user.get("name", f"Student {student_prn}")
        parsed_records = []
        errors = []

        # Find files for each semester
        found_files = {}

        # 1. Single semester direct upload support (via individual card upload)
        single_sem = request.form.get("semester")
        if single_sem:
            try:
                single_sem_num = int(single_sem)
                f = request.files.get("file") or request.files.get(f"sem_file_{single_sem_num}")
                if f and f.filename:
                    found_files[single_sem_num] = f
            except ValueError:
                pass

        # 2. Multi-files by specific sem_file_X keys
        if not found_files:
            for key, file_storage in request.files.items():
                if key.startswith("sem_file_") and file_storage and file_storage.filename:
                    sem_str = key.replace("sem_file_", "")
                    try:
                        sem_num = int(sem_str)
                        found_files[sem_num] = file_storage
                    except ValueError:
                        pass

        # 3. Multi-files mapped by active_semesters
        if not found_files:
            active_sem_strs = request.form.getlist("active_semesters")
            if not active_sem_strs and request.form.get("active_semesters_csv"):
                active_sem_strs = [s.strip() for s in request.form.get("active_semesters_csv", "").split(",") if s.strip()]
            uploaded_list = request.files.getlist("pdf_files")
            for idx, f in enumerate(uploaded_list):
                if f and f.filename:
                    assigned_sem = int(active_sem_strs[idx]) if idx < len(active_sem_strs) else (idx + 1)
                    found_files[assigned_sem] = f

        if not found_files:
            if is_ajax:
                return jsonify({"status": "error", "message": f"Please select at least one semester result PDF to upload for {student_name}."}), 400
            flash(f"Please select at least one semester result PDF to upload for {student_name}.", "warning")
            return redirect(url_for("faculty.upload_results_pdf", student_prn=student_prn))

        for sem_num in sorted(found_files.keys()):
            file_storage = found_files[sem_num]
            try:
                rec = parse_result_pdf(
                    file_storage,
                    filename=file_storage.filename,
                    override_prn=student_prn,
                    override_semester=sem_num,
                    student_name_hint=student_name
                )
                parsed_records.append(rec)
            except Exception as e:
                errors.append(f"Failed to parse Semester {sem_num} ({file_storage.filename}): {str(e)}")

        if not parsed_records:
            if is_ajax:
                return jsonify({"status": "error", "message": "Could not parse result records from uploaded file(s). " + "; ".join(errors)}), 400
            flash("Could not parse result records from uploaded file(s). " + "; ".join(errors), "danger")
            return redirect(url_for("faculty.upload_results_pdf", student_prn=student_prn))

        batch_result = {
            "total_files": len(parsed_records),
            "success_count": sum(1 for r in parsed_records if r["status"] == "success"),
            "warning_count": sum(1 for r in parsed_records if r["status"] == "warning"),
            "error_count": sum(1 for r in parsed_records if r["status"] == "error") + len(errors),
            "records": parsed_records,
            "errors": errors,
            "purge_legacy": purge_legacy,
            "student_prn": student_prn,
            "student_name": student_name,
        }

        prediction = None
        committed = False

        if auto_commit:
            commit_res = commit_result_records(
                records=parsed_records,
                purge_legacy_seed=purge_legacy,
                actor_prn=current_prn
            )
            committed = True
            prediction = predict_student_analytics(student_prn, force_recalculate=True)

            log_audit_event(
                actor_prn=current_prn,
                actor_role="faculty",
                action="SECTIONWISE_PDF_RESULTS_COMMIT",
                details=f"Committed {len(parsed_records)} semester marksheets for student {student_name} ({student_prn})."
            )

            target_sem = prediction.get("target_semester", (parsed_records[-1]["semester"] + 1))
            flash(
                f"Successfully saved {len(parsed_records)} semester marksheet(s) for {student_name} ({student_prn})! AI model generated upcoming prediction for Semester {target_sem}.",
                "success"
            )
        else:
            flash(
                f"Parsed {len(parsed_records)} semester result(s) for {student_name} ({student_prn}). Please review below before committing.",
                "info"
            )

        students = _get_registered_students_with_records(db)
        student_user_fresh = next((s for s in students if s["prn_roll"] == student_prn), student_user)

        if is_ajax:
            latest_rec = parsed_records[-1] if parsed_records else {}
            return jsonify({
                "status": "success",
                "message": f"Successfully parsed and saved {len(parsed_records)} semester marksheet(s) for {student_name}!",
                "semester": latest_rec.get("semester"),
                "sgpa": latest_rec.get("sgpa") or latest_rec.get("computed_sgpa"),
                "computed_sgpa": latest_rec.get("computed_sgpa"),
                "credits_earned": latest_rec.get("credits_earned"),
                "courses_count": len(latest_rec.get("subjects") or []),
                "courses": latest_rec.get("subjects") or [],
                "records": parsed_records,
                "student": {
                    "prn_roll": student_prn,
                    "name": student_name,
                    "cgpa": student_user_fresh.get("cgpa"),
                    "credits_earned": student_user_fresh.get("credits_earned"),
                    "active_backlogs": student_user_fresh.get("active_backlogs", 0),
                    "existing_semesters": student_user_fresh.get("existing_semesters", [])
                },
                "prediction": {
                    "target_semester": prediction.get("target_semester") if prediction else None,
                    "predicted_next_sgpa": prediction.get("predicted_next_sgpa") if prediction else None,
                    "projected_cgpa": prediction.get("projected_cgpa") if prediction else None,
                    "current_attendance": prediction.get("current_attendance") or prediction.get("attendance_percentage") if prediction else None,
                    "detention_risk": prediction.get("detention_risk") if prediction else None,
                    "placement_readiness_score": prediction.get("placement_readiness_score") if prediction else None
                } if prediction else None
            }), 200

        return render_template(
            "admin/upload_results_pdf.html",
            preview=batch_result,
            staged_records_json=json.dumps(parsed_records),
            students=students,
            students_json=json.dumps(students),
            selected_student=student_user_fresh,
            prediction=prediction,
            committed=committed
        )

    # ---------------------------------------------------------
    # Mode 2: Commit Staged Records
    # ---------------------------------------------------------
    if action == "commit":
        raw_payload = request.form.get("staged_records")
        if not raw_payload:
            flash("No staged records provided for commit.", "danger")
            return redirect(url_for("faculty.upload_results_pdf"))

        try:
            staged_records = json.loads(raw_payload)
        except Exception as e:
            flash(f"Invalid record payload: {e}", "danger")
            return redirect(url_for("faculty.upload_results_pdf"))

        result = commit_result_records(
            records=staged_records,
            purge_legacy_seed=purge_legacy,
            actor_prn=current_prn
        )

        log_audit_event(
            actor_prn=current_prn,
            actor_role="faculty",
            action="PDF_RESULTS_COMMIT",
            details=f"Committed {result['committed_students_count']} real students across {result['committed_semesters_count']} semester marksheets."
        )

        affected_prns = result.get("affected_prns", [])
        prediction = None
        selected_student = None
        if affected_prns:
            first_prn = affected_prns[0]
            prediction = result.get("predictions", {}).get(first_prn) or predict_student_analytics(first_prn, force_recalculate=True)
            selected_student = db.users.find_one({"prn_roll": first_prn})

        students = _get_registered_students_with_records(db)
        flash(
            f"Successfully saved {result['committed_students_count']} student(s) with {result['committed_semesters_count']} verified marksheet records!",
            "success"
        )

        return render_template(
            "admin/upload_results_pdf.html",
            preview={"total_files": len(staged_records), "records": staged_records, "success_count": len(staged_records), "warning_count": 0, "error_count": 0, "errors": []},
            staged_records_json=json.dumps(staged_records),
            students=students,
            students_json=json.dumps(students),
            selected_student=selected_student,
            prediction=prediction,
            committed=True
        )

    # ---------------------------------------------------------
    # Mode 3: General Batch Upload
    # ---------------------------------------------------------
    uploaded_files = request.files.getlist("pdf_files")
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ""):
        if "file" in request.files and request.files["file"].filename:
            uploaded_files = [request.files["file"]]
        else:
            flash("Please select at least one PDF file or a ZIP archive to upload.", "warning")
            return redirect(url_for("faculty.upload_results_pdf"))

    batch_result = parse_batch_pdfs(uploaded_files, purge_legacy=purge_legacy)
    if not batch_result["records"]:
        flash("Could not parse any student result records from the uploaded file(s).", "danger")
        return redirect(url_for("faculty.upload_results_pdf"))

    flash(
        f"Parsed {batch_result['total_files']} marksheet(s): {batch_result['success_count']} high confidence, {batch_result['warning_count']} warnings.",
        "info"
    )

    students = _get_registered_students_with_records(db)
    return render_template(
        "admin/upload_results_pdf.html",
        preview=batch_result,
        staged_records_json=json.dumps(batch_result["records"]),
        students=students,
        students_json=json.dumps(students),
        selected_student=None,
        prediction=None,
        committed=False
    )


