import pytest
from ml_engine.subject_risk import compute_subject_risk_profile, analyze_all_enrolled_subjects
from ml_engine.counterfactuals import generate_counterfactual_pathways
from ml_engine.early_warning import evaluate_early_warning_system
from ml_engine.knowledge_graph import analyze_prerequisite_knowledge_graph
from ml_engine.persona_engine import classify_student_persona
from ml_engine.career_pathways import evaluate_multi_pathway_careers
from ml_engine.inference import predict_student_analytics
from utils.db import get_db


# --- 1. Subject-Level Backlog & Grade Risk Predictor Tests ---
def test_subject_risk_profile_safe():
    subject = {
        "subject_code": "DAA",
        "subject_name": "Design & Analysis of Algorithms",
        "credits": 4,
        "internal_score": 32.0,
        "tt1_score": 18.0,
        "tt2_score": 17.0
    }
    profile = compute_subject_risk_profile(subject, student_attendance=85.0)
    assert profile["risk_level"] == "SAFE"
    assert profile["backlog_probability"] < 0.25
    assert profile["min_ese_to_pass"] == 24.0
    assert profile["projected_grade"] in ["O", "A+", "A", "B+"]


def test_subject_risk_profile_critical_kt():
    subject = {
        "subject_code": "ML-II",
        "subject_name": "Machine Learning-II",
        "credits": 4,
        "internal_score": 10.0,
        "tt1_score": 6.0,
        "tt2_score": 6.0
    }
    profile = compute_subject_risk_profile(subject, student_attendance=62.0)
    assert profile["risk_level"] == "CRITICAL_KT_RISK"
    assert profile["min_ese_to_pass"] >= 30.0
    assert profile["backlog_probability"] >= 0.40


def test_analyze_all_enrolled_subjects():
    subjects = [
        {"subject_code": "DAA", "internal_score": 30.0},
        {"subject_code": "ML-II", "internal_score": 8.0}
    ]
    summary = analyze_all_enrolled_subjects(subjects, student_attendance=70.0)
    assert summary["total_subjects"] == 2
    assert summary["critical_backlog_count"] >= 1
    assert summary["overall_subject_health"] in ["CRITICAL", "WARNING"]


# --- 2. Probabilistic Forecasting & Confidence Interval Tests ---
def test_probabilistic_inference_bounds(app):
    with app.app_context():
        db = get_db()
        # Clean up any existing test records to ensure idempotency
        db.users.delete_many({"prn_roll": "STU_PROB_01"})
        db.academic_records.delete_many({"student_prn": "STU_PROB_01"})
        db.predictions_cache.delete_many({"student_prn": "STU_PROB_01"})

        # Insert a sample student in mock db
        db.users.insert_one({
            "prn_roll": "STU_PROB_01",
            "email": "stu_prob_01@test.edu",
            "role": "student",
            "branch": "CSE-DS"
        })
        db.academic_records.insert_many([
            {"student_prn": "STU_PROB_01", "semester": 1, "sgpa": 8.2, "is_completed": True, "attendance_percentage": 85.0},
            {"student_prn": "STU_PROB_01", "semester": 2, "sgpa": 8.5, "is_completed": True, "attendance_percentage": 88.0},
            {"student_prn": "STU_PROB_01", "semester": 3, "sgpa": 8.4, "is_completed": True, "attendance_percentage": 86.0},
            {"student_prn": "STU_PROB_01", "semester": 4, "sgpa": 8.6, "is_completed": True, "attendance_percentage": 87.0},
            {"student_prn": "STU_PROB_01", "semester": 5, "is_completed": False, "attendance_percentage": 85.0, "subjects": [
                {"subject_code": "DAA", "tt1_score": 17.0, "tt2_score": 17.0, "internal_score": 32.0}
            ]}
        ])

        result = predict_student_analytics("STU_PROB_01", force_recalculate=True)
        assert "predicted_sgpa_min" in result
        assert "predicted_sgpa_max" in result
        assert "margin_of_error" in result
        assert result["predicted_sgpa_min"] <= result["predicted_next_sgpa"] <= result["predicted_sgpa_max"]
        assert result["confidence_interval_pct"] == 90
        assert "scenarios" in result or "scenario_projections" in result


# --- 3. Prescriptive Counterfactual Pathways Tests ---
def test_counterfactual_pathways_generation():
    cf = generate_counterfactual_pathways(
        current_cgpa=7.2,
        completed_credits=80,
        ongoing_credits=20,
        current_tt1_avg=14.0,
        current_tt2_avg=13.0,
        current_attendance=78.0,
        target_sgpa=8.5
    )
    assert len(cf["pathways"]) == 3
    titles = [p["title"] for p in cf["pathways"]]
    assert any("Balanced" in t for t in titles)
    assert any("Exam" in t for t in titles)
    assert any("Attendance Cushion" in t for t in titles)
    for p in cf["pathways"]:
        assert 0 <= p["feasibility_score"] <= 100
        assert len(p["actions"]) >= 3


# --- 4. Dynamic Early Warning System (EWS) Tests ---
def test_early_warning_system_accelerating():
    ews = evaluate_early_warning_system(
        current_attendance=88.0,
        current_tt1_avg=18.5,
        current_tt2_avg=19.0,
        sgpa_mean=7.5,
        sgpa_trend_slope=0.35,
        active_backlogs=0
    )
    assert ews["trajectory_status"] == "ACCELERATING"
    assert ews["days_to_ese"] > 0
    assert ews["max_possible_sgpa"] >= 9.0


def test_early_warning_system_critical():
    ews = evaluate_early_warning_system(
        current_attendance=64.0,
        current_tt1_avg=8.0,
        current_tt2_avg=9.0,
        sgpa_mean=6.5,
        sgpa_trend_slope=-0.4,
        active_backlogs=2
    )
    assert ews["trajectory_status"] == "CRITICAL_DEFICIT"
    assert len(ews["intervention_checklist"]) >= 2


# --- 5. Prerequisite Knowledge-Graph Analysis Tests ---
def test_knowledge_graph_vulnerability_detection():
    # Student struggled in Data Structures in Sem 2
    history = [
        {"semester": 2, "subjects": [{"subject_code": "CS201", "subject_name": "Data Structures", "grade_point": 5.0, "total_marks": 45.0}]}
    ]
    # Enrolled in DAA in active semester
    active = [{"subject_code": "DAA", "subject_name": "Design & Analysis of Algorithms"}]
    kg = analyze_prerequisite_knowledge_graph(history, active)
    assert kg["has_vulnerabilities"] is True
    assert kg["vulnerable_count"] >= 1
    assert any(b["target_prerequisite"] == "Data Structures" for b in kg["recommended_bridge_modules"])


def test_knowledge_graph_robust_mastery():
    history = [
        {"semester": 2, "subjects": [{"subject_code": "CS201", "subject_name": "Data Structures", "grade_point": 9.0, "total_marks": 78.0}]},
        {"semester": 1, "subjects": [{"subject_code": "CS101", "subject_name": "Programming in C", "grade_point": 9.0, "total_marks": 80.0}]}
    ]
    active = [{"subject_code": "DAA", "subject_name": "Design & Analysis of Algorithms"}]
    kg = analyze_prerequisite_knowledge_graph(history, active)
    assert kg["has_vulnerabilities"] is False


# --- 6. Unsupervised Student Persona Archetype Tests ---
def test_persona_classification_consistent_achiever():
    persona = classify_student_persona(
        attendance_pct=90.0,
        current_tt_avg=18.0,
        sgpa_mean=8.8,
        sgpa_trend_slope=0.2,
        active_backlogs=0
    )
    assert persona["archetype_code"] == "CONSISTENT_ACHIEVER"
    assert persona["radar_traits"]["discipline_attendance"] == 90.0
    assert persona["radar_traits"]["internal_mastery"] == 90.0


def test_persona_classification_vulnerable_slider():
    persona = classify_student_persona(
        attendance_pct=72.0,
        current_tt_avg=11.0,
        sgpa_mean=6.8,
        sgpa_trend_slope=-0.35,
        active_backlogs=1
    )
    assert persona["archetype_code"] == "VULNERABLE_SLIDER"
    assert "backlog" in persona["tailored_strategy"].lower() or "mentor" in persona["tailored_strategy"].lower()


# --- 7. Multi-Pathway Career Predictor Tests ---
def test_career_pathways_evaluation():
    history = [
        {"semester": 1, "subjects": [{"subject_code": "CS101", "total_marks": 82.0}, {"subject_code": "M1", "total_marks": 85.0}]},
        {"semester": 2, "subjects": [{"subject_code": "CS201", "total_marks": 88.0}, {"subject_code": "M2", "total_marks": 80.0}]}
    ]
    active = [
        {"subject_code": "DAA", "total_marks": 85.0, "presentation_score": 8.5, "aptitude_score": 8.0}
    ]
    careers = evaluate_multi_pathway_careers(
        cgpa=8.6,
        active_backlogs=0,
        attendance_pct=88.0,
        completed_records=history,
        ongoing_subjects=active
    )
    assert len(careers["tracks"]) == 4
    track_ids = [t["id"] for t in careers["tracks"]]
    assert set(track_ids) == {"swe", "ms", "gate", "mba"}
    assert careers["primary_fit_pct"] >= 70.0


# --- 8. Faculty Early-Intervention Quadrant & Action Tests ---
def test_faculty_intervention_dispatch(client, auth_headers):
    # Faculty FAC001 submits intervention
    fac_headers = auth_headers(prn_roll="FAC001", role="faculty", email="faculty@test.edu")

    # Dispatch intervention via API
    res = client.post("/faculty/intervene", headers=fac_headers, json={
        "student_prn": "2022CS001",
        "intervention_type": "remedial_packet",
        "subject_code": "DAA",
        "notes": "Remedial algorithms problem set dispatched."
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["student_prn"] == "2022CS001"
    assert data["data"]["status"] == "DISPATCHED"
