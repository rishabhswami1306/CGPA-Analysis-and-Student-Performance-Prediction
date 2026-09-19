import os
import io
import csv
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
from utils.grade_calculator import compute_semester_sgpa, compute_subject_total, calculate_grade_point
from utils.pdf_generator import generate_student_transcript_pdf
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
    
    total_students = db.users.count_documents({"role": "student", "branch": "CSE-DS"})
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
        "branch": "Computer Engineering (Data Science)",
        "branch_code": "CSE-DS",
        "class_name": "TY BTech DS (A)",
        "academic_year": "2026-27",
        "current_semester": 5,
        "completed_semesters": 4,
        "safe_students": total_students - detention_risk_count,
        "detained_students": detention_risk_count
    }

    return render_template(
        "admin/admin_dashboard.html",
        total_students=total_students,
        total_faculty=total_faculty,
        total_records=total_records,
        detention_risk_count=detention_risk_count,
        cohort_info=cohort_info,
        recent_logs=recent_logs
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
            return redirect(url_for("admin.user_management"))

        # Check uniqueness
        if db.users.find_one({"$or": [{"email": data["email"].lower()}, {"prn_roll": data["prn_roll"]}]}):
            msg = "A user with this Email or PRN already exists."
            if request.is_json:
                return jsonify({"error": msg}), 409
            flash(msg, "danger")
            return redirect(url_for("admin.user_management"))

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
        return redirect(url_for("admin.user_management"))

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


@admin_bp.route("/users/<prn>", methods=["PUT", "DELETE"])
@role_required(["admin"])
def user_detail_api(prn):
    """Update or deactivate user."""
    db = get_db()
    current_prn = get_jwt_identity()
    user = db.users.find_one({"prn_roll": prn})

    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == "DELETE":
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

    # PUT: Update details
    payload = request.get_json()
    schema = UserUpdateSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    update_fields = {"updated_at": datetime.now(timezone.utc)}
    for k, v in data.items():
        update_fields[k] = v

    db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})
    log_audit_event(
        actor_prn=current_prn,
        actor_role="admin",
        action="UPDATE_USER",
        target_student_prn=prn,
        before={k: user.get(k) for k in data.keys()},
        after=data
    )
    return jsonify({"message": "User updated successfully."}), 200


@admin_bp.route("/bulk-upload", methods=["GET", "POST"])
@role_required(["admin"])
def bulk_upload():
    """
    Bulk CSV / Excel upload handler with dry-run validation preview.
    Prevents partial corrupted writes: previews all errors before committing.
    """
    if request.method == "GET":
        return render_template("admin/bulk_upload.html")

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

    commit_mode = request.form.get("commit", "false").lower() == "true"
    current_prn = get_jwt_identity()

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

    # Row-by-row validation
    db = get_db()
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
        if tt1 < 0 or tt1 > 20:
            errors.append(f"Row {row_num}: TT1 score {tt1} must be between 0 and 20.")
        if tt2 < 0 or tt2 > 20:
            errors.append(f"Row {row_num}: TT2 score {tt2} must be between 0 and 20.")
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
            total_rows=len(df),
            valid_count=len(valid_rows),
            error_count=len(errors),
            errors=errors[:50],  # Show first 50 errors
            preview_rows=valid_rows[:10],
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
        grouped[key]["subjects"].append({
            "subject_code": r["subject_code"],
            "subject_name": r["subject_name"],
            "credits": r["credits"],
            "tt1_score": r["tt1_score"],
            "tt2_score": r["tt2_score"],
            "ese_score": r["ese_score"],
            "total_marks": total_marks,
            "grade_point": gp,
            "grade_letter": letter
        })

    inserted_count = 0
    updated_students = set()

    for (prn, sem), rec in grouped.items():
        sgpa, backlogs, total_credits = compute_semester_sgpa(rec["subjects"])
        rec["sgpa"] = sgpa
        rec["active_backlogs"] = backlogs
        rec["updated_at"] = datetime.now(timezone.utc)

        db.academic_records.update_one(
            {"student_prn": prn, "semester": sem},
            {
                "$set": rec,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        inserted_count += 1
        updated_students.add(prn)

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
        flash(f"Successfully processed {inserted_count} semester records. ML models auto-retrained on fresh data!", "success")
    except Exception as e:
        flash(f"Processed {inserted_count} semester records. (Model retrain notice: {e})", "warning")

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
