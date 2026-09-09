import os
import json
from datetime import date
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from utils.db import get_db
from utils.decorators import role_required
from utils.attendance_engine import (
    compute_attendance_predictions,
    simulate_what_if,
    get_semester_milestones,
    TIMETABLE,
    WEEKLY_THEORY_LECTURES,
    FORTNIGHTLY_PRACTICALS,
    SUBJECTS,
    HONORS_SUBJECTS,
    TEACHING_STAFF,
    SEM_START,
    SEM_END,
    HOLIDAYS,
    TERM_TEST_DAYS,
)

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.route("", methods=["GET"])
@attendance_bp.route("/", methods=["GET"])
@attendance_bp.route("/forecast", methods=["GET"])
@role_required(["student", "admin", "faculty"])
def forecast_view():
    """Main Attendance Forecast & Intelligence Hub."""
    claims = get_jwt()
    current_prn = get_jwt_identity()
    user_role = claims.get("role")

    target_prn = request.args.get("student_prn")
    if target_prn:
        student_prn = target_prn
    elif user_role == "student":
        student_prn = current_prn
    else:
        # Default for admin/faculty when no PRN is passed: first student
        db = get_db()
        first_student = db.users.find_one({"role": "student"}, sort=[("roll_no", 1)])
        student_prn = first_student["prn_roll"] if first_student else current_prn

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        flash(f"Student record for PRN {student_prn} not found.", "warning")
        return redirect(url_for("attendance.detention_list_view"))

    att_record = db.attendance_records.find_one({"student_prn": student_prn})
    if not att_record:
        # Fallback empty record if not yet seeded
        att_record = {
            "student_prn": student_prn,
            "subjects": {},
            "total_attended": 0,
            "total_conducted": 0,
            "percentage": 0.0,
            "is_detained": False,
        }

    # Run the comprehensive prediction model
    forecast = compute_attendance_predictions(student_prn, att_record)
    milestones = get_semester_milestones()

    # Populate student list for quick dropdown selector for all users
    students_dropdown = []
    all_students = list(db.users.find({"role": "student"}).sort("roll_no", 1))
    for s in all_students:
        s_att = db.attendance_records.find_one({"student_prn": s["prn_roll"]}) or {}
        students_dropdown.append({
            "prn": s["prn_roll"],
            "name": s["name"],
            "roll_no": s.get("roll_no", ""),
            "pct": s_att.get("percentage", 0.0),
            "is_detained": s_att.get("is_detained", False),
        })

    timetable_days = [
        {"name": "Monday", "day_idx": 0, "slots": TIMETABLE.get(0, [])},
        {"name": "Tuesday", "day_idx": 1, "slots": TIMETABLE.get(1, [])},
        {"name": "Wednesday", "day_idx": 2, "slots": TIMETABLE.get(2, [])},
        {"name": "Thursday", "day_idx": 3, "slots": TIMETABLE.get(3, [])},
        {"name": "Friday", "day_idx": 4, "slots": TIMETABLE.get(4, [])},
        {"name": "Saturday", "day_idx": 5, "slots": TIMETABLE.get(5, [])},
    ]

    return render_template(
        "attendance/attendance_forecast.html",
        user=user,
        user_role=user_role,
        student_prn=student_prn,
        att_record=att_record,
        forecast=forecast,
        milestones=milestones,
        students_dropdown=students_dropdown,
        timetable_days=timetable_days,
        weekly_theory=WEEKLY_THEORY_LECTURES,
        teaching_staff=TEACHING_STAFF,
    )


@attendance_bp.route("/detention-list", methods=["GET"])
@role_required(["student", "admin", "faculty"])
def detention_list_view():
    """Class-wide Detention List & Attendance Register for TY DS (A)."""
    db = get_db()
    claims = get_jwt()
    current_prn = get_jwt_identity()
    user_role = claims.get("role")
    current_user = db.users.find_one({"prn_roll": current_prn})

    filter_status = request.args.get("status", "all")  # 'all', 'detained', 'safe'
    search_query = request.args.get("q", "").strip().lower()

    # Query all attendance records with user details
    records = list(db.attendance_records.find().sort("roll_no", 1))

    # Enrich with user info
    enriched = []
    detained_count = 0
    safe_count = 0
    total_pct_sum = 0.0

    for rec in records:
        prn = rec.get("student_prn")
        u = db.users.find_one({"prn_roll": prn}) or {}
        pct = float(rec.get("percentage", 0.0))
        is_detained = pct < 75.0 or rec.get("is_detained", False)

        if is_detained:
            detained_count += 1
        else:
            safe_count += 1
        total_pct_sum += pct

        item = {
            "prn": prn,
            "roll_no": rec.get("roll_no") or u.get("roll_no", ""),
            "name": u.get("name", "Student"),
            "email": u.get("email", ""),
            "local_guardian": rec.get("local_guardian", "Faculty"),
            "honors_course": rec.get("honors_course") or "None",
            "total_attended": rec.get("total_attended", 0),
            "total_conducted": rec.get("total_conducted", 0),
            "percentage": pct,
            "is_detained": is_detained,
            "subjects": rec.get("subjects", {}),
        }

        # Filter check
        matches_status = True
        if filter_status == "detained" and not is_detained:
            matches_status = False
        elif filter_status == "safe" and is_detained:
            matches_status = False

        matches_search = True
        if search_query:
            q_in_name = search_query in item["name"].lower()
            q_in_prn = search_query in item["prn"].lower()
            q_in_roll = search_query in str(item["roll_no"]).lower()
            q_in_lg = search_query in item["local_guardian"].lower()
            matches_search = q_in_name or q_in_prn or q_in_roll or q_in_lg

        if matches_status and matches_search:
            enriched.append(item)

    total_count = len(records)
    avg_pct = round(total_pct_sum / total_count, 1) if total_count > 0 else 0.0

    return render_template(
        "attendance/detention_list.html",
        current_user=current_user,
        user_role=user_role,
        students=enriched,
        total_count=total_count,
        detained_count=detained_count,
        safe_count=safe_count,
        avg_pct=avg_pct,
        filter_status=filter_status,
        search_query=search_query,
    )


@attendance_bp.route("/api/simulate", methods=["POST"])
@role_required(["student", "admin", "faculty"])
def api_simulate():
    """AJAX endpoint for What-If attendance simulation."""
    data = request.get_json() or {}
    try:
        attended = int(data.get("attended", 0))
        conducted = int(data.get("conducted", 0))
        remaining = int(data.get("remaining", 40))
        extra_attend = int(data.get("extra_attend", 0))
        extra_miss = int(data.get("extra_miss", 0))
        target_pct = float(data.get("target_pct", 75.0))

        sim_res = simulate_what_if(
            attended=attended,
            conducted=conducted,
            remaining=remaining,
            extra_attend=extra_attend,
            extra_miss=extra_miss,
            target_pct=target_pct,
        )
        return jsonify(sim_res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@attendance_bp.route("/api/student/<prn>", methods=["GET"])
@role_required(["student", "admin", "faculty"])
def api_student_forecast(prn):
    """JSON API returning full attendance forecast for a given PRN."""
    db = get_db()
    att_record = db.attendance_records.find_one({"student_prn": prn})
    if not att_record:
        return jsonify({"error": "Student attendance record not found"}), 404

    forecast = compute_attendance_predictions(prn, att_record)
    return jsonify(forecast), 200
