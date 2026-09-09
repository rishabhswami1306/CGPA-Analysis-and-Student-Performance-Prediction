import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from sklearn.model_selection import GroupKFold


# Branch baseline cold-start constants (used when a student has 0 completed semesters)
BRANCH_BASELINES = {
    "CSE-DS": {"avg_sgpa": 7.45, "avg_tt": 15.2, "avg_att": 82.0},
    "CSE": {"avg_sgpa": 7.50, "avg_tt": 15.4, "avg_att": 83.0},
    "IT": {"avg_sgpa": 7.35, "avg_tt": 14.8, "avg_att": 81.0},
    "EXTC": {"avg_sgpa": 7.10, "avg_tt": 14.2, "avg_att": 80.0},
    "AIDS": {"avg_sgpa": 7.40, "avg_tt": 15.0, "avg_att": 82.5},
    "MECH": {"avg_sgpa": 6.95, "avg_tt": 13.8, "avg_att": 79.0},
    "CIVIL": {"avg_sgpa": 6.90, "avg_tt": 13.5, "avg_att": 78.5},
    "DEFAULT": {"avg_sgpa": 7.20, "avg_tt": 14.5, "avg_att": 80.0},
}


def get_student_sgpa_features(
    student_prn: str,
    completed_records: List[Dict[str, Any]],
    current_tt1_avg: float = 15.0,
    current_tt2_avg: float = 15.0,
    current_attendance: float = 80.0,
    branch: str = "DEFAULT",
    current_semester: int = 1
) -> Dict[str, Any]:
    """
    Extracts structured feature vector for next-semester SGPA regression and detention risk.
    Handles cold-start gracefully for semester 1 students.
    """
    branch_key = branch if branch in BRANCH_BASELINES else "DEFAULT"
    baseline = BRANCH_BASELINES[branch_key]

    tt_avg = (current_tt1_avg + current_tt2_avg) / 2.0
    sorted_records = sorted(completed_records, key=lambda x: x.get("semester", 1))

    if not sorted_records:
        # COLD START: 1st semester student
        return {
            "student_prn": student_prn,
            "is_cold_start": True,
            "sgpa_prev1": baseline["avg_sgpa"],
            "sgpa_prev2": baseline["avg_sgpa"],
            "sgpa_prev3": baseline["avg_sgpa"],
            "sgpa_mean": baseline["avg_sgpa"],
            "sgpa_trend_slope": 0.0,
            "current_tt_avg": tt_avg,
            "attendance_percentage": current_attendance,
            "active_backlogs": 0,
            "semester": current_semester,
            "confidence_label": "Provisional — Based on branch baseline & initial Unit Tests"
        }

    sgpas = [float(r.get("sgpa", 7.0)) for r in sorted_records]
    backlogs = sum(int(r.get("active_backlogs", 0)) for r in sorted_records)
    
    sgpa_prev1 = sgpas[-1]
    sgpa_prev2 = sgpas[-2] if len(sgpas) >= 2 else sgpa_prev1
    sgpa_prev3 = sgpas[-3] if len(sgpas) >= 3 else sgpa_prev2
    sgpa_mean = float(np.mean(sgpas))

    # Calculate trend slope over available semesters
    if len(sgpas) >= 2:
        x = np.arange(len(sgpas))
        slope, _ = np.polyfit(x, sgpas, 1)
    else:
        slope = 0.0

    return {
        "student_prn": student_prn,
        "is_cold_start": False,
        "sgpa_prev1": sgpa_prev1,
        "sgpa_prev2": sgpa_prev2,
        "sgpa_prev3": sgpa_prev3,
        "sgpa_mean": sgpa_mean,
        "sgpa_trend_slope": float(round(slope, 3)),
        "current_tt_avg": tt_avg,
        "attendance_percentage": current_attendance,
        "active_backlogs": backlogs,
        "semester": current_semester,
        "confidence_label": "High Confidence — Historical Multi-Semester Model"
    }


def prepare_training_dataset_from_db(db) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Builds tabular DataFrames from academic_records and placement_records in DB.
    Returns (sgpa_df, placement_df).
    """
    # 1. Academic Records
    acad_docs = list(db.academic_records.find({}))
    if not acad_docs:
        return pd.DataFrame(), pd.DataFrame()

    # Group records by student
    student_records = {}
    for doc in acad_docs:
        prn = doc.get("student_prn")
        if prn not in student_records:
            student_records[prn] = []
        student_records[prn].append(doc)

    sgpa_rows = []
    for prn, recs in student_records.items():
        sorted_recs = sorted(recs, key=lambda x: x.get("semester", 1))
        for i in range(len(sorted_recs) - 1):
            history = sorted_recs[:i + 1]
            target_sem_rec = sorted_recs[i + 1]
            
            # Subject average TTs for the target semester
            target_subjects = target_sem_rec.get("subjects", [])
            tt1_vals = [float(s.get("tt1_score", 15.0)) for s in target_subjects]
            tt2_vals = [float(s.get("tt2_score", 15.0)) for s in target_subjects]
            avg_tt1 = np.mean(tt1_vals) if tt1_vals else 15.0
            avg_tt2 = np.mean(tt2_vals) if tt2_vals else 15.0
            att = float(target_sem_rec.get("attendance_percentage", 80.0))

            feats = get_student_sgpa_features(
                student_prn=prn,
                completed_records=history,
                current_tt1_avg=avg_tt1,
                current_tt2_avg=avg_tt2,
                current_attendance=att,
                current_semester=target_sem_rec.get("semester", 2)
            )
            
            # Targets
            feats["target_next_sgpa"] = float(target_sem_rec.get("sgpa", 7.0))
            feats["target_detention_risk"] = 1 if att < 75.0 else 0
            sgpa_rows.append(feats)

    sgpa_df = pd.DataFrame(sgpa_rows)

    # 2. Placement Records
    placement_docs = list(db.placement_records.find({}))
    placement_rows = []
    for doc in placement_docs:
        prn = doc.get("student_prn")
        recs = student_records.get(prn, [])
        if not recs:
            continue
        
        all_sgpas = [float(r.get("sgpa", 0.0)) for r in recs]
        cgpa = float(np.mean(all_sgpas)) if all_sgpas else 7.0
        total_backlogs = sum(int(r.get("active_backlogs", 0)) for r in recs)
        avg_att = float(np.mean([float(r.get("attendance_percentage", 80.0)) for r in recs]))

        # Core technical scores average
        tech_scores = []
        for r in recs:
            for s in r.get("subjects", []):
                tech_scores.append(float(s.get("total_marks", 60.0)))
        tech_avg = float(np.mean(tech_scores)) if tech_scores else 65.0

        placement_rows.append({
            "student_prn": prn,
            "cgpa": cgpa,
            "total_backlogs": total_backlogs,
            "avg_attendance": avg_att,
            "core_tech_avg": tech_avg,
            "placed": 1 if doc.get("placed", False) else 0,
            "package_lpa": float(doc.get("package_lpa", 0.0)) if doc.get("placed", False) else 0.0,
            "placement_tier": doc.get("placement_tier", "Tier 3")
        })

    placement_df = pd.DataFrame(placement_rows)
    return sgpa_df, placement_df


def get_group_kfold_splits(df: pd.DataFrame, group_col: str = "student_prn", n_splits: int = 5):
    """
    Returns train/test indices split using GroupKFold to guarantee zero data leakage across semesters.
    """
    gkf = GroupKFold(n_splits=n_splits)
    groups = df[group_col].values
    X = df.drop(columns=[group_col])
    return gkf.split(X, groups=groups)
