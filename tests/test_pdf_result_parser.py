import io
import os
import zipfile
import pytest
import fitz
from unittest.mock import patch, MagicMock

from utils.pdf_result_parser import (
    parse_result_pdf,
    parse_batch_pdfs,
    commit_result_records,
    _parse_semester,
    _extract_branch_code,
    _parse_course_line
)


SAMPLE_PDF_PATH = r"C:\Users\risha\Desktop\resume\sem3 result.pdf"


def test_parse_semester_utility():
    assert _parse_semester("Second Year-SEM-III") == 3
    assert _parse_semester("SEM-111") == 3
    assert _parse_semester("SEM-IV") == 4
    assert _parse_semester("Third YearSEM-V") == 5
    assert _parse_semester("SEM 1") == 1
    assert _parse_semester("First Year") == 1


def test_extract_branch_code_utility():
    assert _extract_branch_code("BTech (COMPUTER SCIENCE AND ENGINEERING (DATA SCIENCE))") == "CSE-DS"
    assert _extract_branch_code("BTech (ARTIFICIAL INTELLIGENCE AND DATA SCIENCE)") == "CSE-AIML"
    assert _extract_branch_code("BTech Computer Engineering") == "CSE"
    assert _extract_branch_code("Mechanical Engineering") == "MECH"


def test_parse_course_line():
    line1 = "Computer System Fundamentals RCP23DPC201 3.00 40.00 31.00 60.00 34.00 65.00 B+"
    c1 = _parse_course_line(line1)
    assert c1 is not None
    assert c1["subject_code"] == "RCP23DPC201"
    assert c1["credits"] == 3
    assert c1["ca_marks"] == 31.0
    assert c1["ese_marks"] == 34.0
    assert c1["total_marks"] == 65.0
    assert c1["grade_letter"] == "B+"
    assert c1["grade_point"] == 7.0

    line2 = "Data Science Laboratory(Python) RCP23DPC203L 2.00 0.00 49.00 50.00 50.00 99.00 O"
    c2 = _parse_course_line(line2)
    assert c2 is not None
    assert c2["subject_code"] == "RCP23DPC203L"
    assert c2["credits"] == 2
    assert c2["total_marks"] == 99.0
    assert c2["grade_letter"] == "O"
    assert c2["grade_point"] == 10.0


def test_parse_digital_text_pdf():
    # Build in-memory synthetic digital PDF
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    sample_text = """
    R. C. Patel Institute of Technology
    Statement of Marks & Grade
    Name Of the Student: Jane Doe
    Mother Name: Mary
    PRN: 241106099
    Programme: BTech (COMPUTER SCIENCE AND ENGINEERING (DATA SCIENCE))
    Year & Semester: Second Year-SEM-III
    Academic Year: 2025-2026
    Examination: END SEMESTER ODD 2025-26 REGULAR

    Subjects/s Course Code Credit CA Max CA ESE Max ESE Total Grade
    Computer System Fundamentals RCP23DPC201 3.00 40.00 32.00 60.00 45.00 77.00 A
    Database Systems RCP23DPC202 3.00 40.00 35.00 60.00 48.00 83.00 A+
    Mathematics for Intelligent Systems RCP23DMD201 3.00 40.00 38.00 60.00 52.00 90.00 O

    SGPA (SEM III) : 8.89
    CGPA : 8.75
    CREarned (SEM III) : 9
    """
    page.insert_text((50, 50), sample_text, fontsize=10)
    pdf_bytes = doc.tobytes()

    res = parse_result_pdf(pdf_bytes, filename="jane_doe_sem3.pdf")
    assert res["status"] == "success"
    assert res["student_prn"] == "241106099"
    assert "Jane Doe" in res["student_name"]
    assert res["semester"] == 3
    assert res["branch"] == "CSE-DS"
    assert len(res["subjects"]) >= 3
    assert res["sgpa"] == 8.89
    assert res["cgpa"] == 8.75


@pytest.mark.skipif(not os.path.exists(SAMPLE_PDF_PATH), reason="Sample real PDF not found on host")
def test_parse_real_marksheet_pdf():
    res = parse_result_pdf(SAMPLE_PDF_PATH, filename="sem3 result.pdf")
    assert res["status"] == "success"
    assert res["confidence"] == "high"
    assert res["student_prn"] == "241106005"
    assert "Rishabh" in res["student_name"]
    assert res["semester"] == 3
    assert res["branch"] == "CSE-DS"
    assert res["sgpa"] == 8.14
    assert res["cgpa"] == 8.33
    assert res["credits_earned"] == 22
    assert len(res["subjects"]) == 11


def test_commit_result_records(app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()

        test_records = [
            {
                "filename": "test_student.pdf",
                "student_prn": "241109999",
                "student_name": "Test Real Student",
                "mother_name": "Mother Test",
                "branch": "CSE-DS",
                "semester": 3,
                "academic_year": "2025-2026",
                "sgpa": 8.50,
                "cgpa": 8.40,
                "credits_earned": 20,
                "subjects": [
                    {
                        "subject_code": "RCP23DPC201",
                        "subject_name": "Computer System Fundamentals",
                        "credits": 3,
                        "ca_marks": 35.0,
                        "ese_marks": 45.0,
                        "total_marks": 80.0,
                        "grade_letter": "O",
                        "grade_point": 10.0
                    },
                    {
                        "subject_code": "RCP23DPC202",
                        "subject_name": "Database Systems",
                        "credits": 3,
                        "ca_marks": 30.0,
                        "ese_marks": 40.0,
                        "total_marks": 70.0,
                        "grade_letter": "A",
                        "grade_point": 8.0
                    }
                ]
            }
        ]

        result = commit_result_records(test_records, purge_legacy_seed=True, actor_prn="ADMIN")
        assert result["status"] == "success"
        assert result["committed_students_count"] == 1
        assert result["committed_semesters_count"] == 1

        # Verify user in db.users
        user = db.users.find_one({"prn_roll": "241109999"})
        assert user is not None
        assert user["name"] == "Test Real Student"
        assert user["role"] == "student"
        assert user["branch"] == "CSE-DS"
        assert user["is_real_student"] is True

        # Verify academic record
        acad = db.academic_records.find_one({"student_prn": "241109999", "semester": 3})
        assert acad is not None
        assert acad["sgpa"] == 8.50
        assert acad["is_real_marksheet"] is True
        assert len(acad["subjects"]) == 2

        # Clean up
        db.users.delete_one({"prn_roll": "241109999"})
        db.academic_records.delete_many({"student_prn": "241109999"})


def test_batch_parse_zip():
    # Create in-memory zip of two synthetic PDFs
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 50), "Statement of Marks PRN: 241107771 Name: Student One SEM-I SGPA: 8.00\nRCP23DPC101 3.00 40 30 60 40 70 A", fontsize=10)
    pdf_bytes1 = doc.tobytes()

    doc2 = fitz.open()
    page2 = doc2.new_page(width=612, height=792)
    page2.insert_text((50, 50), "Statement of Marks PRN: 241107772 Name: Student Two SEM-I SGPA: 8.50\nRCP23DPC101 3.00 40 30 60 50 80 O", fontsize=10)
    pdf_bytes2 = doc2.tobytes()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("student1.pdf", pdf_bytes1)
        zf.writestr("student2.pdf", pdf_bytes2)

    zip_buf.seek(0)
    zip_item = MagicMock()
    zip_item.filename = "batch_results.zip"
    zip_item.read.return_value = zip_buf.getvalue()

    batch_res = parse_batch_pdfs([zip_item])
    assert batch_res["total_files"] == 2
    assert batch_res["records"][0]["student_prn"] in ["241107771", "241107772"]


def test_admin_upload_results_pdf_routes(client, app):
    # 1. Unauthenticated gets redirected
    res_unauth = client.get("/admin/upload-results-pdf")
    assert res_unauth.status_code in [302, 401]

    # 2. Login as admin
    client.post("/auth/login", data={"email": "admin@test.edu", "password": "Admin@12345"}, follow_redirects=True)

    # 3. GET view renders upload interface
    res_get = client.get("/admin/upload-results-pdf")
    assert res_get.status_code == 200
    assert b"Upload Real Student Result Marksheets" in res_get.data
    assert b"pdf_files_input" in res_get.data

    # 4. POST commit with staged records
    import json
    staged_payload = [
        {
            "filename": "route_test_result.pdf",
            "student_prn": "241108888",
            "student_name": "HTTP Route Test Student",
            "branch": "CSE-DS",
            "semester": 3,
            "academic_year": "2025-2026",
            "sgpa": 8.75,
            "cgpa": 8.60,
            "credits_earned": 22,
            "subjects": [
                {
                    "subject_code": "RCP23DPC201",
                    "subject_name": "Computer System Fundamentals",
                    "credits": 3,
                    "ca_marks": 36.0,
                    "ese_marks": 48.0,
                    "total_marks": 84.0,
                    "grade_letter": "A+",
                    "grade_point": 9.0
                }
            ]
        }
    ]

    res_commit = client.post(
        "/admin/upload-results-pdf",
        data={
            "action": "commit",
            "purge_legacy": "true",
            "staged_records": json.dumps(staged_payload)
        },
        follow_redirects=True
    )
    assert res_commit.status_code == 200
    assert b"Successfully saved" in res_commit.data

    # Verify db upsert
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        usr = db.users.find_one({"prn_roll": "241108888"})
        assert usr is not None
        assert usr["name"] == "HTTP Route Test Student"
        # Cleanup
        db.users.delete_one({"prn_roll": "241108888"})
        db.academic_records.delete_many({"student_prn": "241108888"})


def test_marking_and_numbering_edge_cases():
    from utils.pdf_result_parser import _clean_numeric_tokens, get_student_year_context

    # 1. OCR split decimals and trailing dots
    dirty_text = "SGPA: 8. 14 Marks: 99. 00 Trailing: 38. Comma: 7,50"
    cleaned = _clean_numeric_tokens(dirty_text)
    assert "8.14" in cleaned
    assert "99.00" in cleaned
    assert "38.00" in cleaned
    assert "7.50" in cleaned

    # 2. 25-mark Lab course (must not be treated as out of 100 or multiplied by 2)
    # 21/25 = 84% -> Grade O (10.0)
    line_lab25 = "Design Thinking Lab RCP23DPC205L 1.00 0.00 0.00 25.00 21.00 21.00 O"
    c_lab = _parse_course_line(line_lab25)
    assert c_lab is not None
    assert c_lab["total_marks"] == 21.0
    assert c_lab["grade_letter"] == "O"
    assert c_lab["grade_point"] == 10.0

    # 3. 50-mark Lab course
    # 42/50 = 84% -> Grade O (10.0)
    line_lab50 = "Web Technology Lab RCP23DPC206L 2.00 0.00 0.00 50.00 42.00 42.00 O"
    c_lab50 = _parse_course_line(line_lab50)
    assert c_lab50 is not None
    assert c_lab50["total_marks"] == 42.0
    assert c_lab50["grade_letter"] == "O"
    assert c_lab50["grade_point"] == 10.0

    # 4. 100-mark Theory course with 50 marks
    # 50/100 = 50% -> Grade B (6.0), NOT doubled to 100.0/Grade O
    line_theory50 = "Discrete Mathematics RCP23DPC207 3.00 40.00 20.00 60.00 30.00 50.00 B"
    c_theory = _parse_course_line(line_theory50)
    assert c_theory is not None
    assert c_theory["total_marks"] == 50.0
    assert c_theory["grade_letter"] == "B"
    assert c_theory["grade_point"] == 6.0

    # 5. Student year context
    student_3rd_year = {"current_year": "3rd", "current_semester": 5}
    ctx = get_student_year_context(student_3rd_year)
    assert ctx["year_num"] == 3
    assert ctx["default_semesters"] == [1, 2, 3, 4]

    student_2nd_year = {"current_year": "2nd", "current_semester": 3}
    ctx2 = get_student_year_context(student_2nd_year)
    assert ctx2["year_num"] == 2
    assert ctx2["default_semesters"] == [1, 2]


def test_sectionwise_student_upload_route(client, app):
    # 1. Setup mock student in db
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.users.delete_one({"prn_roll": "241103333"})
        db.academic_records.delete_many({"student_prn": "241103333"})
        db.users.insert_one({
            "prn_roll": "241103333",
            "name": "SectionWise Demo Student",
            "role": "student",
            "branch": "CSE-DS",
            "current_year": "3rd",
            "current_semester": 5,
            "email": "demo.sectionwise@test.edu"
        })

    # 2. Login as admin
    client.post("/auth/login", data={"email": "admin@test.edu", "password": "Admin@12345"}, follow_redirects=True)

    # 3. Create synthetic PDF for Semester 1
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 50), "Statement of Marks PRN: 241103333 Name: SectionWise Demo Student SEM-I SGPA: 8.40\nRCP23DPC101 3.00 40 32 60 48 80 O", fontsize=10)
    pdf_bytes1 = doc.tobytes()

    # Create synthetic PDF for Semester 2
    doc2 = fitz.open()
    page2 = doc2.new_page(width=612, height=792)
    page2.insert_text((50, 50), "Statement of Marks PRN: 241103333 Name: SectionWise Demo Student SEM-II SGPA: 8.60\nRCP23DPC102 3.00 40 34 60 50 84 O", fontsize=10)
    pdf_bytes2 = doc2.tobytes()

    # 4. Post section-wise upload for Semesters 1 and 2
    data = {
        "action": "upload_and_predict",
        "student_prn": "241103333",
        "auto_commit": "true",
        "sem_file_1": (io.BytesIO(pdf_bytes1), "sem1_result.pdf"),
        "sem_file_2": (io.BytesIO(pdf_bytes2), "sem2_result.pdf"),
    }

    res = client.post("/admin/upload-results-pdf", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200
    assert b"Successfully saved" in res.data
    assert b"AI Upcoming Result Forecast" in res.data or b"Predicted Upcoming SGPA" in res.data

    # 5. Verify records in DB
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        records = list(db.academic_records.find({"student_prn": "241103333"}).sort("semester", 1))
        assert len(records) == 2
        assert records[0]["semester"] == 1
        assert records[0]["sgpa"] == 8.40
        assert records[1]["semester"] == 2
        assert records[1]["sgpa"] == 8.60

        # Clean up
        db.users.delete_one({"prn_roll": "241103333"})
        db.academic_records.delete_many({"student_prn": "241103333"})


SM3R_PDF_PATH = r"C:\Users\risha\Desktop\resume\sm3r.pdf"
IMAGE_PATH = r"marksheet_preview.png"


@pytest.mark.skipif(not os.path.exists(SM3R_PDF_PATH), reason="Sample sm3r marksheet not found on host")
def test_parse_sm3r_scanned_pdf():
    res = parse_result_pdf(SM3R_PDF_PATH, filename="sm3r.pdf")
    assert res["status"] == "success"
    assert res["confidence"] == "high"
    assert res["student_prn"] == "241106058"
    assert "Diya" in res["student_name"] or "Prajapat" in res["student_name"]
    assert res["semester"] == 3
    assert res["sgpa"] == 7.14
    assert res["cgpa"] == 7.67
    assert res["credits_earned"] == 22
    assert len(res["subjects"]) == 11

    # Verify Data Science Lab marks reconciliation
    ds_lab = next(s for s in res["subjects"] if "203L" in s["subject_code"])
    assert ds_lab["total_marks"] == 98.0
    assert ds_lab["max_marks"] == 100.0
    assert ds_lab["ca_max"] == 50.0
    assert ds_lab["ese_max"] == 50.0
    assert ds_lab["grade_letter"] == "O"


@pytest.mark.skipif(not os.path.exists(IMAGE_PATH), reason="marksheet_preview.png not found on host")
def test_parse_direct_marksheet_image():
    res = parse_result_pdf(IMAGE_PATH, filename="marksheet_preview.png")
    assert res["status"] == "success"
    assert res["student_prn"] == "241106005"
    assert "Rishabh" in res["student_name"]
    assert res["semester"] == 3
    assert res["sgpa"] == 8.14
    assert len(res["subjects"]) == 11



