import pytest
import json


def test_successful_login(client):
    """Test login endpoint returning valid access token."""
    res = client.post(
        "/auth/login",
        json={"email": "student1@test.edu", "password": "Student@12345"}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data
    assert data["user"]["role"] == "student"
    assert data["user"]["prn_roll"] == "2022CS001"


def test_invalid_login_credentials(client):
    """Test login failure on bad password."""
    res = client.post(
        "/auth/login",
        json={"email": "student1@test.edu", "password": "WrongPassword123"}
    )
    assert res.status_code == 401


def test_account_lockout_after_failed_attempts(client):
    """Test brute-force protection: 5 failed attempts locks the account."""
    for _ in range(5):
        client.post(
            "/auth/login",
            json={"email": "student2@test.edu", "password": "BadPassword"}
        )

    # 6th attempt should return 429 Too Many Requests (Account Locked)
    locked_res = client.post(
        "/auth/login",
        json={"email": "student2@test.edu", "password": "Student@12345"}
    )
    assert locked_res.status_code == 429
    assert "locked" in locked_res.get_json()["error"].lower()


def test_rbac_admin_route_protection(client, auth_headers):
    """Ensure student cannot access /admin/users and admin can."""
    # Student request
    student_headers = auth_headers(prn_roll="2022CS001", role="student", email="student1@test.edu")
    res_student = client.get("/admin/users", headers=student_headers)
    assert res_student.status_code == 403

    # Admin request
    admin_headers = auth_headers(prn_roll="ADMIN001", role="admin", email="admin@test.edu")
    res_admin = client.get("/admin/users", headers=admin_headers)
    assert res_admin.status_code == 200


def test_idor_protection_on_student_routes(client, auth_headers):
    """Ensure student cannot access another student's academic records via API."""
    student1_headers = auth_headers(prn_roll="2022CS001", role="student")
    
    # Student 1 attempts to query Student 2
    res = client.get("/api/student/2022CS002/academic-summary", headers=student1_headers)
    assert res.status_code == 403
    assert "not authorized" in res.get_json()["message"].lower()

    # Student 1 queries own PRN
    res_own = client.get("/api/student/2022CS001/academic-summary", headers=student1_headers)
    assert res_own.status_code == 200
