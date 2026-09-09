from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from utils.db import get_db
from utils.decorators import role_required, faculty_subject_authorized
from utils.validators import MarksUpdateSchema
from utils.audit_logger import log_audit_event
from utils.grade_calculator import compute_semester_sgpa, compute_subject_total, calculate_grade_point
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

    # If Admin, show all subjects
    if user.get("role") == "admin":
        assigned_subjects = db.academic_records.distinct("subjects.subject_code")

    # Fetch summary for assigned subjects
    subject_summaries = []
    for code in assigned_subjects:
        records = list(db.academic_records.find({"subjects.subject_code": code}))
        sub_name = code
        scores = []
        for r in records:
            for s in r.get("subjects", []):
                if s.get("subject_code") == code:
                    sub_name = s.get("subject_name", code)
                    scores.append(float(s.get("total_marks", 0.0)))
        
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        pass_count = sum(1 for sc in scores if sc >= 40.0)
        pass_pct = round((pass_count / len(scores)) * 100.0, 1) if scores else 100.0

        subject_summaries.append({
            "subject_code": code,
            "subject_name": sub_name,
            "enrolled_students": len(records),
            "average_marks": avg_score,
            "pass_percentage": pass_pct
        })

    return render_template(
        "faculty/faculty_dashboard.html",
        user=user,
        assigned_subjects=assigned_subjects,
        subject_summaries=subject_summaries
    )


@faculty_bp.route("/grade-entry", methods=["GET", "POST"])
@role_required(["faculty", "admin"])
def grade_entry_view():
    """Grade entry interface for assigned subjects."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    assigned_subjects = user.get("assigned_subjects", []) if user else []

    if user.get("role") == "admin":
        assigned_subjects = db.academic_records.distinct("subjects.subject_code")

    selected_subject = request.args.get("subject_code") or (assigned_subjects[0] if assigned_subjects else None)
    selected_sem = int(request.args.get("semester", 1))

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
            students_data.append({
                "student_prn": prn,
                "student_name": student_user.get("name", prn),
                "branch": student_user.get("branch", ""),
                "semester": selected_sem,
                "subject_code": selected_subject,
                "tt1_score": target_sub.get("tt1_score", 0.0),
                "tt2_score": target_sub.get("tt2_score", 0.0),
                "ese_score": target_sub.get("ese_score", 0.0),
                "total_marks": target_sub.get("total_marks", 0.0),
                "grade_point": target_sub.get("grade_point", 0.0),
                "grade_letter": target_sub.get("grade_letter", "P"),
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

    # Update scores
    if "tt1_score" in data:
        subjects[target_idx]["tt1_score"] = float(data["tt1_score"])
    if "tt2_score" in data:
        subjects[target_idx]["tt2_score"] = float(data["tt2_score"])
    if "ese_score" in data:
        subjects[target_idx]["ese_score"] = float(data["ese_score"])

    # Deterministically calculate subject total & grade points
    tt1 = subjects[target_idx]["tt1_score"]
    tt2 = subjects[target_idx]["tt2_score"]
    ese = subjects[target_idx]["ese_score"]
    total = compute_subject_total(tt1, tt2, ese)
    gp, letter = calculate_grade_point(total)

    subjects[target_idx]["total_marks"] = total
    subjects[target_idx]["grade_point"] = gp
    subjects[target_idx]["grade_letter"] = letter

    # Update attendance if passed
    if "attendance_percentage" in data:
        record["attendance_percentage"] = float(data["attendance_percentage"])

    # Deterministically recalculate Semester SGPA
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

    # Audit log
    log_audit_event(
        actor_prn=current_prn,
        actor_role="faculty",
        action="EDIT_MARKS",
        target_student_prn=prn,
        before=before_state,
        after=subjects[target_idx],
        details=f"Subject {subject_code} marks updated. New SGPA: {new_sgpa:.2f}"
    )

    # Recalculate predictions in real-time
    new_predictions = predict_student_analytics(prn, force_recalculate=True)

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
        "new_sgpa": new_sgpa,
        "new_backlogs": new_backlogs,
        "predictions": new_predictions
    }), 200
