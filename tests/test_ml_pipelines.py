import pytest
import pandas as pd
import numpy as np

from ml_engine.preprocessor import get_student_sgpa_features, get_group_kfold_splits
from ml_engine.inference import predict_student_analytics
from ml_engine.explainability import generate_sgpa_recommendations, generate_placement_recommendations
from utils.db import get_db


def test_cold_start_feature_extraction():
    """Verify semester 1 students receive provisional features without error."""
    features = get_student_sgpa_features(
        student_prn="2024CS001",
        completed_records=[],
        current_tt1_avg=16.0,
        current_tt2_avg=15.0,
        current_attendance=82.0,
        branch="CSE-DS",
        current_semester=1
    )
    assert features["is_cold_start"] is True
    assert "Provisional" in features["confidence_label"]
    assert features["current_tt_avg"] == 15.5
    assert features["attendance_percentage"] == 82.0


def test_historical_student_feature_extraction():
    """Verify multi-semester students compute correct trend slope and previous SGPAs."""
    history = [
        {"semester": 1, "sgpa": 7.0, "active_backlogs": 0},
        {"semester": 2, "sgpa": 8.0, "active_backlogs": 0},
        {"semester": 3, "sgpa": 9.0, "active_backlogs": 0},
    ]
    features = get_student_sgpa_features(
        student_prn="2022CS001",
        completed_records=history,
        current_tt1_avg=18.0,
        current_tt2_avg=17.0,
        current_attendance=88.0,
        branch="CSE",
        current_semester=4
    )
    assert features["is_cold_start"] is False
    assert features["sgpa_prev1"] == 9.0
    assert features["sgpa_prev2"] == 8.0
    assert features["sgpa_prev3"] == 7.0
    assert features["sgpa_mean"] == 8.0
    assert features["sgpa_trend_slope"] > 0.0  # Positive upward trajectory


def test_group_kfold_no_student_leakage():
    """Verify GroupKFold ensures same student is never in both train and test folds."""
    df = pd.DataFrame({
        "student_prn": ["S1", "S1", "S1", "S2", "S2", "S3", "S3", "S4", "S4", "S5"],
        "sgpa_prev1": [7.0, 7.5, 8.0, 8.0, 8.5, 6.5, 7.0, 9.0, 9.2, 7.8],
        "target_next_sgpa": [7.5, 8.0, 8.5, 8.5, 8.8, 7.0, 7.2, 9.2, 9.5, 8.0]
    })
    splits = get_group_kfold_splits(df, group_col="student_prn", n_splits=3)
    for train_idx, test_idx in splits:
        train_students = set(df.iloc[train_idx]["student_prn"])
        test_students = set(df.iloc[test_idx]["student_prn"])
        # Intersection must be completely empty!
        assert len(train_students.intersection(test_students)) == 0


def test_explainability_recommendations():
    """Verify explainability converts features to clear student recommendations."""
    low_att_feats = {
        "attendance_percentage": 68.0,
        "current_tt_avg": 17.0,
        "sgpa_trend_slope": 0.2,
        "active_backlogs": 1,
        "is_cold_start": False
    }
    recs = generate_sgpa_recommendations(low_att_feats, predicted_sgpa=7.2)
    assert any("Attendance" in r and "drag" in r for r in recs)
    assert any("backlog" in r.lower() for r in recs)
