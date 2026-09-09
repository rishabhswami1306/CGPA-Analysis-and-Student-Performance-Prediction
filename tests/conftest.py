import os
import sys
import pytest
from flask_jwt_extended import create_access_token
import mongomock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from utils.db import get_db, reset_db_connections
from routes.auth_routes import bcrypt


@pytest.fixture(scope="session")
def app():
    """Create Flask app configured for testing."""
    test_app = create_app("testing")
    test_app.config.update({
        "TESTING": True,
        "JWT_SECRET_KEY": "test-jwt-secret-key-12345",
        "SECRET_KEY": "test-secret-key-12345",
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False
    })
    return test_app


@pytest.fixture(scope="function")
def client(app):
    """Create test client with fresh in-memory mock database."""
    reset_db_connections()
    with app.app_context():
        db = get_db(uri="mongomock://localhost/cgpa_test_db", db_name="cgpa_test_db")
        # Clean collections
        db.users.delete_many({})
        db.academic_records.delete_many({})
        db.predictions_cache.delete_many({})
        db.placement_records.delete_many({})
        db.audit_logs.delete_many({})

        # Insert test users
        admin_pw = bcrypt.generate_password_hash("Admin@12345").decode("utf-8")
        db.users.insert_one({
            "prn_roll": "ADMIN001",
            "email": "admin@test.edu",
            "password_hash": admin_pw,
            "role": "admin",
            "name": "Test Admin",
            "branch": "CSE",
            "admission_year": 2018,
            "assigned_subjects": [],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0
        })

        faculty_pw = bcrypt.generate_password_hash("Faculty@12345").decode("utf-8")
        db.users.insert_one({
            "prn_roll": "FAC001",
            "email": "faculty@test.edu",
            "password_hash": faculty_pw,
            "role": "faculty",
            "name": "Prof. Test Faculty",
            "branch": "CSE-DS",
            "admission_year": 2019,
            "assigned_subjects": ["CS301", "CS302"],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0
        })

        student_pw = bcrypt.generate_password_hash("Student@12345").decode("utf-8")
        db.users.insert_one({
            "prn_roll": "2022CS001",
            "email": "student1@test.edu",
            "password_hash": student_pw,
            "role": "student",
            "name": "Test Student One",
            "branch": "CSE-DS",
            "admission_year": 2022,
            "assigned_subjects": [],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0
        })

        db.users.insert_one({
            "prn_roll": "2022CS002",
            "email": "student2@test.edu",
            "password_hash": student_pw,
            "role": "student",
            "name": "Test Student Two",
            "branch": "CSE-DS",
            "admission_year": 2022,
            "assigned_subjects": [],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0
        })

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(app):
    """Helper to generate JWT Authorization headers for tests."""
    def _headers(prn_roll="2022CS001", role="student", email="student1@test.edu"):
        with app.app_context():
            token = create_access_token(
                identity=prn_roll,
                additional_claims={"role": role, "email": email, "name": "Test User"}
            )
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
    return _headers
