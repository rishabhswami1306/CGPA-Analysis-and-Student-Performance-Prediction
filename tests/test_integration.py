import pytest
import io
from utils.db import get_db
from utils.pdf_generator import generate_student_transcript_pdf


def test_faculty_grade_submission_and_audit_flow(client, auth_headers):
    """End-to-end test: Faculty updates grade -> SGPA recalculated -> Audit logged."""
    db = get_db()
    # Seed one record for 2022CS001
    db.academic_records.insert_one({
        "student_prn": "2022CS001",
        "semester": 3,
        "attendance_percentage": 82.0,
        "subjects": [
            {
                "subject_code": "CS301",
                "subject_name": "Data Structures",
                "credits": 4,
                "tt1_score": 14.0,
                "tt2_score": 14.0,
                "ese_score": 50.0,
                "total_marks": 64.0,
                "grade_point": 7.0,
                "grade_letter": "B+"
            }
        ],
        "sgpa": 7.0,
        "active_backlogs": 0
    })

    # Faculty FAC001 (assigned CS301) submits higher marks
    fac_headers = auth_headers(prn_roll="FAC001", role="faculty", email="faculty@test.edu")
    res = client.post(
        "/faculty/submit-grade",
        headers=fac_headers,
        json={
            "student_prn": "2022CS001",
            "semester": 3,
            "subject_code": "CS301",
            "tt1_score": 18.0,
            "tt2_score": 18.0,
            "ese_score": 70.0
        }
    )

    assert res.status_code == 200
    data = res.get_json()
    # Total marks = 18 + 70 = 88 -> Grade point 10 (O)
    assert data["updated_subject"]["total_marks"] == 88.0
    assert data["updated_subject"]["grade_point"] == 10.0
    assert data["new_sgpa"] == 10.0

    # Verify audit log was recorded
    audit_entry = db.audit_logs.find_one({"action": "EDIT_MARKS", "target_student_prn": "2022CS001"})
    assert audit_entry is not None
    assert audit_entry["actor_prn"] == "FAC001"


def test_faculty_unauthorized_subject_rejection(client, auth_headers):
    """Ensure faculty cannot grade subjects not in their assigned_subjects list."""
    fac_headers = auth_headers(prn_roll="FAC001", role="faculty", email="faculty@test.edu")
    
    # FAC001 is assigned to CS301 and CS302, but attempts to grade CS999
    res = client.post(
        "/faculty/submit-grade",
        headers=fac_headers,
        json={
            "student_prn": "2022CS001",
            "semester": 3,
            "subject_code": "CS999",
            "tt1_score": 15.0,
            "tt2_score": 15.0,
            "ese_score": 60.0
        }
    )
    assert res.status_code == 403


def test_pdf_transcript_generation(client):
    """Verify ReportLab PDF transcript generation creates valid non-empty PDF bytes."""
    student_data = {
        "prn_roll": "2022CS001",
        "name": "Test Student",
        "branch": "CSE-DS",
        "admission_year": 2022
    }
    academic_records = [
        {
            "semester": 1,
            "sgpa": 8.5,
            "attendance_percentage": 85.0,
            "active_backlogs": 0,
            "subjects": [
                {
                    "subject_code": "FE101",
                    "subject_name": "Math I",
                    "credits": 4,
                    "tt1_score": 16.0,
                    "tt2_score": 16.0,
                    "ese_score": 68.0,
                    "total_marks": 84.0,
                    "grade_point": 10.0,
                    "grade_letter": "O"
                }
            ]
        }
    ]
    pdf_bytes = generate_student_transcript_pdf(student_data, academic_records)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:4] == b"%PDF"  # Valid PDF header
