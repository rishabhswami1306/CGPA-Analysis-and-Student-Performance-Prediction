import pytest
from utils.grade_calculator import (
    calculate_grade_point,
    compute_subject_total,
    compute_semester_sgpa,
    compute_cumulative_cgpa,
    compute_attendance_shortfall
)
from utils.what_if_solver import solve_what_if_target


def test_grade_point_thresholds():
    """Verify deterministic grade point mapping matches official institute thresholds."""
    assert calculate_grade_point(85.0) == (10.0, "O")
    assert calculate_grade_point(80.0) == (10.0, "O")
    assert calculate_grade_point(79.9) == (9.0, "A+")
    assert calculate_grade_point(75.0) == (9.0, "A+")
    assert calculate_grade_point(74.0) == (8.0, "A")
    assert calculate_grade_point(70.0) == (8.0, "A")
    assert calculate_grade_point(65.0) == (7.0, "B+")
    assert calculate_grade_point(55.0) == (6.0, "B")
    assert calculate_grade_point(47.0) == (5.0, "C")
    assert calculate_grade_point(40.0) == (4.0, "P")
    assert calculate_grade_point(39.9) == (0.0, "F")
    assert calculate_grade_point(0.0) == (0.0, "F")


def test_subject_total_calculation():
    """Verify (TT1 + TT2)/2 + ESE formula."""
    # TT1 = 18/20, TT2 = 16/20 -> avg = 17. ESE = 70/80 -> total = 87
    total = compute_subject_total(18.0, 16.0, 70.0)
    assert total == 87.0

    # Scaled ESE from 100 max_ese to 80
    total_scaled = compute_subject_total(20.0, 20.0, 80.0, max_ese=100.0)
    # avg = 20, scaled ESE = (80/100)*80 = 64 -> total = 84.0
    assert total_scaled == 84.0


def test_semester_sgpa_calculation():
    """Verify credit-weighted SGPA calculation."""
    subjects = [
        {"subject_code": "CS1", "credits": 4, "grade_point": 10.0}, # 40
        {"subject_code": "CS2", "credits": 4, "grade_point": 8.0},  # 32
        {"subject_code": "CS3", "credits": 3, "grade_point": 9.0},  # 27
        {"subject_code": "CS4", "credits": 3, "grade_point": 7.0},  # 21
        {"subject_code": "CS5", "credits": 2, "grade_point": 0.0},  # 0 (Backlog)
    ]
    # Total credit points = 40 + 32 + 27 + 21 + 0 = 120
    # Total credits = 4 + 4 + 3 + 3 + 2 = 16
    # SGPA = 120 / 16 = 7.50, backlogs = 1
    sgpa, backlogs, total_credits = compute_semester_sgpa(subjects)
    assert sgpa == 7.50
    assert backlogs == 1
    assert total_credits == 16


def test_cumulative_cgpa_calculation():
    """Verify multi-semester cumulative CGPA calculation."""
    records = [
        {"semester": 1, "sgpa": 8.0, "subjects": [{"credits": 20}], "active_backlogs": 0},
        {"semester": 2, "sgpa": 9.0, "subjects": [{"credits": 20}], "active_backlogs": 0},
        {"semester": 3, "sgpa": 7.0, "subjects": [{"credits": 20}], "active_backlogs": 1},
    ]
    # Total credit points = 8*20 + 9*20 + 7*20 = 480
    # Total credits = 60
    # CGPA = 480 / 60 = 8.00, total backlogs = 1
    cgpa, backlogs, credits = compute_cumulative_cgpa(records)
    assert cgpa == 8.00
    assert backlogs == 1
    assert credits == 60


def test_attendance_shortfall_algebra():
    """Verify exact deterministic shortfall calculation."""
    # Case 1: Attendance at 60% (60 attended out of 100). Needs >= 75%
    # (60 + x) / (100 + x) >= 0.75 => x >= (75*100 - 100*60) / 25 = 1500 / 25 = 60 lectures
    res = compute_attendance_shortfall(attended_lectures=60, total_lectures=100, target_pct=75.0)
    assert res["is_at_risk"] is True
    assert res["current_percentage"] == 60.0
    assert res["lectures_needed"] == 60

    # Case 2: Attendance safe at 85% (85 attended out of 100)
    # (85) / (100 + m) >= 0.75 => 100 + m <= 85 / 0.75 = 113.33 => m <= 13 missable lectures
    safe_res = compute_attendance_shortfall(attended_lectures=85, total_lectures=100, target_pct=75.0)
    assert safe_res["is_at_risk"] is False
    assert safe_res["current_percentage"] == 85.0
    assert safe_res["can_miss_lectures"] == 13


def test_what_if_goal_solver():
    """Verify prescriptive What-If goal algebra."""
    # Student has completed 20 credits with 8.0 CGPA
    # Wants target CGPA of 8.5 after current semester (20 credits)
    # Needed total grade points = 8.5 * 40 = 340
    # Points so far = 8.0 * 20 = 160
    # Current semester points needed = 340 - 160 = 180
    # Required SGPA = 180 / 20 = 9.00
    subjects = [
        {"subject_code": "CS101", "subject_name": "Algo", "credits": 4, "tt1_score": 18.0, "tt2_score": 18.0, "max_ese": 80.0}
    ]
    sol = solve_what_if_target(
        target_cgpa=8.5,
        current_cgpa=8.0,
        completed_credits=20,
        current_sem_credits=20,
        subjects=subjects
    )
    assert sol["is_achievable"] is True
    assert sol["required_sgpa"] == 9.00
