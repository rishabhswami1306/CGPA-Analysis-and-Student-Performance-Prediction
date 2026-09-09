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

    # Check cache unless recalculation is forced
    if not force_recalculate:
        cached_val = cache.get(cache_key)
        if cached_val:
            try:
                if isinstance(cached_val, bytes):
                    cached_val = cached_val.decode('utf-8')
                return json.loads(cached_val)
            except Exception:
                pass

        # Check MongoDB predictions_cache
        db_cached = db.predictions_cache.find_one({"student_prn": student_prn})
        if db_cached and not force_recalculate:
            db_cached.pop("_id", None)
            return db_cached

    # 1. Fetch Student User Profile and Academic History
    user = db.users.find_one({"prn_roll": student_prn}) or {}
    branch = user.get("branch", "CSE")
    acad_records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))

    # Determine latest completed semester or current semester
    completed_semesters = len(acad_records)
    current_semester = completed_semesters + 1 if completed_semesters < 8 else 8

    # Derive default TT scores and attendance if not supplied
    if acad_records and (current_tt1_avg is None or current_tt2_avg is None or current_attendance is None):
        latest_rec = acad_records[-1]
        subjects = latest_rec.get("subjects", [])
        tt1_vals = [float(s.get("tt1_score", 15.0)) for s in subjects]
        tt2_vals = [float(s.get("tt2_score", 15.0)) for s in subjects]
        if current_tt1_avg is None:
            current_tt1_avg = float(np.mean(tt1_vals)) if tt1_vals else 15.0
        if current_tt2_avg is None:
            current_tt2_avg = float(np.mean(tt2_vals)) if tt2_vals else 15.0
        if current_attendance is None:
            current_attendance = float(latest_rec.get("attendance_percentage", 82.0))
    else:
        current_tt1_avg = current_tt1_avg if current_tt1_avg is not None else 15.0
        current_tt2_avg = current_tt2_avg if current_tt2_avg is not None else 15.0
        current_attendance = current_attendance if current_attendance is not None else 82.0

    # 2. Extract ML Feature Vector
    features = get_student_sgpa_features(
        student_prn=student_prn,
        completed_records=acad_records,
        current_tt1_avg=current_tt1_avg,
        current_tt2_avg=current_tt2_avg,
        current_attendance=current_attendance,
        branch=branch,
        current_semester=current_semester
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
    cgpa, total_backlogs, earned_credits = compute_cumulative_cgpa(acad_records)
    if cgpa == 0.0:
        cgpa = pred_sgpa

    # Core tech score
    tech_scores = []
    for r in acad_records:
        for s in r.get("subjects", []):
            tech_scores.append(float(s.get("total_marks", 65.0)))
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

    # 7. Compile Final Payload
    result = {
        "student_prn": student_prn,
        "predicted_next_sgpa": pred_sgpa,
        "current_cgpa": cgpa,
        "detention_risk": detention_risk,
        "attendance_percentage": current_attendance,
        "shortfall_analysis": shortfall_info,
        "placement_readiness_score": readiness_percentage,
        "placement_tier": placement_tier,
        "improvement_recommendations": all_recommendations,
        "model_version": model_version,
        "computed_from_semester": completed_semesters,
        "is_cold_start": features.get("is_cold_start", False),
        "confidence_label": features.get("confidence_label", "Provisional"),
        "last_calculated_at": datetime.now(timezone.utc).isoformat()
    }

    # 8. Save to DB and Cache
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
