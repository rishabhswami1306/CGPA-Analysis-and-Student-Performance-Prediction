from app import create_app
from flask_jwt_extended import create_access_token

app = create_app()
client = app.test_client()

with app.app_context():
    # Test 1: Student dashboard for honors student 241106058
    token = create_access_token(identity="241106058", additional_claims={"role": "student"})
    res = client.get("/student/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Dashboard failed with {res.status_code}"
    html = res.get_data(as_text=True)
    assert "CMPM" in html, "CMPM not found in student dashboard HTML"
    assert "EM" in html, "EM not found in student dashboard HTML"
    assert "Honors" in html, "Honors badge not found in student dashboard HTML"
    print("PASS: Student Dashboard displays both EM and CMPM honors cards!")

    # Test 2: Attendance Forecast for 241106058
    res_fc = client.get("/attendance/forecast?student_prn=241106058", headers={"Authorization": f"Bearer {token}"})
    assert res_fc.status_code == 200, f"Forecast failed with {res_fc.status_code}"
    html_fc = res_fc.get_data(as_text=True)
    assert "HONORS: CMPM" in html_fc or "CMPM" in html_fc, "CMPM not in forecast HTML"
    assert "HONORS: EM" in html_fc or "EM" in html_fc, "EM not in forecast HTML"
    assert "Honors: CMPM" in html_fc, "Honors: CMPM option not in forecast simulator select"
    assert "Honors: EM" in html_fc, "Honors: EM option not in forecast simulator select"
    assert "Dr. P.K. Patil" in html_fc, "Dr. P.K. Patil not found as CMPM teacher"
    assert "Prof. U.B. Chimankar" in html_fc, "Prof. U.B. Chimankar not found as EM teacher"
    print("PASS: Attendance Forecast displays both EM and CMPM cards, faculty, and simulator options!")

    # Test 3: Detention list
    admin_token = create_access_token(identity="ADMIN001", additional_claims={"role": "admin"})
    res_det = client.get("/attendance/detention-list", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_det.status_code == 200, f"Detention list failed with {res_det.status_code}"
    html_det = res_det.get_data(as_text=True)
    assert "EM, CMPM" in html_det, "EM, CMPM not found in detention list honors column"
    print("PASS: Detention list displays 'EM, CMPM' in Honors column!")

print("\nALL HONORS VERIFICATIONS PASSED!")
