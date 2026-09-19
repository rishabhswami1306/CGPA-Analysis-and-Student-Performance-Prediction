import pytest
from utils.placement_eligibility import (
    solve_dream_target_sgpa,
    evaluate_company_eligibility,
    DEFAULT_COMPANIES
)


def test_solve_dream_target_sgpa():
    # Student has 8.0 CGPA over 60 credits. Wants 8.5 CGPA with 20 credits next sem.
    # Points after: 8.5 * 80 = 680
    # Current points: 8.0 * 60 = 480
    # Required next sem: (680 - 480) / 20 = 200 / 20 = 10.0
    res = solve_dream_target_sgpa(current_cgpa=8.0, completed_credits=60, target_cgpa=8.5, next_sem_credits=20)
    assert res["required_sgpa"] == 10.0
    assert res["is_achievable_next_sem"] is True
    assert res["cgpa_gap"] == 0.5


def test_evaluate_company_eligibility():
    # Perfect candidate: 9.2 CGPA, 0 backlogs, CSE
    analysis = evaluate_company_eligibility(
        student_cgpa=9.2,
        total_backlogs=0,
        branch="CSE",
        completed_credits=60,
        current_sem_credits=20
    )
    assert analysis["eligible_count"] > 0
    assert analysis["highest_eligible_package"] >= 20.0
    
    # Candidate with backlogs: restricted from Tier 1 companies requiring 0 backlogs
    backlog_analysis = evaluate_company_eligibility(
        student_cgpa=9.2,
        total_backlogs=2,
        branch="CSE",
        completed_credits=60,
        current_sem_credits=20
    )
    # Tier-1 companies like Google (max 0 backlogs) should be ineligible
    google_comp = next((c for c in backlog_analysis["companies"] if c["company_id"] == "google"), None)
    assert google_comp is not None
    assert google_comp["is_eligible"] is False


def test_evaluate_company_multi_criteria():
    # Verify catalog expansion
    assert len(DEFAULT_COMPANIES) >= 28

    # Candidate with low attendance (65%) should fail attendance criteria
    low_att_analysis = evaluate_company_eligibility(
        student_cgpa=9.5,
        total_backlogs=0,
        branch="CSE",
        completed_credits=60,
        current_sem_credits=20,
        student_attendance=65.0,  # Below 75%
        student_placement_score=85.0
    )
    # Even with 9.5 CGPA, candidate should fail attendance threshold for standard drives
    ineligible_due_to_att = [c for c in low_att_analysis["companies"] if c["status_tag"] == "ATTENDANCE_SHORTFALL"]
    assert len(ineligible_due_to_att) > 0

    # Verify newly added companies exist with required criteria attributes
    company_ids = [c["company_id"] for c in DEFAULT_COMPANIES]
    assert "nvidia" in company_ids
    assert "apple" in company_ids
    assert "de_shaw" in company_ids
    assert "walmart" in company_ids
    assert "zomato" in company_ids
    assert "persistent" in company_ids

    apple_comp = next(c for c in DEFAULT_COMPANIES if c["company_id"] == "apple")
    assert apple_comp["hiring_category"] == "Super Dream"
    assert "min_attendance" in apple_comp
    assert "interview_rounds" in apple_comp
    assert "service_bond_months" in apple_comp

