import pytest


def test_header_and_footer_modifications(client):
    """Ensure upper header has Admin, Faculty, Student login options, normal styling, and removed texts are gone."""
    res = client.get("/auth/login/student")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 1. Removed texts must NOT be present
    assert "Attendance & Academic Predictive System" not in html
    assert "All rights reserved" not in html
    assert "header-department-select" not in html  # Department section removed

    # 2. Institutional header text remains
    assert "R. C. Patel Institute of Technology" in html
    assert "SES's R. C. Patel Institute of Technology, Shirpur" in html

    # 3. Upper header options must be present with Student Login
    assert 'href="/auth/login/admin"' in html
    assert 'href="/auth/login/faculty"' in html
    assert 'href="/auth/login/student"' in html
    assert "Student Login" in html


def test_three_different_login_pages(client):
    """Ensure 3 distinct pages render with dedicated titles, clean user-friendly design, and no department dropdown."""
    # 1. Admin login page
    res_admin = client.get("/auth/login/admin")
    assert res_admin.status_code == 200
    admin_html = res_admin.get_data(as_text=True)
    assert "Administrator Login" in admin_html
    assert 'action="/auth/login/admin"' in admin_html
    assert 'name="target_role" value="admin"' in admin_html
    assert 'name="department"' not in admin_html
    assert "Exclusive Admin Gateway" not in admin_html

    # 2. Faculty login page
    res_faculty = client.get("/auth/login/faculty")
    assert res_faculty.status_code == 200
    faculty_html = res_faculty.get_data(as_text=True)
    assert "Faculty Login" in faculty_html
    assert 'action="/auth/login/faculty"' in faculty_html
    assert 'name="target_role" value="faculty"' in faculty_html
    assert 'name="department"' not in faculty_html
    assert "Faculty Gateway:" not in faculty_html

    # 3. Student login page
    res_student = client.get("/auth/login/student")
    assert res_student.status_code == 200
    student_html = res_student.get_data(as_text=True)
    assert "Student Login" in student_html
    assert 'action="/auth/login/student"' in student_html
    assert 'name="target_role" value="student"' in student_html
    assert 'name="department"' not in student_html
    assert "Student Gateway:" not in student_html


def test_admin_portal_exclusivity(client):
    """Only admins can log in to /auth/login/admin; faculty and students are blocked."""
    # Student attempting Admin login -> Blocked 403
    res_student = client.post(
        "/auth/login/admin",
        data={"email": "student1@test.edu", "password": "Student@12345"},
        follow_redirects=False
    )
    assert res_student.status_code == 403
    assert "Access Denied" in res_student.get_data(as_text=True)

    # Faculty attempting Admin login -> Blocked 403
    res_faculty = client.post(
        "/auth/login/admin",
        data={"email": "faculty@test.edu", "password": "Faculty@12345"},
        follow_redirects=False
    )
    assert res_faculty.status_code == 403
    assert "Access Denied" in res_faculty.get_data(as_text=True)

    # Admin attempting Admin login -> Success (302 redirect to admin dashboard)
    res_admin = client.post(
        "/auth/login/admin",
        data={"email": "admin@test.edu", "password": "Admin@12345"},
        follow_redirects=False
    )
    assert res_admin.status_code == 302
    assert "/admin/dashboard" in res_admin.headers.get("Location", "")


def test_faculty_portal_exclusivity(client):
    """Only faculty can log in to /auth/login/faculty; admins and students are blocked."""
    # Student attempting Faculty login -> Blocked 403
    res_student = client.post(
        "/auth/login/faculty",
        data={"email": "student1@test.edu", "password": "Student@12345"},
        follow_redirects=False
    )
    assert res_student.status_code == 403
    assert "Access Denied" in res_student.get_data(as_text=True)

    # Admin attempting Faculty login -> Blocked 403
    res_admin = client.post(
        "/auth/login/faculty",
        data={"email": "admin@test.edu", "password": "Admin@12345"},
        follow_redirects=False
    )
    assert res_admin.status_code == 403
    assert "Access Denied" in res_admin.get_data(as_text=True)

    # Faculty attempting Faculty login -> Success (302 redirect to faculty dashboard)
    res_faculty = client.post(
        "/auth/login/faculty",
        data={"email": "faculty@test.edu", "password": "Faculty@12345"},
        follow_redirects=False
    )
    assert res_faculty.status_code == 302
    assert "/faculty/dashboard" in res_faculty.headers.get("Location", "")


def test_student_portal_exclusivity(client):
    """Only students can log in to /auth/login/student; admins and faculty are blocked."""
    # Admin attempting Student login -> Blocked 403
    res_admin = client.post(
        "/auth/login/student",
        data={"email": "admin@test.edu", "password": "Admin@12345"},
        follow_redirects=False
    )
    assert res_admin.status_code == 403
    assert "Access Denied" in res_admin.get_data(as_text=True)

    # Faculty attempting Student login -> Blocked 403
    res_faculty = client.post(
        "/auth/login/student",
        data={"email": "faculty@test.edu", "password": "Faculty@12345"},
        follow_redirects=False
    )
    assert res_faculty.status_code == 403
    assert "Access Denied" in res_faculty.get_data(as_text=True)

    # Student attempting Student login -> Success (302 redirect to student dashboard)
    res_student = client.post(
        "/auth/login/student",
        data={"email": "student1@test.edu", "password": "Student@12345"},
        follow_redirects=False
    )
    assert res_student.status_code == 302
    assert "/student/dashboard" in res_student.headers.get("Location", "")
