import io
import json
import pytest
from unittest.mock import MagicMock
from utils.detention_list_parser import (
    parse_detention_file,
    commit_detention_records,
    parse_detention_row_line
)


def test_parse_detention_row_line():
    db_by_prn = {"241106010": {"prn_roll": "241106010", "name": "Patil Kunal Sanjay", "roll_no": 9}}
    db_by_roll = {9: {"prn_roll": "241106010", "name": "Patil Kunal Sanjay", "roll_no": 9}}

    line = "9 241106010 PATIL KUNAL SANJAY 58 87 66.67%"
    parsed = parse_detention_row_line(line, db_by_prn, db_by_roll)
    assert parsed is not None
    assert parsed["student_prn"] == "241106010"
    assert parsed["roll_no"] == 9
    assert parsed["percentage"] == 66.67
    assert parsed["is_detained"] is True


def test_parse_detention_csv(app):
    with app.app_context():
        csv_data = """roll_no,student_prn,student_name,total_attended,total_conducted,percentage
1,241106001,Sangpal Amey Mukesh,85,90,94.44
9,241106010,Patil Kunal Sanjay,50,88,56.82
"""
        buf = io.BytesIO(csv_data.encode("utf-8"))
        res = parse_detention_file(buf, "test_detention.csv")
        assert res["total_records"] == 2
        assert res["detained_count"] == 1
        assert res["safe_count"] == 1
        assert res["records"][0]["student_prn"] == "241106001"
        assert res["records"][1]["student_prn"] == "241106010"
        assert res["records"][1]["is_detained"] is True


def test_commit_detention_records(app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()

        test_records = [
            {
                "roll_no": 9,
                "student_prn": "241106010",
                "percentage": 78.50,
                "total_attended": 70,
                "total_conducted": 89,
                "is_detained": False
            }
        ]

        commit_res = commit_detention_records(test_records, actor_prn="ADMIN_TEST")
        assert commit_res["status"] == "success"
        assert commit_res["updated_count"] == 1

        # Check attendance_records
        att = db.attendance_records.find_one({"student_prn": "241106010"})
        assert att is not None
        assert att["percentage"] == 78.50
        assert att["is_detained"] is False
        assert att["total_attended"] == 70

        # Check user profile
        usr = db.users.find_one({"prn_roll": "241106010"})
        assert usr["attendance_percentage"] == 78.50
        assert usr["is_detained"] is False


def test_reupload_detention_list_http_routes(client, app):
    # 1. Unauthenticated gets redirected
    res_unauth = client.get("/attendance/reupload-detention-list")
    assert res_unauth.status_code in [302, 401]

    # 2. Login as admin
    client.post("/auth/login", data={"email": "admin", "password": "Admin@12345"}, follow_redirects=True)

    # 3. GET form
    res_get = client.get("/attendance/reupload-detention-list")
    assert res_get.status_code == 200
    assert b"Re-upload Detention List" in res_get.data

    # 4. POST commit
    staged = [
        {
            "roll_no": 5,
            "student_prn": "241106005",
            "percentage": 82.50,
            "total_attended": 75,
            "total_conducted": 90,
            "is_detained": False
        }
    ]
    res_commit = client.post(
        "/attendance/reupload-detention-list",
        data={
            "action": "commit",
            "staged_records": json.dumps(staged)
        },
        follow_redirects=True
    )
    assert res_commit.status_code == 200
    assert b"Successfully updated attendance" in res_commit.data
