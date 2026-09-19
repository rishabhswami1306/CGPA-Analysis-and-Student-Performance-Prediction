import io
import json
import pytest
import pandas as pd
from utils.db import get_db
from utils.bulk_uploader import (
    parse_upload_file, validate_and_prepare_batch, commit_faculty_bulk_upload, generate_bulk_template
)


def test_bulk_uploader_tt_marks_parsing(client):
    """Verify parsing and validation of Unit Test marks from CSV with alias headers."""
    csv_data = """prn,subject,tt1,tt2,apt,skat,ta,mock,pres,ese
2022CS001,CS301,18.5,17.5,4.0,4.5,4.5,4.0,4.0,52.0
2022CS002,CS301,15.0,16.0,3.5,3.0,4.0,3.5,3.5,45.0
"""
    file_buf = io.BytesIO(csv_data.encode("utf-8"))
    df = parse_upload_file(file_buf, "test_tt.csv")
    assert "student_prn" in df.columns
    assert "subject_code" in df.columns
    assert "tt1_score" in df.columns
    assert "tt2_score" in df.columns

    batch = validate_and_prepare_batch(
        df=df,
        upload_type="tt_marks",
        default_semester=5,
        default_subject="CS301",
        authorized_subjects=["CS301", "CS302"],
        is_admin=False
    )

    assert batch["is_valid"] is True
    assert batch["valid_count"] == 2
    assert len(batch["errors"]) == 0

    first = batch["staged_rows"][0]
    assert first["student_prn"] == "2022CS001"
    assert first["subject_code"] == "CS301"
    assert first["marks"]["tt1_score"] == 18.5
    assert first["marks"]["tt2_score"] == 17.5
    assert first["marks"]["tt_converted"] == 9.0  # round((18.5 + 17.5)/4.0, 2)
    assert first["marks"]["internal_score"] > 25.0
    assert first["marks"]["total_marks"] > 70.0


def test_bulk_uploader_attendance_bunk_parsing(client):
    """Verify parsing of Attendance Register and Bunk counts."""
    csv_data = """student_prn,subject_code,conducted_hours,attended_hours,bunked_hours
2022CS001,CS301,36,32,4
2022CS002,CS301,36,25,11
"""
    file_buf = io.BytesIO(csv_data.encode("utf-8"))
    df = parse_upload_file(file_buf, "test_attendance.csv")

    batch = validate_and_prepare_batch(
        df=df,
        upload_type="attendance_bunk",
        default_semester=5,
        default_subject="CS301",
        authorized_subjects=["CS301"],
        is_admin=False
    )

    assert batch["is_valid"] is True
    assert batch["valid_count"] == 2

    row1 = batch["staged_rows"][0]
    assert row1["attendance"]["conducted_hours"] == 36
    assert row1["attendance"]["attended_hours"] == 32
    assert row1["attendance"]["bunked_hours"] == 4
    assert row1["attendance"]["attendance_percentage"] == round((32 / 36) * 100.0, 2)
    assert row1["attendance"]["safe_bunks"] >= 4
    assert row1["attendance"]["detention_risk"] is False

    row2 = batch["staged_rows"][1]
    assert row2["attendance"]["attendance_percentage"] < 75.0
    assert row2["attendance"]["detention_risk"] is True


def test_bulk_upload_clean_overwrite(client):
    """
    Verify that committing bulk upload cleanly removes/overwrites previous records
    and recalculates internals and totals.
    """
    db = get_db()
    # Seed an existing record with old scores
    db.academic_records.insert_one({
        "student_prn": "2022CS001",
        "semester": 5,
        "academic_year": "2026-27",
        "is_completed": False,
        "attendance_percentage": 70.0,
        "subjects": [
            {
                "subject_code": "CS301",
                "subject_name": "Course CS301",
                "credits": 4,
                "tt1_score": 10.0,
                "tt2_score": 11.0,
                "tt_converted": 5.25,
                "aptitude_score": 1.0,
                "skat_score": 1.0,
                "teacher_assessment_score": 1.0,
                "mock_interview_score": 1.0,
                "presentation_score": 1.0,
                "internal_score": 10.25,
                "ese_score": 0.0,
                "total_marks": 10.25,
                "grade_point": 0.0,
                "grade_letter": "F"
            }
        ]
    })

    # Prepare fresh staged row with updated TT marks
    staged = [
        {
            "row_num": 2,
            "student_prn": "2022CS001",
            "student_name": "Test Student One",
            "semester": 5,
            "subject_code": "CS301",
            "has_marks": True,
            "has_attendance": True,
            "marks": {
                "tt1_score": 19.0,
                "tt2_score": 19.5,
                "tt_converted": 9.62,
                "aptitude_score": 4.5,
                "skat_score": 4.5,
                "teacher_assessment_score": 4.5,
                "mock_interview_score": 4.0,
                "presentation_score": 4.5,
                "ese_score": 0.0,
                "internal_score": 31.62,
                "total_marks": 31.62,
                "grade_point": 0.0,
                "grade_letter": "F"
            },
            "attendance": {
                "conducted_hours": 40,
                "attended_hours": 36,
                "bunked_hours": 4,
                "attendance_percentage": 90.0,
                "safe_bunks": 6,
                "detention_risk": False
            }
        }
    ]

    commit_res = commit_faculty_bulk_upload(
        staged_rows=staged,
        actor_prn="FAC001",
        actor_role="faculty",
        overwrite_mode=True
    )

    assert commit_res["success"] is True
    assert commit_res["records_overwritten"] == 1
    assert "2022CS001" in commit_res["updated_prns"]

    # Verify that previous record was completely replaced in the database
    updated_rec = db.academic_records.find_one({"student_prn": "2022CS001", "semester": 5})
    assert updated_rec is not None
    assert updated_rec["attendance_percentage"] == 90.0

    subject = updated_rec["subjects"][0]
    assert subject["subject_code"] == "CS301"
    assert subject["tt1_score"] == 19.0
    assert subject["tt2_score"] == 19.5
    assert subject["tt_converted"] == 9.62
    assert subject["internal_score"] == 31.62

    # Verify attendance records collection was updated
    att_doc = db.attendance_records.find_one({"student_prn": "2022CS001"})
    assert att_doc is not None
    assert att_doc["overall_percentage"] == 90.0
    assert att_doc["subjects"]["CS301"]["lecture_attended"] == 36
    assert att_doc["subjects"]["CS301"]["bunked_hours"] == 4


def test_bulk_upload_template_generation():
    """Verify downloadable template generation for CSV and Excel."""
    # Test CSV
    buf_csv, fn_csv, mime_csv = generate_bulk_template("tt_marks", "csv", "CS301", 5)
    assert fn_csv.endswith(".csv")
    assert mime_csv == "text/csv"
    content_csv = buf_csv.getvalue().decode("utf-8")
    assert "student_prn" in content_csv
    assert "tt1_score" in content_csv

    # Test Excel
    buf_xl, fn_xl, mime_xl = generate_bulk_template("attendance_bunk", "excel", "CS301", 5)
    assert fn_xl.endswith(".xlsx")
    assert "spreadsheetml" in mime_xl
    df_xl = pd.read_excel(buf_xl)
    assert "conducted_hours" in df_xl.columns or "bunked_hours" in df_xl.columns


def test_faculty_bulk_upload_http_routes(client, auth_headers):
    """Verify HTTP endpoints for faculty bulk upload view and template download."""
    headers = auth_headers(prn_roll="FAC001", role="faculty")

    # 1. GET /faculty/bulk-upload
    res_get = client.get("/faculty/bulk-upload", headers=headers)
    assert res_get.status_code == 200
    assert b"Bulk Spreadsheet Upload" in res_get.data

    # 2. GET /faculty/bulk-upload/template (CSV)
    res_tmpl = client.get("/faculty/bulk-upload/template?type=tt_marks&format=csv&subject_code=CS301&semester=5", headers=headers)
    assert res_tmpl.status_code == 200
    assert res_tmpl.mimetype == "text/csv"

    # 3. POST /faculty/bulk-upload (Upload CSV with direct_commit=true)
    csv_content = b"""student_prn,subject_code,tt1_score,tt2_score,attendance_percentage
2022CS001,CS301,18.0,17.0,85.0
2022CS002,CS301,16.5,15.5,78.0
"""
    data = {
        "file": (io.BytesIO(csv_content), "marks_upload.csv"),
        "upload_type": "combined",
        "default_subject": "CS301",
        "semester": "5",
        "direct_commit": "true",
        "overwrite_mode": "true"
    }

    res_post = client.post(
        "/faculty/bulk-upload",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": headers["Authorization"]}
    )

    assert res_post.status_code == 200
    assert b"Records Successfully Overwritten" in res_post.data or b"Successfully updated and overwritten" in res_post.data
