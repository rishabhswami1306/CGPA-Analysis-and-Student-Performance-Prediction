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


@api_bp.route("/analytics/subject-risk/<student_prn>", methods=["GET"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def get_subject_risk_api(student_prn):
    """Subject-level KT/Backlog risk breakdown and required ESE thresholds."""
    pred = predict_student_analytics(student_prn)
    return jsonify({
        "student_prn": student_prn,
        "subject_risk_analysis": pred.get("subject_risk_analysis", {})
    }), 200


@api_bp.route("/analytics/career-pathways/<student_prn>", methods=["GET"])
@role_required(["student", "faculty", "admin"])
@student_ownership_required
def get_career_pathways_api(student_prn):
    """Multi-pathway career readiness scores (SWE, MS, GATE, MBA)."""
    pred = predict_student_analytics(student_prn)
    return jsonify({
        "student_prn": student_prn,
        "multi_pathway_careers": pred.get("multi_pathway_careers", {})
    }), 200


@api_bp.route("/analytics/counterfactual", methods=["POST"])
@role_required(["student", "faculty", "admin"])
def calculate_counterfactual_api():
    """Prescriptive minimal-effort counterfactual solver API."""
    data = request.get_json() or {}
    from ml_engine.counterfactuals import generate_counterfactual_pathways
    
    current_cgpa = float(data.get("current_cgpa", 7.5))
    completed_credits = int(data.get("completed_credits", 80))
    ongoing_credits = int(data.get("ongoing_credits", 20))
    current_tt1_avg = float(data.get("current_tt1_avg", 15.0))
    current_tt2_avg = float(data.get("current_tt2_avg", 15.0))
    current_attendance = float(data.get("current_attendance", 80.0))
    target_sgpa = float(data["target_sgpa"]) if "target_sgpa" in data else None
    target_cgpa = float(data["target_cgpa"]) if "target_cgpa" in data else None

    result = generate_counterfactual_pathways(
        current_cgpa=current_cgpa,
        completed_credits=completed_credits,
        ongoing_credits=ongoing_credits,
        current_tt1_avg=current_tt1_avg,
        current_tt2_avg=current_tt2_avg,
        current_attendance=current_attendance,
        target_sgpa=target_sgpa,
        target_cgpa=target_cgpa
    )
    return jsonify(result), 200


@api_bp.route("/admin/branch-analytics", methods=["GET"])
@role_required(["admin"])
def get_branch_analytics():
    """
    TY CSE-DS Cohort Academic Analytics: Audited Sem 1-4 CGPA vs Ongoing Sem 5 Forecast Distribution
    """
    db = get_db()
    students = list(db.users.find({"role": "student", "branch": "CSE-DS"}))

    sem1_4_cgpas = []
    sem5_preds = []

    for s in students:
        prn = s.get("prn_roll")
        # Completed Sem 1-4 records
        recs = list(db.academic_records.find({
            "student_prn": prn,
            "semester": {"$lte": 4},
            "is_completed": {"$ne": False}
        }))
        cgpa, _, _ = compute_cumulative_cgpa(recs)
        sem1_4_cgpas.append(cgpa)

        # Sem 5 prediction
        pred = predict_student_analytics(prn)
        sem5_preds.append(float(pred.get("predicted_next_sgpa", cgpa)))

    def build_dist(values):
        return {
            "distinction_9_plus": sum(1 for c in values if c >= 9.0),
            "first_class_7_5_to_9": sum(1 for c in values if 7.5 <= c < 9.0),
            "second_class_6_to_7_5": sum(1 for c in values if 6.0 <= c < 7.5),
            "pass_class_4_to_6": sum(1 for c in values if 4.0 <= c < 6.0),
            "fail_below_4": sum(1 for c in values if c < 4.0),
        }

    summary = {
        "Sem 1–4 Audited CGPA": {
            "total_students": len(sem1_4_cgpas),
            "avg_cgpa": round(float(np.mean(sem1_4_cgpas)), 2) if sem1_4_cgpas else 0.0,
            "cgpa_distribution": build_dist(sem1_4_cgpas)
        },
        "Sem 5 ML Forecast": {
            "total_students": len(sem5_preds),
            "avg_cgpa": round(float(np.mean(sem5_preds)), 2) if sem5_preds else 0.0,
            "cgpa_distribution": build_dist(sem5_preds)
        }
    }

    return jsonify({"branches": summary, "cohort": "TY BTech DS (A) 2026-27"}), 200


@api_bp.route("/admin/detention-list", methods=["GET"])
@role_required(["admin"])
def get_detention_list():
    """
    Get Detention Alert List for ongoing Semester 5 (<75% attendance)
    """
    db = get_db()
    # Query from attendance_records (current ongoing Semester 5 attendance register)
    risk_records = list(db.attendance_records.find({"percentage": {"$lt": 75.0}}).sort("percentage", 1))

    alert_list = []
    for rec in risk_records:
        prn = rec.get("student_prn")
        user = db.users.find_one({"prn_roll": prn}) or {}
        att = float(rec.get("percentage", 0.0))
        tot_con = rec.get("total_conducted", 90)
        tot_att = rec.get("total_attended", 60)
        shortfall = compute_attendance_shortfall(tot_att, tot_con, target_pct=75.0)

        alert_list.append({
            "student_prn": prn,
            "name": user.get("name", prn),
            "branch": "CSE-DS",
            "class_name": "TY BTech DS (A)",
            "semester": 5,
            "attendance_percentage": att,
            "lectures_needed": shortfall.get("lectures_needed", 0),
            "local_guardian": rec.get("local_guardian", "Mentor Assigned"),
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

    att_doc = db.attendance_records.find_one({"student_prn": student_prn})
    sem5_rec = next((r for r in records if r.get("semester") == 5), None)
    student_att = float(att_doc.get("percentage") if att_doc else (sem5_rec.get("attendance_percentage", 80.0) if sem5_rec else 80.0))

    try:
        from ml_engine.inference import predict_student_analytics
        pred = predict_student_analytics(student_prn)
        placement_score = float(pred.get("placement_readiness_score", 72.0))
    except Exception:
        placement_score = 72.0

    analysis = evaluate_company_eligibility(
        student_cgpa=cgpa,
        total_backlogs=total_backlogs,
        branch=user.get("branch", "CSE"),
        completed_credits=total_credits,
        current_sem_credits=20,
        student_attendance=student_att,
        student_placement_score=placement_score,
        academic_gap_years=int(user.get("academic_gap_years", 0)),
        tenth_marks=float(user.get("tenth_marks", 82.0)),
        twelfth_marks=float(user.get("twelfth_marks", 80.0)),
        db=db
    )

    return jsonify(analysis), 200

