import pytest
from app import create_app
from utils.db import get_db

def test_admin_rbac_and_login_protection(client):
    """Verify unauthorized users cannot access admin dashboard, only authorized admin can."""
    # 1. Unauthenticated request redirected or rejected
    res = client.get("/admin/dashboard")
    assert res.status_code in [302, 401]

    # 2. Student login cannot access admin dashboard (HTTP 403)
    res_student_login = client.post("/auth/login", data={"email": "student1@test.edu", "password": "Student@12345"}, follow_redirects=True)
    assert res_student_login.status_code == 200
    res_forbidden = client.get("/admin/dashboard")
    assert res_forbidden.status_code in [302, 403]

    # 3. Admin login successfully accesses admin dashboard
    client.get("/auth/logout")
    res_admin_login = client.post("/auth/login", data={"email": "admin@test.edu", "password": "Admin@12345"}, follow_redirects=True)
    assert res_admin_login.status_code == 200

    res_admin_dash = client.get("/admin/dashboard")
    assert res_admin_dash.status_code == 200
    assert b"Department of Computer Science and Engineering (Data Science)" in res_admin_dash.data or b"Computer Science and Engineering (Data Science)" in res_admin_dash.data
    assert b"Cohort Students" in res_admin_dash.data
    assert b"Academic Data Management" in res_admin_dash.data

def test_student_management_crud(client):
    """Test registering, updating, viewing profile, and deleting a student."""
    # Login as admin
    client.post("/auth/login", data={"email": "admin@test.edu", "password": "Admin@12345"}, follow_redirects=True)

    test_prn = "202401100999"
    db = get_db()
    db.users.delete_many({"prn_roll": test_prn})
    db.academic_records.delete_many({"student_prn": test_prn})

    # 1. Register student
    reg_payload = {
        "prn_roll": test_prn,
        "name": "Integration Test Student",
        "email": "teststudent999@institute.edu",
        "role": "student",
        "branch": "CSE-DS",
        "admission_year": 2024,
        "password": "TestPassword@123"
    }
    reg_res = client.post("/admin/users", data=reg_payload, follow_redirects=True)
    assert reg_res.status_code == 200

    created_user = db.users.find_one({"prn_roll": test_prn})
    assert created_user is not None
    assert created_user["name"] == "Integration Test Student"

    # 2. View individual student profile
    profile_res = client.get(f"/admin/students/{test_prn}")
    assert profile_res.status_code == 200
    assert b"Integration Test Student" in profile_res.data
    assert b"Computer Science and Engineering (Data Science)" in profile_res.data

    # 3. Update student details
    update_res = client.post(
        f"/admin/users/{test_prn}",
        data={
            "name": "Integration Test Student Updated",
            "email": "updatedstudent999@institute.edu",
            "branch": "CSE-DS",
            "admission_year": 2024,
            "is_active": "true"
        },
        follow_redirects=True
    )
    assert update_res.status_code == 200
    updated_user = db.users.find_one({"prn_roll": test_prn})
    assert updated_user["name"] == "Integration Test Student Updated"
    assert updated_user["email"] == "updatedstudent999@institute.edu"

    # 4. Delete student record
    del_res = client.post(f"/admin/users/{test_prn}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    deleted_user = db.users.find_one({"prn_roll": test_prn})
    assert deleted_user is None

def test_academic_data_management_marks_and_cgpa(client):
    """Test entering marks (TT 30, Int 40) and managing SGPA/CGPA."""
    # Login as admin
    client.post("/auth/login", data={"email": "admin@test.edu", "password": "Admin@12345"}, follow_redirects=True)

    test_prn = "2022CS001"
    db = get_db()
    
    # Initialize a base record for student 2022CS001
    db.academic_records.delete_many({"student_prn": test_prn, "semester": 5})

    # 1. Admin grade entry with 30-mark TT
    grade_payload = {
        "student_prn": test_prn,
        "semester": 5,
        "course_code": "CS501",
        "tt1_score": 27.0,  # out of 30
        "tt2_score": 28.5,  # out of 30
        "assignment_score": 4.5,
        "attendance_score": 5.0,
        "quiz_score": 4.0,
        "seminar_score": 4.5,
        "ese_score": 52.0  # out of 60
    }
    entry_res = client.post("/admin/grade-entry", data=grade_payload, follow_redirects=True)
    assert entry_res.status_code == 200

    rec = db.academic_records.find_one({"student_prn": test_prn, "semester": 5})
    assert rec is not None
    assert rec["sgpa"] is not None

    found_course = next((c for c in rec.get("courses", []) if c.get("course_code") == "CS501"), None)
    assert found_course is not None
    assert found_course["tt1_score"] == 27.0
    assert found_course["tt2_score"] == 28.5
    # TT converted to 15: round(((27.0 + 28.5) / 60) * 15, 2) = 13.88
    assert found_course["tt_converted_15"] == 13.88
    # Internals: 13.88 + 4.5 + 5.0 + 4.0 + 4.5 = 31.88
    assert found_course["total_internal_40"] == 31.88
    # Total: 31.88 + 52.0 = 83.88
    assert found_course["total_100"] == 83.88

    # 2. Recalculate CGPA endpoint
    recalc_res = client.post(f"/admin/students/{test_prn}/recalculate-cgpa", follow_redirects=True)
    assert recalc_res.status_code == 200
    user_after = db.users.find_one({"prn_roll": test_prn})
    assert "cgpa" in user_after
    assert user_after["cgpa"] > 0
