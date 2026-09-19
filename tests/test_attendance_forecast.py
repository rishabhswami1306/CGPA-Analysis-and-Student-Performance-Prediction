import pytest
from utils.attendance_engine import (
    compute_subject_prediction,
    compute_attendance_predictions,
    simulate_what_if,
    get_semester_milestones,
)

def test_subject_prediction_detained_recovery():
    # 5 attended out of 12 conducted -> 41.67%, target 75%
    # must attend: ceil((75*12 - 100*5)/25) = ceil(400/25) = 16
    pred = compute_subject_prediction(attended=5, conducted=12, remaining=30, target_pct=75.0)
    assert pred["is_detained"] is True
    assert pred["must_attend_now"] == 16
    assert pred["can_miss_now"] == 0
    # verify: (5 + 16) / (12 + 16) = 21 / 28 = 0.75 (75%)
    assert (5 + 16) / (12 + 16) >= 0.75


def test_subject_prediction_safe_buffer():
    # 10 attended out of 10 conducted -> 100%, target 75%
    # can miss: floor((100*10 - 75*10)/75) = floor(250/75) = 3
    pred = compute_subject_prediction(attended=10, conducted=10, remaining=20, target_pct=75.0)
    assert pred["is_detained"] is False
    assert pred["can_miss_now"] == 3
    assert pred["must_attend_now"] == 0
    # verify: 10 / (10 + 3) = 10 / 13 = 76.92% >= 75%
    assert 10 / (10 + 3) >= 0.75
    # 4 missed would drop to 10 / 14 = 71.4% < 75%
    assert 10 / (10 + 4) < 0.75


def test_subject_prediction_zero_conducted():
    pred = compute_subject_prediction(attended=0, conducted=0, remaining=40, target_pct=75.0)
    assert pred["is_detained"] is False
    assert pred["status"] == "Not Started"
    assert pred["max_achievable_pct"] == 100.0


def test_what_if_simulation_math():
    sim = simulate_what_if(
        attended=20,
        conducted=25,
        remaining=30,
        extra_attend=5,
        extra_miss=2,
        target_pct=75.0
    )
    # new attended = 25, new conducted = 32 -> 78.125% -> 78.12%
    assert sim["new_attended"] == 25
    assert sim["new_conducted"] == 32
    assert sim["projected_pct"] == 78.12
    assert sim["is_safe"] is True


def test_semester_milestones():
    milestones = get_semester_milestones()
    assert "progress_pct" in milestones
    assert "milestones" in milestones
    assert len(milestones["milestones"]) > 0
    assert milestones["days_remaining"] >= 0


def test_attendance_routes_integration(client, auth_headers):
    from utils.db import get_db
    db = get_db()
    # Seed test users and attendance records
    db.users.insert_many([
        {"prn_roll": "241106005", "name": "Swami Rishabh", "role": "student", "roll_no": 5, "email": "241106005@rcpit.ac.in"},
        {"prn_roll": "241106010", "name": "Patil Kunal", "role": "student", "roll_no": 9, "email": "241106010@rcpit.ac.in"},
    ])
    db.attendance_records.insert_many([
        {
            "student_prn": "241106005",
            "roll_no": 5,
            "percentage": 85.2,
            "is_detained": False,
            "total_attended": 52,
            "total_conducted": 61,
            "subjects": {
                "ML-II": {"lecture_attended": 10, "lecture_conducted": 12, "practical_attended": 2, "practical_conducted": 2},
                "DAA": {"lecture_attended": 9, "lecture_conducted": 10, "practical_attended": 2, "practical_conducted": 2},
            }
        },
        {
            "student_prn": "241106010",
            "roll_no": 9,
            "percentage": 66.7,
            "is_detained": True,
            "total_attended": 40,
            "total_conducted": 60,
            "subjects": {
                "ML-II": {"lecture_attended": 5, "lecture_conducted": 12, "practical_attended": 1, "practical_conducted": 2},
                "DAA": {"lecture_attended": 6, "lecture_conducted": 10, "practical_attended": 1, "practical_conducted": 2},
            }
        }
    ])

    # 1. Student accesses forecast
    headers_stu = auth_headers(prn_roll="241106005", role="student")
    res = client.get("/attendance/forecast", headers=headers_stu)
    assert res.status_code == 200
    assert b"Interactive Attendance Simulator" in res.data
    assert b"241106005" in res.data

    # 2. Detention list
    res_det = client.get("/attendance/detention-list", headers=headers_stu)
    assert res_det.status_code == 200
    assert b"Official First Detention List" in res_det.data

    # 3. Simulate API
    res_sim = client.post(
        "/attendance/api/simulate",
        json={"attended": 30, "conducted": 40, "remaining": 30, "extra_attend": 4, "extra_miss": 1, "target_pct": 75.0},
        headers=headers_stu
    )
    assert res_sim.status_code == 200
    assert "projected_pct" in res_sim.get_json()

    # 4. Student API self query
    res_api = client.get("/attendance/api/student/241106005", headers=headers_stu)
    assert res_api.status_code == 200
    assert "overall" in res_api.get_json()

    # 5. IDOR test: Student cannot query other student's attendance API
    res_idor = client.get("/attendance/api/student/241106010", headers=headers_stu)
    assert res_idor.status_code == 403

    # 6. Faculty access with dropdown
    headers_fac = auth_headers(prn_roll="FAC_LANJEWAR", role="faculty")
    res_fac = client.get("/attendance/forecast?student_prn=241106010", headers=headers_fac)
    assert res_fac.status_code == 200
    assert b"Switch Student:" in res_fac.data
