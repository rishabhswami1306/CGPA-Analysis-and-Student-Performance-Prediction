import os
import sys
import traceback

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from utils.db import get_db

def test_live_app():
    print("--- 1. Initializing Flask App (development config) ---")
    app = create_app("development")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    client = app.test_client()

    print("\n--- 2. Checking Database Connectivity and Seeded Data ---")
    with app.app_context():
        db = get_db()
        users_count = db.users.count_documents({})
        acad_count = db.academic_records.count_documents({})
        print(f"Users in DB: {users_count}")
        print(f"Academic records in DB: {acad_count}")

        if users_count == 0:
            print("WARNING: No users in DB! Running seed_data...")
            from scripts.seed_data import seed_database
            seed_database()
            users_count = db.users.count_documents({})
            print(f"Users after seeding: {users_count}")

    test_accounts = [
        ("admin@rcpit.ac.in", "Admin@12345", "/admin/dashboard"),
        ("lanjewar@rcpit.ac.in", "Faculty@12345", "/faculty/dashboard"),
        ("salunkhe@rcpit.ac.in", "Faculty@12345", "/faculty/dashboard"),
        ("241106005@rcpit.ac.in", "241106005", "/student/dashboard"),  # Rishabh Swami (Safe, Honors)
        ("241106010@rcpit.ac.in", "241106010", "/student/dashboard"),  # Patil Kunal (Detained: 66.67%)
        ("241106001@rcpit.ac.in", "241106001", "/student/dashboard"),  # Sangpal Amey (Safe: 95.4%)
    ]

    print("\n--- 3. Testing Authentication & Dashboard Rendering ---")
    for email, password, target_url in test_accounts:
        print(f"\nTesting account: {email} -> {target_url}")
        login_res = client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)
        print(f"  Login response: {login_res.status_code}")
        if login_res.status_code not in [200, 302]:
            print(f"  FAILED login for {email}: {login_res.data[:200]}")
            continue

        # Check cookies set
        cookies = client.get_cookie("access_token_cookie")
        print(f"  Access token cookie present: {bool(cookies)}")

        # Visit dashboard
        try:
            dash_res = client.get(target_url)
            print(f"  Dashboard GET {target_url}: Status {dash_res.status_code}")
            if dash_res.status_code != 200:
                print(f"  ERROR: Status {dash_res.status_code}")
                # Print response snippet or traceback
                print(dash_res.data.decode("utf-8", errors="ignore")[:500])
            else:
                print("  SUCCESS! Rendered cleanly.")
        except Exception as e:
            print(f"  EXCEPTION while rendering {target_url}: {e}")
            traceback.print_exc()

    print("\n--- 4. Testing Prediction Functions Directly ---")
    with app.app_context():
        from ml_engine.inference import predict_student_analytics
        test_prns = ["241106005", "241106010", "241106001"]
        for prn in test_prns:
            print(f"\nTesting predict_student_analytics('{prn}', force_recalculate=True):")
            try:
                res = predict_student_analytics(prn, force_recalculate=True)
                print(f"  Predicted SGPA: {res.get('predicted_next_sgpa')}")
                print(f"  Bounds: [{res.get('predicted_sgpa_min')} — {res.get('predicted_sgpa_max')}]")
                print(f"  Archetype: {res.get('persona_archetype', {}).get('archetype_name')}")
                print(f"  EWS Status: {res.get('early_warning_system', {}).get('trajectory_status')}")
                print(f"  Subjects analyzed: {res.get('subject_risk_analysis', {}).get('total_subjects')}")
                print("  SUCCESS!")
            except Exception as e:
                print(f"  EXCEPTION on PRN {prn}: {e}")
                traceback.print_exc()

if __name__ == "__main__":
    test_live_app()
