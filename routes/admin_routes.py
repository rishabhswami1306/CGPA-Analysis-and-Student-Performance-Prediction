import os
import io
import csv
import json
import pandas as pd
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename
from marshmallow import ValidationError

from utils.db import get_db
from utils.decorators import role_required
from utils.validators import UserRegisterSchema, UserUpdateSchema, AcademicRecordCreateSchema
from utils.audit_logger import log_audit_event
from utils.grade_calculator import compute_semester_sgpa, compute_subject_total, calculate_grade_point, compute_subject_internal, compute_cumulative_cgpa
from utils.pdf_generator import generate_student_transcript_pdf
from utils.pdf_result_parser import parse_batch_pdfs, commit_result_records, parse_result_pdf, get_student_year_context
from ml_engine.train_models import retrain_all_models
from ml_engine.inference import predict_student_analytics

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route("/dashboard", methods=["GET"])
@role_required(["admin"])
def dashboard_view():
    """Admin summary dashboard view scoped for TY CSE-DS cohort."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": current_prn})
    
    total_students = db.users.count_documents({"role": "student"})
    total_faculty = db.users.count_documents({"role": "faculty"})
    # Completed semester marksheets across Sem 1 to 4
    total_records = db.academic_records.count_documents({"semester": {"$lte": 4}, "is_completed": {"$ne": False}})
    
    # Students with attendance < 75% in the ongoing Semester 5 register
    detention_risk_count = db.attendance_records.count_documents({"percentage": {"$lt": 75.0}})
    
    # Recent audit logs
    recent_logs = list(db.audit_logs.find({}).sort("timestamp", -1).limit(8))
    for log in recent_logs:
        log["_id"] = str(log["_id"])

    cohort_info = {
        "branch": "Computer Science and Engineering (Data Science)",
        "branch_code": "CSE-DS",
        "class_name": "TY BTech DS (A)",
        "academic_year": "2026-27",
        "current_semester": 5,
        "completed_semesters": 4,
        "safe_students": total_students - detention_risk_count,
        "detained_students": detention_risk_count
    }

    # Student directory list for quick profile access
    students_list = list(db.users.find({"role": "student"}, {"prn_roll": 1, "name": 1, "email": 1, "branch": 1}).sort("prn_roll", 1))

    return render_template(
        "admin/admin_dashboard.html",
        user=user,
        total_students=total_students,
        total_faculty=total_faculty,
        total_records=total_records,
        detention_risk_count=detention_risk_count,
        cohort_info=cohort_info,
        recent_logs=recent_logs,
        students_list=students_list
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@role_required(["admin"])
def user_management():
    """User account CRUD with search, pagination, and role filters."""
    db = get_db()
    current_prn = get_jwt_identity()

    if request.method == "POST":
        # Create user
        payload = request.get_json() if request.is_json else request.form.to_dict()
        if "assigned_subjects" in payload and isinstance(payload["assigned_subjects"], str):
            payload["assigned_subjects"] = [s.strip() for s in payload["assigned_subjects"].split(",") if s.strip()]

        schema = UserRegisterSchema()
        try:
            data = schema.load(payload)
        except ValidationError as err:
            if request.is_json:
                return jsonify({"error": "Validation failed", "details": err.messages}), 400
            flash(f"Error: {err.messages}", "danger")
            return redirect(request.referrer or url_for("admin.user_management"))

        # Check uniqueness
        if db.users.find_one({"$or": [{"email": data["email"].lower()}, {"prn_roll": data["prn_roll"]}]}):
            msg = "A user with this Email or PRN already exists."
            if request.is_json:
                return jsonify({"error": msg}), 409
            flash(msg, "danger")
            return redirect(request.referrer or url_for("admin.user_management"))

        from routes.auth_routes import bcrypt
        pw_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

        new_user = {
            "prn_roll": data["prn_roll"],
            "email": data["email"].lower(),
            "password_hash": pw_hash,
            "role": data["role"],
            "name": data["name"],
            "branch": data["branch"],
            "admission_year": data["admission_year"],
            "assigned_subjects": data.get("assigned_subjects", []),
            "is_active": True,
            "must_change_password": True,
            "failed_login_attempts": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        db.users.insert_one(new_user)

        log_audit_event(
            actor_prn=current_prn,
            actor_role="admin",
            action="CREATE_USER",
            target_student_prn=data["prn_roll"],
            after={"email": data["email"], "role": data["role"], "name": data["name"]}
        )

        if request.is_json:
            return jsonify({"message": f"User {data['prn_roll']} created successfully."}), 201
        flash(f"User {data['name']} ({data['prn_roll']}) created successfully.", "success")
        return redirect(request.referrer or url_for("admin.user_management"))

    # GET: List users with pagination and filtering
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 15))
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()
    branch_filter = request.args.get("branch", "").strip()

    query = {}
    if role_filter:
        query["role"] = role_filter
    if branch_filter:
        query["branch"] = branch_filter
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"prn_roll": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]

    total_count = db.users.count_documents(query)
    users_cursor = db.users.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
    users_list = list(users_cursor)
    for u in users_list:
        u["_id"] = str(u["_id"])

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    if request.is_json:
        return jsonify({
            "users": users_list,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages
        }), 200

    return render_template(
        "admin/users_list.html",
        users=users_list,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        search=search,
        role_filter=role_filter,
        branch_filter=branch_filter
    )


@admin_bp.route("/users/<prn>", methods=["PUT", "POST", "DELETE"])
@admin_bp.route("/users/<prn>/edit", methods=["POST"])
@role_required(["admin"])
def user_detail_api(prn):
    """Update or deactivate/delete user."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": prn})

    if not user:
        if request.is_json:
            return jsonify({"error": "User not found"}), 404
        flash(f"User {prn} not found.", "danger")
        return redirect(url_for("admin.user_management"))

    if request.method == "DELETE":
        is_permanent = request.args.get("permanent", "false").lower() == "true"
        if is_permanent:
            db.users.delete_one({"_id": user["_id"]})
            del_acad = db.academic_records.delete_many({"student_prn": prn})
            del_att = db.attendance_records.delete_many({"student_prn": prn})
            if "interventions" in db.list_collection_names() or hasattr(db, "interventions"):
                db.interventions.delete_many({"student_prn": prn})
            log_audit_event(
                actor_prn=current_prn,
                actor_role="admin",
                action="DELETE_STUDENT_RECORD",
                target_student_prn=prn,
                details={"name": user.get("name"), "deleted_records": del_acad.deleted_count}
            )
            return jsonify({"message": f"Student {prn} and all associated records permanently deleted."}), 200
        else:
            # Soft delete / toggle active state
            new_status = not user.get("is_active", True)
            db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc)}})
            log_audit_event(
                actor_prn=current_prn,
                actor_role="admin",
                action="TOGGLE_USER_STATUS",
                target_student_prn=prn,
                before={"is_active": user.get("is_active", True)},
                after={"is_active": new_status}
            )
            return jsonify({"message": f"User active status toggled to {new_status}"}), 200

    # PUT or POST: Update details
    payload = request.get_json(silent=True) or request.form.to_dict()
    update_fields = {"updated_at": datetime.now(timezone.utc)}

    if "name" in payload and payload["name"].strip():
        update_fields["name"] = payload["name"].strip()
    if "email" in payload and payload["email"].strip():
        update_fields["email"] = payload["email"].strip().lower()
    if "branch" in payload and payload["branch"].strip():
        update_fields["branch"] = payload["branch"].strip()
    if "admission_year" in payload:
        try:
            update_fields["admission_year"] = int(payload["admission_year"])
        except (ValueError, TypeError):
            pass
    if "is_active" in payload:
        if isinstance(payload["is_active"], bool):
            update_fields["is_active"] = payload["is_active"]
        elif isinstance(payload["is_active"], str):
            update_fields["is_active"] = payload["is_active"].lower() in ("true", "1", "yes")

    db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})
    log_audit_event(
        actor_prn=current_prn,
        actor_role="admin",
        action="UPDATE_USER",
        target_student_prn=prn,
        before={k: user.get(k) for k in update_fields.keys()},
        after=update_fields
    )

    if request.is_json:
        return jsonify({"message": "User updated successfully.", "updated_fields": update_fields}), 200
    flash(f"User {user.get('name', prn)} ({prn}) updated successfully.", "success")
    return redirect(request.referrer or url_for("admin.user_management"))


@admin_bp.route("/users/<prn>/delete", methods=["POST"])
@role_required(["admin"])
def delete_student_user(prn):
    """Permanently deletes a student record from the institutional database."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": prn})
    if not user:
        if request.is_json:
            return jsonify({"error": "User not found"}), 404
        flash(f"User {prn} not found.", "danger")
        return redirect(url_for("admin.user_management"))

    # Delete user account
    db.users.delete_one({"_id": user["_id"]})
    # Delete academic records
    deleted_academic = db.academic_records.delete_many({"student_prn": prn})
    # Delete attendance records
    deleted_att = db.attendance_records.delete_many({"student_prn": prn})
    if "interventions" in db.list_collection_names() or hasattr(db, "interventions"):
        db.interventions.delete_many({"student_prn": prn})

    log_audit_event(
        actor_prn=current_prn,
        actor_role="admin",
        action="DELETE_STUDENT_RECORD",
        target_student_prn=prn,
        details={
            "name": user.get("name"),
            "email": user.get("email"),
            "deleted_academic_records": deleted_academic.deleted_count,
            "deleted_attendance_records": deleted_att.deleted_count
        }
    )

    if request.is_json:
        return jsonify({"message": f"Student {prn} and all associated records deleted permanently."}), 200
    flash(f"Student {user.get('name', prn)} ({prn}) and all academic records successfully deleted.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/students/<prn>", methods=["GET"])
@admin_bp.route("/student/<prn>", methods=["GET"])
@role_required(["admin"])
def student_profile_view(prn):
    """Comprehensive individual student profile with attendance, marks, and SGPA/CGPA history."""
    db = get_db()
    student = db.users.find_one({"prn_roll": prn})
    if not student:
        flash(f"Student with PRN {prn} not found.", "danger")
        return redirect(url_for("admin.user_management"))

    # Fetch attendance
    att_doc = db.attendance_records.find_one({"student_prn": prn}) or {}
    attendance_pct = float(att_doc.get("percentage", 80.0))
    total_conducted = att_doc.get("total_conducted", 0)
    total_attended = att_doc.get("total_attended", 0)
    lectures_needed = max(0, int(3 * total_conducted - 4 * total_attended)) if total_conducted > 0 else 0

    # Fetch all semester records
    sem_records = list(db.academic_records.find({"student_prn": prn}).sort("semester", 1))

    total_earned_points = 0.0
    total_completed_credits = 0
    total_backlogs = 0

    sem_summaries = []
    for r in sem_records:
        sem_num = r.get("semester")
        sgpa = r.get("sgpa")
        backlogs = r.get("active_backlogs", 0)
        total_backlogs += backlogs
        subs = r.get("subjects", [])
        sem_credits = sum(s.get("credits", 3) for s in subs)

        # Recalculate internal scores dynamically for consistent display
        for s in subs:
            s_tt1 = float(s.get("tt1_score", 0.0))
            s_tt2 = float(s.get("tt2_score", 0.0))
            s["tt_converted"] = round((min(30.0, max(0.0, s_tt1)) + min(30.0, max(0.0, s_tt2))) / 4.0, 2)
            s["internal_score"] = compute_subject_internal(
                s_tt1, s_tt2,
                float(s.get("aptitude_score", 0.0)),
                float(s.get("skat_score", 0.0)),
                float(s.get("teacher_assessment_score", 0.0)),
                float(s.get("mock_interview_score", 0.0)),
                float(s.get("presentation_score", 0.0))
            )
            s["total_marks"] = round(min(100.0, s["internal_score"] + float(s.get("ese_score", 0.0))), 2)

        if sgpa is not None and sem_num < 5:
            total_earned_points += (sgpa * sem_credits)
            total_completed_credits += sem_credits

        sem_summaries.append({
            "semester": sem_num,
            "sgpa": sgpa,
            "active_backlogs": backlogs,
            "credits": sem_credits,
            "is_completed": r.get("is_completed", sem_num < 5),
            "subjects": subs,
            "attendance": r.get("attendance_percentage", attendance_pct)
        })

    cgpa = round(total_earned_points / total_completed_credits, 2) if total_completed_credits > 0 else (sem_summaries[0]["sgpa"] if sem_summaries and sem_summaries[0]["sgpa"] else 8.0)

    # ML Predictions & Risk
    analytics = predict_student_analytics(prn)
    predicted_sgpa = analytics.get("predicted_next_sgpa")
    risk_level = analytics.get("risk_category", "LOW")

    return render_template(
        "admin/student_profile.html",
        student=student,
        attendance_pct=attendance_pct,
        total_conducted=total_conducted,
        total_attended=total_attended,
        lectures_needed=lectures_needed,
        sem_summaries=sem_summaries,
        cgpa=cgpa,
        total_completed_credits=total_completed_credits,
        total_backlogs=total_backlogs,
        predicted_sgpa=predicted_sgpa,
        risk_level=risk_level,
        analytics=analytics
    )


@admin_bp.route("/grade-entry", methods=["GET", "POST"])
@role_required(["admin"])
def grade_entry():
    """Admin marks entry interface allowing direct entry or updates for student results across semesters."""
    db = get_db()
    current_prn = get_jwt_identity()

    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form.to_dict()
        prn = payload.get("student_prn")
        try:
            sem = int(payload.get("semester", 5))
        except (ValueError, TypeError):
            sem = 5

        if not prn:
            if request.is_json:
                return jsonify({"error": "student_prn is required"}), 400
            flash("Student PRN is required.", "danger")
            return redirect(url_for("admin.grade_entry"))

        record = db.academic_records.find_one({"student_prn": prn, "semester": sem})
        if not record:
            record = {
                "student_prn": prn,
                "semester": sem,
                "attendance_percentage": float(payload.get("attendance_percentage", 80.0)),
                "subjects": [],
                "is_completed": sem < 5,
                "created_at": datetime.now(timezone.utc)
            }

        subjects = record.get("subjects", []) or record.get("courses", [])
        sub_code = payload.get("subject_code") or payload.get("course_code")

        if sub_code:
            target_idx = next(
                (i for i, s in enumerate(subjects) if s.get("subject_code") == sub_code or s.get("course_code") == sub_code),
                None
            )
            if target_idx is None:
                new_sub = {
                    "subject_code": sub_code,
                    "course_code": sub_code,
                    "subject_name": payload.get("subject_name") or payload.get("course_name") or sub_code,
                    "credits": int(payload.get("credits", 3))
                }
                subjects.append(new_sub)
                target_idx = len(subjects) - 1

            for field in [
                "tt1_score", "tt2_score", "aptitude_score", "assignment_score", "skat_score", "quiz_score",
                "teacher_assessment_score", "attendance_score", "mock_interview_score",
                "presentation_score", "seminar_score", "ese_score"
            ]:
                if field in payload:
                    try:
                        subjects[target_idx][field] = float(payload[field])
                    except (ValueError, TypeError):
                        pass

            tt1 = float(subjects[target_idx].get("tt1_score", 0.0))
            tt2 = float(subjects[target_idx].get("tt2_score", 0.0))
            apt = float(subjects[target_idx].get("aptitude_score") or subjects[target_idx].get("assignment_score", 0.0))
            sk = float(subjects[target_idx].get("skat_score") or subjects[target_idx].get("quiz_score", 0.0))
            ta = float(subjects[target_idx].get("teacher_assessment_score") or subjects[target_idx].get("attendance_score", 0.0))
            mock = float(subjects[target_idx].get("mock_interview_score", 0.0))
            pres = float(subjects[target_idx].get("presentation_score") or subjects[target_idx].get("seminar_score", 0.0))
            ese = float(subjects[target_idx].get("ese_score", 0.0))

            tt_conv = round((min(30.0, max(0.0, tt1)) + min(30.0, max(0.0, tt2))) / 4.0, 2)
            internal = compute_subject_internal(tt1, tt2, apt, sk, ta, mock, pres)
            total = compute_subject_total(tt1, tt2, ese, 60.0, apt, sk, ta, mock, pres, internal_score=internal)
            gp, letter = calculate_grade_point(total)

            subjects[target_idx]["subject_code"] = sub_code
            subjects[target_idx]["course_code"] = sub_code
            subjects[target_idx]["tt_converted"] = tt_conv
            subjects[target_idx]["tt_converted_15"] = tt_conv
            subjects[target_idx]["internal_score"] = internal
            subjects[target_idx]["total_internal_40"] = internal
            subjects[target_idx]["total_marks"] = total
            subjects[target_idx]["total_100"] = total
            subjects[target_idx]["grade_point"] = gp
            subjects[target_idx]["grade_letter"] = letter

        if "attendance_percentage" in payload:
            try:
                record["attendance_percentage"] = float(payload["attendance_percentage"])
            except (ValueError, TypeError):
                pass

        # Compute SGPA
        has_ese = any(float(s.get("ese_score", 0.0)) > 0 for s in subjects)
        if has_ese:
            record["is_completed"] = True

        is_ongoing = (sem == 5 and record.get("is_completed") is False and not has_ese)
        if is_ongoing:
            new_sgpa = None
            new_backlogs = 0
        else:
            new_sgpa, new_backlogs, _ = compute_semester_sgpa(subjects)

        record["subjects"] = subjects
        record["courses"] = subjects
        record["sgpa"] = new_sgpa
        record["active_backlogs"] = new_backlogs
        record["updated_at"] = datetime.now(timezone.utc)

        db.academic_records.update_one(
            {"student_prn": prn, "semester": sem},
            {"$set": record},
            upsert=True
        )

        # Invalidate predictions cache
        predict_student_analytics(prn, force_recalculate=True)

        log_audit_event(
            actor_prn=current_prn,
            actor_role="admin",
            action="ADMIN_UPDATE_MARKS",
            target_student_prn=prn,
            details=f"Admin updated Semester {sem} marks for student {prn} ({sub_code or 'bulk'})."
        )

        if request.is_json:
            return jsonify({
                "message": f"Marks updated successfully for {prn} in Semester {sem}.",
                "sgpa": new_sgpa,
                "subjects": subjects
            }), 200

        flash(f"Marks updated successfully for student {prn} in Semester {sem}.", "success")
        return redirect(url_for("admin.grade_entry", student_prn=prn, semester=sem))

    # GET: Render Admin Grade Entry Page
    students = list(db.users.find({"role": "student"}).sort("prn_roll", 1))
    selected_prn = request.args.get("student_prn") or (students[0]["prn_roll"] if students else None)
    try:
        selected_sem = int(request.args.get("semester", 5))
    except (ValueError, TypeError):
        selected_sem = 5

    student_data = None
    record_data = None
    subjects_data = []

    if selected_prn:
        student_data = db.users.find_one({"prn_roll": selected_prn})
        record_data = db.academic_records.find_one({"student_prn": selected_prn, "semester": selected_sem}) or {}
        subjects_data = record_data.get("subjects", [])

        # If no subjects yet for ongoing Sem 5, initialize default TY BTech DS subjects
        if not subjects_data and selected_sem == 5:
            default_subs = [
                {"code": "ML-II", "name": "Machine Learning II", "credits": 4},
                {"code": "IS", "name": "Information Security", "credits": 3},
                {"code": "DAA", "name": "Design & Analysis of Algorithms", "credits": 4},
                {"code": "CCN", "name": "Computer Communication & Networks", "credits": 3},
                {"code": "CCS", "name": "Cloud Computing Services", "credits": 3},
                {"code": "CI", "name": "Computational Intelligence", "credits": 3},
                {"code": "AJL", "name": "Advanced Java Lab", "credits": 2},
                {"code": "EM", "name": "Engineering Mathematics & Stats", "credits": 3}
            ]
            subjects_data = [{
                "subject_code": s["code"],
                "subject_name": s["name"],
                "credits": s["credits"],
                "tt1_score": 0.0,
                "tt2_score": 0.0,
                "tt_converted": 0.0,
                "aptitude_score": 0.0,
                "skat_score": 0.0,
                "teacher_assessment_score": 0.0,
                "mock_interview_score": 0.0,
                "presentation_score": 0.0,
                "internal_score": 0.0,
                "ese_score": 0.0,
                "total_marks": 0.0,
                "grade_point": 0.0,
                "grade_letter": "Pending"
            } for s in default_subs]
        else:
            for s in subjects_data:
                tt1 = float(s.get("tt1_score", 0.0))
                tt2 = float(s.get("tt2_score", 0.0))
                s["tt_converted"] = round((min(30.0, max(0.0, tt1)) + min(30.0, max(0.0, tt2))) / 4.0, 2)
                s["internal_score"] = compute_subject_internal(
                    tt1, tt2,
                    float(s.get("aptitude_score", 0.0)),
                    float(s.get("skat_score", 0.0)),
                    float(s.get("teacher_assessment_score", 0.0)),
                    float(s.get("mock_interview_score", 0.0)),
                    float(s.get("presentation_score", 0.0))
                )
                ese = float(s.get("ese_score", 0.0))
                s["total_marks"] = round(min(100.0, s["internal_score"] + ese), 2)

    return render_template(
        "admin/grade_entry.html",
        students=students,
        selected_prn=selected_prn,
        selected_sem=selected_sem,
        student_data=student_data,
        record_data=record_data,
        subjects_data=subjects_data
    )


@admin_bp.route("/students/<prn>/recalculate-cgpa", methods=["POST"])
@role_required(["admin"])
def recalculate_student_cgpa(prn):
    """Recalculates SGPA for all completed semesters and updates student cumulative CGPA."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": prn})
    if not user:
        return jsonify({"error": "Student not found"}), 404

    records = list(db.academic_records.find({"student_prn": prn}).sort("semester", 1))
    total_pts = 0.0
    total_creds = 0
    updated_sems = []

    for rec in records:
        sem = rec.get("semester")
        subs = rec.get("subjects", [])
        if sem < 5 or (rec.get("is_completed") is not False and any(float(s.get("ese_score", 0.0)) > 0 for s in subs)):
            sgpa, backlogs, creds = compute_semester_sgpa(subs)
            rec["sgpa"] = sgpa
            rec["active_backlogs"] = backlogs
            db.academic_records.update_one({"_id": rec["_id"]}, {"$set": {"sgpa": sgpa, "active_backlogs": backlogs}})
            total_pts += (sgpa * creds)
            total_creds += creds
            updated_sems.append({"semester": sem, "sgpa": sgpa, "credits": creds, "backlogs": backlogs})

    new_cgpa = round(total_pts / total_creds, 2) if total_creds > 0 else 8.0
    db.users.update_one({"_id": user["_id"]}, {"$set": {"cgpa": new_cgpa, "updated_at": datetime.now(timezone.utc)}})
    predict_student_analytics(prn, force_recalculate=True)

    log_audit_event(
        actor_prn=current_prn,
        actor_role="admin",
        action="RECALCULATE_CGPA",
        target_student_prn=prn,
        details=f"Admin recalculated CGPA for {prn}: {new_cgpa} across {len(updated_sems)} completed semesters."
    )

    if request.is_json:
        return jsonify({
            "message": f"Successfully recalculated SGPA and CGPA for student {prn}.",
            "cgpa": new_cgpa,
            "total_credits": total_creds,
            "semesters": updated_sems
        }), 200

    flash(f"Successfully recalculated SGPA and CGPA ({new_cgpa}) for student {prn}.", "success")
    return redirect(url_for("admin.student_profile_view", prn=prn))


@admin_bp.route("/bulk-upload", methods=["GET", "POST"])
@role_required(["admin"])
def bulk_upload():
    """
    Bulk CSV / Excel upload handler with dry-run validation preview and direct commit.
    Prevents partial corrupted writes: previews all errors before committing, syncs
    attendance records, updates user cumulative CGPA, and refreshes ML predictions.
    """
    if request.method == "GET":
        return render_template("admin/bulk_upload.html")

    db = get_db()
    current_prn = get_jwt_identity()
    commit_mode = request.form.get("commit", "false").lower() == "true"
    staged_json = request.form.get("staged_data")

    # If staged JSON submitted from preview page
    if staged_json:
        try:
            valid_rows = json.loads(staged_json)
        except Exception as e:
            flash(f"Invalid staged records data: {e}", "danger")
            return redirect(url_for("admin.bulk_upload"))
        commit_mode = True
        df_len = len(valid_rows)
        errors = []
    else:
        if "file" not in request.files:
            flash("No file part in request.", "danger")
            return redirect(url_for("admin.bulk_upload"))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("admin.bulk_upload"))

        if not allowed_file(file.filename):
            flash("Invalid file format. Allowed formats: .csv, .xlsx, .xls", "danger")
            return redirect(url_for("admin.bulk_upload"))

        try:
            filename = secure_filename(file.filename)
            if filename.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            flash(f"Failed to parse file: {str(e)}", "danger")
            return render_template("admin/bulk_upload.html", error=str(e))

        # Required columns validation
        required_cols = ["student_prn", "semester", "subject_code", "subject_name", "credits", "tt1_score", "tt2_score", "ese_score", "attendance_percentage"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            flash(f"Missing required columns: {', '.join(missing_cols)}", "danger")
            return render_template("admin/bulk_upload.html", error=f"Missing columns: {missing_cols}")

        df_len = len(df)
        errors = []
        valid_rows = []
        seen_prn_sem_sub = set()

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 1-based indexing + header
            prn = str(row.get("student_prn", "")).strip()
            
            try:
                sem = int(row.get("semester"))
                sub_code = str(row.get("subject_code", "")).strip()
                sub_name = str(row.get("subject_name", "")).strip()
                credits = int(row.get("credits", 4))
                tt1 = float(row.get("tt1_score", 0.0))
                tt2 = float(row.get("tt2_score", 0.0))
                ese = float(row.get("ese_score", 0.0))
                att = float(row.get("attendance_percentage", 80.0))
            except (ValueError, TypeError) as e:
                errors.append(f"Row {row_num}: Data conversion error ({e})")
                continue

            # Checks
            if not prn:
                errors.append(f"Row {row_num}: PRN is blank.")
            if sem < 1 or sem > 8:
                errors.append(f"Row {row_num}: Semester {sem} out of range (1-8).")
            if credits < 1 or credits > 6:
                errors.append(f"Row {row_num}: Credits {credits} out of range (1-6).")
            if tt1 < 0 or tt1 > 30:
                errors.append(f"Row {row_num}: TT1 score {tt1} must be between 0 and 30.")
            if tt2 < 0 or tt2 > 30:
                errors.append(f"Row {row_num}: TT2 score {tt2} must be between 0 and 30.")
            if ese < 0 or ese > 100:
                errors.append(f"Row {row_num}: ESE score {ese} must be between 0 and 100.")
            if att < 0 or att > 100:
                errors.append(f"Row {row_num}: Attendance {att}% must be between 0 and 100.")

            key = (prn, sem, sub_code)
            if key in seen_prn_sem_sub:
                errors.append(f"Row {row_num}: Duplicate entry for student {prn}, Semester {sem}, Subject {sub_code} in upload file.")
            else:
                seen_prn_sem_sub.add(key)

            valid_rows.append({
                "student_prn": prn,
                "semester": sem,
                "subject_code": sub_code,
                "subject_name": sub_name,
                "credits": credits,
                "tt1_score": tt1,
                "tt2_score": tt2,
                "ese_score": ese,
                "attendance_percentage": att
            })

    # If errors exist or dry-run requested, show preview
    if errors or not commit_mode:
        return render_template(
            "admin/bulk_upload_preview.html",
            total_rows=df_len,
            valid_count=len(valid_rows),
            error_count=len(errors),
            errors=errors[:50],  # Show first 50 errors
            preview_rows=valid_rows[:10],
            staged_records_json=json.dumps(valid_rows),
            can_commit=len(errors) == 0 and len(valid_rows) > 0
        )

    # Commit Mode: Group by (student_prn, semester) and write to academic_records
    grouped = {}
    for r in valid_rows:
        key = (r["student_prn"], r["semester"])
        if key not in grouped:
            grouped[key] = {
                "student_prn": r["student_prn"],
                "semester": r["semester"],
                "attendance_percentage": r["attendance_percentage"],
                "subjects": []
            }
        
        total_marks = compute_subject_total(r["tt1_score"], r["tt2_score"], r["ese_score"])
        gp, letter = calculate_grade_point(total_marks)
        ca_val = round((r["tt1_score"] + r["tt2_score"]) / 2.0, 1)
        tt_conv = round(ca_val * 0.5, 2)
        sub_doc = {
            "subject_code": r["subject_code"],
            "course_code": r["subject_code"],
            "subject_name": r["subject_name"],
            "course_name": r["subject_name"],
            "credits": r["credits"],
            "tt1_score": r["tt1_score"],
            "tt2_score": r["tt2_score"],
            "tt_converted": tt_conv,
            "tt_converted_15": tt_conv,
            "ca_marks": ca_val,
            "internal_score": ca_val,
            "total_internal_40": ca_val,
            "ese_score": r["ese_score"],
            "ese_marks": r["ese_score"],
            "total_marks": total_marks,
            "total_100": total_marks,
            "grade_point": gp,
            "grade_letter": letter
        }
        grouped[key]["subjects"].append(sub_doc)

    inserted_count = 0
    updated_students = set()

    for (prn, sem), rec in grouped.items():
        sgpa, backlogs, total_credits = compute_semester_sgpa(rec["subjects"])
        rec["courses"] = rec["subjects"]
        rec["sgpa"] = sgpa
        rec["active_backlogs"] = backlogs
        rec["credits_earned"] = total_credits
        rec["is_completed"] = (sem < 5 or any(s.get("ese_score", 0) > 0 for s in rec["subjects"]))
        rec["status"] = "completed" if rec["is_completed"] else "ongoing"
        rec["updated_at"] = datetime.now(timezone.utc)

        db.academic_records.update_one(
            {"student_prn": prn, "semester": sem},
            {
                "$set": rec,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )

        # Synchronize attendance collection
        att_pct = float(rec.get("attendance_percentage", 80.0))
        db.attendance_records.update_one(
            {"student_prn": prn, "semester": sem},
            {
                "$set": {
                    "attendance_percentage": att_pct,
                    "percentage": att_pct,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "student_prn": prn,
                    "semester": sem,
                    "total_conducted": 120,
                    "total_attended": int(120 * att_pct / 100),
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        inserted_count += 1
        updated_students.add(prn)

    # Recalculate cumulative CGPA for all updated students in db.users
    for prn in updated_students:
        all_recs = list(db.academic_records.find({"student_prn": prn, "is_completed": True, "sgpa": {"$ne": None}}).sort("semester", 1))
        if all_recs:
            cum_cgpa, tot_backlogs, tot_credits = compute_cumulative_cgpa(all_recs)
            db.users.update_one(
                {"prn_roll": prn},
                {"$set": {
                    "cgpa": cum_cgpa,
                    "active_backlogs": tot_backlogs,
                    "credits_earned": tot_credits,
                }}
            )

    # Log audit event
    log_audit_event(
        actor_prn=current_prn,
        actor_role="admin",
        action="BULK_UPLOAD",
        details=f"Committed {len(valid_rows)} marks rows across {inserted_count} semester records."
    )

    # Auto-retrain ML Models since new ground truth is added!
    try:
        retrain_all_models()
        flash(f"Successfully committed {inserted_count} semester records. ML models auto-retrained on fresh data!", "success")
    except Exception as e:
        flash(f"Committed {inserted_count} semester records. (Model retrain notice: {e})", "warning")

    # Invalidate predictions cache for affected students
    for prn in updated_students:
        predict_student_analytics(prn, force_recalculate=True)

    return redirect(url_for("admin.dashboard_view"))


@admin_bp.route("/audit-logs", methods=["GET"])
@role_required(["admin"])
def audit_logs_view():
    """Audit log viewer with filters for actor, action type, and date range."""
    db = get_db()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    action_filter = request.args.get("action", "").strip()
    actor_filter = request.args.get("actor", "").strip()
    target_filter = request.args.get("target", "").strip()

    query = {}
    if action_filter:
        query["action"] = action_filter
    if actor_filter:
        query["actor_prn"] = {"$regex": actor_filter, "$options": "i"}
    if target_filter:
        query["target_student_prn"] = {"$regex": target_filter, "$options": "i"}

    total_count = db.audit_logs.count_documents(query)
    logs_cursor = db.audit_logs.find(query).sort("timestamp", -1).skip((page - 1) * per_page).limit(per_page)
    logs = list(logs_cursor)
    for l in logs:
        l["_id"] = str(l["_id"])

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    if request.is_json:
        return jsonify({"logs": logs, "total_count": total_count, "page": page, "total_pages": total_pages}), 200

    return render_template(
        "admin/audit_logs.html",
        logs=logs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        action_filter=action_filter,
        actor_filter=actor_filter,
        target_filter=target_filter
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
            {
                "student_prn": s["prn_roll"],
                "sgpa": {"$ne": None},
                "$or": [{"is_completed": True}, {"is_real_marksheet": True}]
            },
            {"semester": 1, "sgpa": 1, "cgpa": 1, "credits_earned": 1, "is_real_marksheet": 1, "subjects": 1}
        ).sort("semester", 1))
        s["existing_semesters"] = [
            {
                "semester": int(r.get("semester", 1)),
                "sgpa": float(r.get("sgpa") or 0.0),
                "cgpa": float(r.get("cgpa") or r.get("sgpa") or 0.0),
                "credits": int(r.get("credits_earned") or (sum(int(sub.get("credits", 4)) for sub in r.get("subjects", [])) if r.get("subjects") else 20)),
                "courses_count": len(r.get("subjects") or []),
                "is_real": bool(r.get("is_real_marksheet", False))
            }
            for r in recs
            if r.get("sgpa") is not None
        ]
    return students


@admin_bp.route("/api/registered-students", methods=["GET"])
@role_required(["admin"])
def get_registered_students_api():
    """API returning registered student profiles with their year and completed semester records."""
    db = get_db()
    students = _get_registered_students_with_records(db)
    return jsonify({"status": "success", "count": len(students), "students": students})


@admin_bp.route("/upload-results-pdf", methods=["GET", "POST"])
@role_required(["admin"])
def upload_results_pdf():
    """
    Parses and ingests authentic student result marksheet PDFs (or ZIP archives).
    Supports section-wise semester upload for a selected registered student based on their current year,
    scans and fetches data directly into the selected student, commits genuine records,
    and runs the AI predictive model to forecast the upcoming semester performance.
    """
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
            return redirect(url_for("admin.upload_results_pdf"))

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
            return redirect(url_for("admin.upload_results_pdf", student_prn=student_prn))

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
            return redirect(url_for("admin.upload_results_pdf", student_prn=student_prn))

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
                actor_role="admin",
                action="SECTIONWISE_PDF_RESULTS_COMMIT",
                details=f"Committed {len(parsed_records)} semester marksheets for student {student_name} ({student_prn})."
            )

            target_sem = prediction.get("target_semester", (parsed_records[-1]["semester"] + 1))
            flash(
                f"Successfully saved {len(parsed_records)} semester marksheet(s) for {student_name} ({student_prn})! AI model re-analyzed cumulative data and generated upcoming prediction for Semester {target_sem}.",
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
            return redirect(url_for("admin.upload_results_pdf"))

        try:
            staged_records = json.loads(raw_payload)
        except Exception as e:
            flash(f"Invalid record payload: {e}", "danger")
            return redirect(url_for("admin.upload_results_pdf"))

        result = commit_result_records(
            records=staged_records,
            purge_legacy_seed=purge_legacy,
            actor_prn=current_prn
        )

        log_audit_event(
            actor_prn=current_prn,
            actor_role="admin",
            action="PDF_RESULTS_COMMIT",
            details=f"Committed {result['committed_students_count']} real students across {result['committed_semesters_count']} semester marksheets. Purge mock data: {purge_legacy}."
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
            f"Successfully saved {result['committed_students_count']} student(s) with {result['committed_semesters_count']} verified marksheet records! ML models updated with upcoming performance predictions.",
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
    # Mode 3: General Batch Upload (Multiple students / ZIP)
    # ---------------------------------------------------------
    uploaded_files = request.files.getlist("pdf_files")
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ""):
        if "file" in request.files and request.files["file"].filename:
            uploaded_files = [request.files["file"]]
        else:
            flash("Please select at least one PDF file or a ZIP archive to upload.", "warning")
            return redirect(url_for("admin.upload_results_pdf"))

    batch_result = parse_batch_pdfs(uploaded_files, purge_legacy=purge_legacy)
    if not batch_result["records"]:
        flash("Could not parse any student result records from the uploaded file(s).", "danger")
        return redirect(url_for("admin.upload_results_pdf"))

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


@admin_bp.route("/retrain", methods=["POST"])
@role_required(["admin"])
def trigger_retrain():
    """Manual trigger to retrain all ML pipelines."""
    current_prn = get_jwt_identity()
    try:
        report = retrain_all_models()
        log_audit_event(
            actor_prn=current_prn,
            actor_role="admin",
            action="MODEL_RETRAIN",
            details=report
        )
        return jsonify({"message": "All ML models successfully retrained and validated.", "metrics": report}), 200
    except Exception as e:
        return jsonify({"error": f"Retraining failed: {str(e)}"}), 500
