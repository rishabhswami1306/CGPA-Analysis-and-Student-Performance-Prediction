import requests

BASE_URL = "http://127.0.0.1:5000"

logins = [
    ("admin", "Admin@12345", "/admin/dashboard"),
    ("admin", "admin", "/admin/dashboard"),
    ("ADMIN001", "Admin@12345", "/admin/dashboard"),
    ("admin@rcpit.ac.in", "Admin@12345", "/admin/dashboard"),
    ("sanjekar", "Faculty@12345", "/faculty/dashboard"),
    ("241106005", "241106005", "/student/dashboard"),
    ("241106010", "241106010", "/student/dashboard"),
]

print("=== VERIFYING LIVE HTTP LOGINS ===")
for ident, pwd, expected_loc in logins:
    session = requests.Session()
    resp = session.post(
        f"{BASE_URL}/auth/login",
        data={"email": ident, "password": pwd},
        allow_redirects=False
    )
    status = resp.status_code
    loc = resp.headers.get("Location", "")
    assert status == 302, f"Failed for {ident}: status={status}, resp={resp.text[:200]}"
    assert expected_loc in loc, f"Expected {expected_loc} in {loc}"
    print(f" [PASS] Login '{ident}' -> HTTP {status} Redirect: {loc}")

print("\n=== VERIFYING RE-UPLOAD DETENTION LIST PAGE ===")
admin_session = requests.Session()
admin_session.post(f"{BASE_URL}/auth/login", data={"email": "admin", "password": "Admin@12345"})
detention_page = admin_session.get(f"{BASE_URL}/attendance/reupload-detention-list")
assert detention_page.status_code == 200, f"Detention page returned {detention_page.status_code}"
assert "Re-upload Detention Notice" in detention_page.text
print(f" [PASS] /attendance/reupload-detention-list -> HTTP 200 OK (Page contains 'Re-upload Detention Notice')")

print("\n=== VERIFYING RESULT PDF UPLOAD PAGES ===")
pdf_page = admin_session.get(f"{BASE_URL}/admin/upload-results-pdf")
assert pdf_page.status_code == 200, f"Admin PDF upload returned {pdf_page.status_code}"
assert "Upload Student Result Marksheets" in pdf_page.text
print(f" [PASS] /admin/upload-results-pdf -> HTTP 200 OK")

faculty_session = requests.Session()
faculty_session.post(f"{BASE_URL}/auth/login", data={"email": "sanjekar", "password": "Faculty@12345"})
faculty_pdf_page = faculty_session.get(f"{BASE_URL}/faculty/upload-results-pdf")
assert faculty_pdf_page.status_code == 200, f"Faculty PDF upload returned {faculty_pdf_page.status_code}"
assert "Upload Student Result Marksheets" in faculty_pdf_page.text
print(f" [PASS] /faculty/upload-results-pdf -> HTTP 200 OK")

print("\n=== ALL LIVE VERIFICATIONS PASSED SUCCESSFULLY! ===")
