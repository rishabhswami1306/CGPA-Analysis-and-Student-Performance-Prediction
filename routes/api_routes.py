from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import numpy as np

from utils.db import get_db
from utils.decorators import role_required, student_ownership_required
from utils.grade_calculator import compute_cumulative_cgpa, compute_attendance_shortfall
from utils.what_if_solver import solve_what_if_target
from ml_engine.inference import predict_student_analytics
from ml_engine.train_models import retrain_all_models

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/student/<student_prn>/academic-summary", methods=["GET"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def get_academic_summary(student_prn):
    """
    Get Student Academic Summary & Historical Trends
    ---
    tags:
      - Student Analytics
    parameters:
      - name: student_prn
        in: path
        type: string
        required: true
        description: Student PRN / Roll number
    responses:
      200:
        description: Academic records and calculated metrics
      404:
        description: Student not found
    """
    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        return jsonify({"error": "Student not found"}), 404

    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(records)

    for r in records:
        r.pop("_id", None)

    return jsonify({
        "student_prn": student_prn,
        "name": user.get("name"),
        "branch": user.get("branch"),
        "cumulative_cgpa": cgpa,
        "total_credits_earned": total_credits,
        "active_backlogs": total_backlogs,
        "completed_semesters": len(records),
        "records": records
    }), 200


@api_bp.route("/student/<student_prn>/prediction", methods=["GET"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def get_student_prediction(student_prn):
    """
    Get ML Forecasting, Detention Classification & Explainability Insights
    ---
    tags:
      - Predictive Analytics
    parameters:
      - name: student_prn
        in: path
        type: string
        required: true
        description: Student PRN / Roll number
    responses:
      200:
        description: ML prediction result and action points
    """
    force = request.args.get("force", "false").lower() == "true"
    result = predict_student_analytics(student_prn, force_recalculate=force)
    return jsonify(result), 200


@api_bp.route("/student/<student_prn>/what-if", methods=["POST"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def calculate_what_if(student_prn):
    """
    Prescriptive Goal Engine Solver
    ---
    tags:
      - Prescriptive Analytics
    parameters:
      - name: student_prn
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            target_cgpa:
              type: number
              example: 8.5
            subjects:
              type: array
              items:
                type: object
    responses:
      200:
        description: Required exam score breakdown
    """
    data = request.get_json() or {}
    target_cgpa = float(data.get("target_cgpa", 8.5))
    
    db = get_db()
    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))
    current_cgpa, _, total_credits = compute_cumulative_cgpa(records)

    subjects = data.get("subjects")
    if not subjects and records:
        latest = records[-1]
        subjects = latest.get("subjects", [])

    if not subjects:
        subjects = [
            {"subject_code": "CS101", "subject_name": "Data Structures", "credits": 4, "tt1_score": 15.0, "tt2_score": 15.0, "max_ese": 80.0},
            {"subject_code": "CS102", "subject_name": "Operating Systems", "credits": 4, "tt1_score": 16.0, "tt2_score": 14.0, "max_ese": 80.0}
        ]

    sem_credits = sum(int(s.get("credits", 4)) for s in subjects)

    analysis = solve_what_if_target(
        target_cgpa=target_cgpa,
        current_cgpa=current_cgpa,
        completed_credits=total_credits,
        current_sem_credits=sem_credits,
        subjects=subjects
    )
    return jsonify(analysis), 200


@api_bp.route("/admin/branch-analytics", methods=["GET"])
@role_required(["admin"])
def get_branch_analytics():
    """
    Institute & Branch Analytics for Heatmaps and Distributions
    ---
    tags:
      - Admin Analytics
    responses:
      200:
        description: Aggregated grade and attendance distributions
    """
    db = get_db()
    students = list(db.users.find({"role": "student"}))

    branch_data = {}
    for s in students:
        branch = s.get("branch", "Other")
        prn = s.get("prn_roll")
        recs = list(db.academic_records.find({"student_prn": prn}))
        cgpa, backlogs, _ = compute_cumulative_cgpa(recs)
        att = np.mean([float(r.get("attendance_percentage", 80.0)) for r in recs]) if recs else 80.0

        if branch not in branch_data:
            branch_data[branch] = {"cgpas": [], "attendances": [], "backlogs_count": 0, "students_count": 0}

        branch_data[branch]["cgpas"].append(cgpa)
        branch_data[branch]["attendances"].append(att)
        branch_data[branch]["backlogs_count"] += backlogs
        branch_data[branch]["students_count"] += 1

    summary = {}
    for b, d in branch_data.items():
        summary[b] = {
            "total_students": d["students_count"],
            "avg_cgpa": round(float(np.mean(d["cgpas"])), 2) if d["cgpas"] else 0.0,
            "avg_attendance": round(float(np.mean(d["attendances"])), 1) if d["attendances"] else 0.0,
            "total_backlogs": d["backlogs_count"],
            "cgpa_distribution": {
                "distinction_9_plus": sum(1 for c in d["cgpas"] if c >= 9.0),
                "first_class_7_5_to_9": sum(1 for c in d["cgpas"] if 7.5 <= c < 9.0),
                "second_class_6_to_7_5": sum(1 for c in d["cgpas"] if 6.0 <= c < 7.5),
                "pass_class_4_to_6": sum(1 for c in d["cgpas"] if 4.0 <= c < 6.0),
                "fail_below_4": sum(1 for c in d["cgpas"] if c < 4.0),
            }
        }

    return jsonify({"branches": summary}), 200


@api_bp.route("/admin/detention-list", methods=["GET"])
@role_required(["admin"])
def get_detention_list():
    """
    Get Detention Alert List (<75% attendance)
    ---
    tags:
      - Admin Analytics
    responses:
      200:
        description: List of all students with critical attendance shortfall
    """
    db = get_db()
    risk_records = list(db.academic_records.find({"attendance_percentage": {"$lt": 75.0}}))

    alert_list = []
    seen = set()
    for rec in risk_records:
        prn = rec.get("student_prn")
        if prn in seen:
            continue
        seen.add(prn)
        user = db.users.find_one({"prn_roll": prn}) or {}
        att = float(rec.get("attendance_percentage", 0.0))
        shortfall = compute_attendance_shortfall(int(att), 100, target_pct=75.0)

        alert_list.append({
            "student_prn": prn,
            "name": user.get("name", prn),
            "branch": user.get("branch", ""),
            "semester": rec.get("semester"),
            "attendance_percentage": att,
            "lectures_needed": shortfall.get("lectures_needed", 0),
            "alert_status": "CRITICAL SHORTFALL"
        })

    return jsonify({"detention_alerts": alert_list, "total_at_risk": len(alert_list)}), 200


@api_bp.route("/student/<student_prn>/placement-eligibility", methods=["GET"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def get_placement_eligibility(student_prn):
    """
    Get Student Campus Placement Company Eligibility & Target Simulator
    ---
    tags:
      - Placement & Employability
    parameters:
      - name: student_prn
        in: path
        type: string
        required: true
        description: Student PRN / Roll number
    responses:
      200:
        description: Company eligibility analysis and dream target solver
      404:
        description: Student not found
    """
    from utils.placement_eligibility import evaluate_company_eligibility

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        return jsonify({"error": "Student not found"}), 404

    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(records)

    analysis = evaluate_company_eligibility(
        student_cgpa=cgpa,
        total_backlogs=total_backlogs,
        branch=user.get("branch", "CSE"),
        completed_credits=total_credits,
        current_sem_credits=20,
        db=db
    )

    return jsonify(analysis), 200

