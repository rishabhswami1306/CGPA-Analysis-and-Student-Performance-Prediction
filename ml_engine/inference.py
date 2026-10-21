import os
import json
import logging
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from utils.db import get_db, get_cache
from utils.grade_calculator import compute_attendance_shortfall, compute_cumulative_cgpa
from ml_engine.preprocessor import get_student_sgpa_features
from ml_engine.explainability import generate_sgpa_recommendations, generate_placement_recommendations
from ml_engine.model_registry import load_model_bundle
from ml_engine.subject_risk import analyze_all_enrolled_subjects
from ml_engine.counterfactuals import generate_counterfactual_pathways
from ml_engine.early_warning import evaluate_early_warning_system
from ml_engine.knowledge_graph import analyze_prerequisite_knowledge_graph
from ml_engine.persona_engine import classify_student_persona
from ml_engine.career_pathways import evaluate_multi_pathway_careers

logger = logging.getLogger(__name__)


def predict_student_analytics(
    student_prn: str,
    current_tt1_avg: float = None,
    current_tt2_avg: float = None,
    current_attendance: float = None,
    force_recalculate: bool = False
) -> dict:
    """
    Computes real-time ML predictions, explainability insights, and deterministic metrics.
    Caches results in predictions_cache and Redis.
    """
    db = get_db()
    cache = get_cache()
    cache_key = f"prediction:{student_prn}"

    def _is_valid_cache_entry(entry):
        if not isinstance(entry, dict):
            return False
        required_keys = (
            "predicted_next_sgpa",
            "scenario_projections",
            "early_warning_system",
            "subject_risk_analysis",
            "persona_archetype",
            "knowledge_graph_analysis",
            "counterfactual_pathways",
            "multi_pathway_careers"
        )
        return all(k in entry and entry[k] is not None for k in required_keys)

    # Check cache unless recalculation is forced
    if not force_recalculate:
        cached_val = cache.get(cache_key)
        if cached_val:
            try:
                if isinstance(cached_val, bytes):
                    cached_val = cached_val.decode('utf-8')
                parsed = json.loads(cached_val)
                if _is_valid_cache_entry(parsed):
                    return parsed
            except Exception:
                pass

        # Check MongoDB predictions_cache
        db_cached = db.predictions_cache.find_one({"student_prn": student_prn})
        if db_cached and not force_recalculate:
            db_cached.pop("_id", None)
            if _is_valid_cache_entry(db_cached):
                return db_cached

    # 1. Fetch Student User Profile and Academic History
    user = db.users.find_one({"prn_roll": student_prn}) or {}
    branch = user.get("branch", "CSE-DS")
    acad_records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))

    # Completed records have is_completed: True and non-None sgpa (Semesters 1-4)
    completed_records = [
        r for r in acad_records
        if (r.get("is_completed") is True or r.get("sgpa") is not None or r.get("is_real_marksheet") is True)
    ]
    completed_semesters = len(completed_records)
    if completed_records:
        max_completed_sem = max(int(r.get("semester", 1)) for r in completed_records)
        target_semester = min(8, max_completed_sem + 1)
    else:
        curr_sem = user.get("current_semester")
        target_semester = min(8, max(1, int(curr_sem))) if curr_sem else 1

    ongoing_record = next((r for r in acad_records if r.get("semester") == target_semester), None)

    # Derive 5th semester attendance and Unit Test scores from ongoing records
    att_rec = db.attendance_records.find_one({"student_prn": student_prn})
    if current_attendance is None:
        if att_rec and "percentage" in att_rec:
            current_attendance = float(att_rec["percentage"])
        elif ongoing_record and ongoing_record.get("attendance_percentage") is not None:
            current_attendance = float(ongoing_record["attendance_percentage"])
        elif completed_records:
            current_attendance = float(completed_records[-1].get("attendance_percentage", 80.0))
        else:
            current_attendance = 80.0

    if current_tt1_avg is None or current_tt2_avg is None:
        if ongoing_record:
            sub_list = ongoing_record.get("subjects", [])
            tt1_scores = [float(s.get("tt1_score", 15.0)) for s in sub_list if s.get("tt1_score") is not None]
            tt2_scores = [float(s.get("tt2_score", 15.0)) for s in sub_list if s.get("tt2_score") is not None]
            if current_tt1_avg is None:
                current_tt1_avg = float(np.mean(tt1_scores)) if tt1_scores else 15.0
            if current_tt2_avg is None:
                current_tt2_avg = float(np.mean(tt2_scores)) if tt2_scores else 14.5
        elif completed_records:
            last_subs = completed_records[-1].get("subjects", [])
            tt1_scores = [float(s.get("tt1_score", 15.0)) for s in last_subs]
            tt2_scores = [float(s.get("tt2_score", 15.0)) for s in last_subs]
            if current_tt1_avg is None:
                current_tt1_avg = float(np.mean(tt1_scores)) if tt1_scores else 15.0
            if current_tt2_avg is None:
                current_tt2_avg = float(np.mean(tt2_scores)) if tt2_scores else 14.5
        else:
            current_tt1_avg = 15.0
            current_tt2_avg = 14.5

    # 2. Extract ML Feature Vector (Trained on completed history + ongoing Sem 5 variables)
    features = get_student_sgpa_features(
        student_prn=student_prn,
        completed_records=completed_records,
        current_tt1_avg=current_tt1_avg,
        current_tt2_avg=current_tt2_avg,
        current_attendance=current_attendance,
        branch=branch,
        current_semester=target_semester
    )

    # 3. Pipeline 1: Next-Semester SGPA Regressor
    sgpa_bundle = load_model_bundle("sgpa_regressor")
    if sgpa_bundle and "model" in sgpa_bundle:
        model = sgpa_bundle["model"]
        feat_cols = sgpa_bundle.get("features", [])
        input_df = pd.DataFrame([{col: features.get(col, 0.0) for col in feat_cols}])
        pred_sgpa_raw = float(model.predict(input_df)[0])
        pred_sgpa = min(10.0, max(0.0, round(pred_sgpa_raw, 2)))
        model_version = sgpa_bundle.get("version", "1.0.0")
    else:
        # Robust heuristic fallback
        base = features["sgpa_mean"] if not features["is_cold_start"] else 7.5
        tt_bonus = (features["current_tt_avg"] - 14.0) * 0.15
        att_bonus = (features["attendance_percentage"] - 75.0) * 0.02
        pred_sgpa = min(10.0, max(4.0, round(base + tt_bonus + att_bonus, 2)))
        model_version = "1.0.0-fallback"

    # 4. Pipeline 2: Detention Risk & Shortfall Math
    # Deterministic calculation
    total_lectures = 100
    attended_lectures = int(round((current_attendance / 100.0) * total_lectures))
    shortfall_info = compute_attendance_shortfall(attended_lectures, total_lectures, target_pct=75.0)

    # Risk level categorization
    if current_attendance < 75.0:
        detention_risk = "HIGH"
    elif current_attendance < 80.0:
        detention_risk = "MEDIUM"
    else:
        detention_risk = "LOW"

    # 5. Pipeline 3: Placement Eligibility & Readiness Predictor
    cgpa, total_backlogs, earned_credits = compute_cumulative_cgpa(completed_records)
    if cgpa == 0.0:
        cgpa = pred_sgpa

    # Projected cumulative CGPA after completing upcoming semester with predicted SGPA
    next_sem_credits = 20
    if ongoing_record:
        next_sem_credits = sum(int(s.get("credits", 4)) for s in ongoing_record.get("subjects", [])) or 20
    total_credits_with_next = earned_credits + next_sem_credits
    if total_credits_with_next > 0:
        projected_cgpa = round(((cgpa * earned_credits) + (pred_sgpa * next_sem_credits)) / total_credits_with_next, 2)
    else:
        projected_cgpa = pred_sgpa

    # Core tech score
    tech_scores = []
    for r in completed_records:
        for s in r.get("subjects", []):
            if s.get("total_marks") is not None and s.get("total_marks") > 0:
                tech_scores.append(float(s.get("total_marks")))
    tech_avg = float(np.mean(tech_scores)) if tech_scores else (current_tt1_avg + current_tt2_avg) / 2.0 * 2.5 + 40.0

    place_bundle = load_model_bundle("placement_predictor")
    if place_bundle and "model" in place_bundle:
        p_model = place_bundle["model"]
        p_cols = place_bundle.get("features", ["cgpa", "total_backlogs", "avg_attendance", "core_tech_avg"])
        p_input = pd.DataFrame([{
            "cgpa": cgpa,
            "total_backlogs": total_backlogs,
            "avg_attendance": current_attendance,
            "core_tech_avg": tech_avg
        }])
        try:
            proba = float(p_model.predict_proba(p_input)[0, 1])
        except Exception:
            proba = 0.85 if cgpa >= 7.5 and total_backlogs == 0 else 0.50
    else:
        # Heuristic readiness score
        readiness_raw = (cgpa / 10.0) * 60 + (tech_avg / 100.0) * 30 + (current_attendance / 100.0) * 10 - (total_backlogs * 15)
        proba = min(0.99, max(0.10, readiness_raw / 100.0))

    readiness_percentage = round(proba * 100.0, 1)

    if readiness_percentage >= 80.0 and total_backlogs == 0:
        placement_tier = "Tier 1 — High CTC / Product Core (12+ LPA)"
    elif readiness_percentage >= 60.0 and total_backlogs <= 1:
        placement_tier = "Tier 2 — Premier Tech Solutions (6–12 LPA)"
    else:
        placement_tier = "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)"

    # 6. Explainability & Actionable Recommendations
    sgpa_recs = generate_sgpa_recommendations(features, pred_sgpa)
    place_recs = generate_placement_recommendations(cgpa, total_backlogs, tech_avg, proba, placement_tier)
    all_recommendations = sgpa_recs + place_recs[:2]

    # 7. Advanced Prediction Enhancements
    # A. Probabilistic Forecasting & Confidence Intervals (Uncertainty Quantification)
    sgpas = [float(r.get("sgpa", 7.5)) for r in completed_records if r.get("sgpa") is not None]
    if len(sgpas) >= 2:
        sigma_u = max(0.18, min(0.60, float(np.std(sgpas)) * 0.85))
    elif features.get("is_cold_start", False):
        sigma_u = 0.50
    else:
        sigma_u = 0.32

    if current_attendance < 75.0:
        sigma_u += 0.10

    margin_of_error = round(1.645 * sigma_u, 2)
    pred_sgpa_min = round(max(4.0, pred_sgpa - margin_of_error), 2)
    pred_sgpa_max = round(min(10.0, pred_sgpa + margin_of_error), 2)

    scenarios = {
        "pessimistic": {
            "label": "Pessimistic / Lower Bound",
            "sgpa": pred_sgpa_min,
            "description": "Challenging ESE exam papers or attendance dip"
        },
        "expected": {
            "label": "Expected / Baseline Model",
            "sgpa": pred_sgpa,
            "description": "Baseline regression projection matching historical pace"
        },
        "optimistic": {
            "label": "Optimistic / Upper Bound",
            "sgpa": pred_sgpa_max,
            "description": "Top quartile Unit Test 2 & End-Semester clutch"
        }
    }

    # Extract active ongoing subjects
    active_subs = []
    if ongoing_record and ongoing_record.get("subjects"):
        active_subs = ongoing_record.get("subjects", [])
    elif completed_records and completed_records[-1].get("subjects"):
        active_subs = completed_records[-1].get("subjects", [])

    # Class averages for active courses
    class_averages = {}
    try:
        active_sem_num = ongoing_record.get("semester", target_semester) if ongoing_record else target_semester
        class_records = list(db.academic_records.find({"semester": active_sem_num}))
        for cr in class_records:
            for sub_item in cr.get("subjects", []):
                c_code = sub_item.get("subject_code")
                c_score = float(sub_item.get("total_marks", 0.0) or (sub_item.get("tt1_score", 0.0) * 5.0) or 65.0)
                class_averages.setdefault(c_code, []).append(c_score)
        class_averages = {k: round(float(np.mean(v)), 1) for k, v in class_averages.items()}
    except Exception:
        pass

    # B. Subject-Level Backlog & Grade Risk Predictor
    subject_risk_analysis = analyze_all_enrolled_subjects(active_subs, current_attendance, class_averages)

    # C. Prescriptive Counterfactual Minimal-Effort Pathways
    target_goal_sgpa = min(10.0, max(pred_sgpa + 0.5, 8.5))
    counterfactual_analysis = generate_counterfactual_pathways(
        current_cgpa=cgpa,
        completed_credits=earned_credits,
        ongoing_credits=next_sem_credits,
        current_tt1_avg=current_tt1_avg,
        current_tt2_avg=current_tt2_avg,
        current_attendance=current_attendance,
        target_sgpa=target_goal_sgpa,
        subjects=active_subs
    )

    # D. Dynamic Early Warning System (EWS) & Rescue Window
    early_warning = evaluate_early_warning_system(
        current_attendance=current_attendance,
        current_tt1_avg=current_tt1_avg,
        current_tt2_avg=current_tt2_avg,
        sgpa_mean=features.get("sgpa_mean", 7.5),
        sgpa_trend_slope=features.get("sgpa_trend_slope", 0.0),
        active_backlogs=total_backlogs,
        ongoing_subjects=active_subs,
        current_week=9,
        semester_total_weeks=15
    )

    # E. Prerequisite Knowledge-Graph / Dependency Vulnerability Analysis
    knowledge_graph = analyze_prerequisite_knowledge_graph(
        completed_records=completed_records,
        active_subjects=active_subs
    )

    # F. Unsupervised Student Persona / Archetype Clustering
    persona_analysis = classify_student_persona(
        attendance_pct=current_attendance,
        current_tt_avg=(current_tt1_avg + current_tt2_avg) / 2.0,
        sgpa_mean=features.get("sgpa_mean", 7.5),
        sgpa_trend_slope=features.get("sgpa_trend_slope", 0.0),
        active_backlogs=total_backlogs,
        completed_records=completed_records,
        ongoing_subjects=active_subs
    )

    # G. Multi-Pathway Career Predictor
    career_pathways = evaluate_multi_pathway_careers(
        cgpa=cgpa,
        active_backlogs=total_backlogs,
        attendance_pct=current_attendance,
        completed_records=completed_records,
        ongoing_subjects=active_subs
    )

    # 8. Compile Final Payload
    result = {
        "student_prn": student_prn,
        "target_semester": target_semester,
        "semester_label": f"Semester {target_semester} (Current Ongoing)",
        "predicted_next_sgpa": pred_sgpa,
        "predicted_sgpa_min": pred_sgpa_min,
        "predicted_sgpa_max": pred_sgpa_max,
        "margin_of_error": margin_of_error,
        "confidence_interval_pct": 90,
        "scenario_projections": scenarios,
        "current_cgpa": cgpa,
        "projected_cgpa": projected_cgpa,
        "completed_semesters": completed_semesters,
        "earned_credits": earned_credits,
        "detention_risk": detention_risk,
        "attendance_percentage": current_attendance,
        "shortfall_analysis": shortfall_info,
        "placement_readiness_score": readiness_percentage,
        "placement_tier": placement_tier,
        "improvement_recommendations": all_recommendations,
        "subject_risk_analysis": subject_risk_analysis,
        "counterfactual_pathways": counterfactual_analysis,
        "early_warning_system": early_warning,
        "knowledge_graph_analysis": knowledge_graph,
        "persona_archetype": persona_analysis,
        "multi_pathway_careers": career_pathways,
        "model_version": model_version,
        "computed_from_semester": completed_semesters,
        "is_cold_start": features.get("is_cold_start", False),
        "confidence_label": features.get("confidence_label", "High Confidence — Historical Multi-Semester Model"),
        "last_calculated_at": datetime.now(timezone.utc).isoformat()
    }

    # 9. Save to DB and Cache
    try:
        db.predictions_cache.update_one(
            {"student_prn": student_prn},
            {"$set": result},
            upsert=True
        )
        cache.set(cache_key, json.dumps(result, default=str), ex=3600)
    except Exception as e:
        logger.warning(f"Error saving to predictions cache: {e}")

    return result
