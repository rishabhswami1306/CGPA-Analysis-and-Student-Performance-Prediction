import json
from datetime import datetime, timezone
from utils.db import get_db
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt()

def migrate_honors():
    # 1. Update students_attendance_verified.json
    json_path = "students_attendance_verified.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_prns = []
    for s in data:
        raw_honors = s.get("honors_course")
        if raw_honors == "EM" or (raw_honors and "EM" in raw_honors and "CMPM" not in raw_honors):
            s["honors_course"] = "EM, CMPM"
            if "CMPM" not in s.get("subjects", {}):
                pct = s.get("percentage", 80.0)
                cmpm_att = min(9, max(0, round(9 * (pct / 100.0))))
                s.setdefault("subjects", {})["CMPM"] = {
                    "lecture_attended": cmpm_att,
                    "lecture_conducted": 9
                }
                s["total_conducted"] = s.get("total_conducted", 98) + 9
                s["total_attended"] = s.get("total_attended", 80) + cmpm_att
                s["percentage"] = round((s["total_attended"] / s["total_conducted"]) * 100, 2)
                s["recorded_percentage"] = round(s["percentage"])
                s["is_detained"] = s["percentage"] < 75.0
            updated_prns.append((s["prn"], s))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {len(updated_prns)} students in {json_path}")

    # 2. Update MongoDB
    db = get_db()
    for prn, s in updated_prns:
        # Update attendance_records
        db.attendance_records.update_one(
            {"student_prn": prn},
            {
                "$set": {
                    "honors_course": "EM, CMPM",
                    "subjects.CMPM": s["subjects"]["CMPM"],
                    "total_attended": s["total_attended"],
                    "total_conducted": s["total_conducted"],
                    "percentage": s["percentage"],
                    "recorded_percentage": s["recorded_percentage"],
                    "is_detained": s["is_detained"],
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )

        # Update users
        db.users.update_one(
            {"prn_roll": prn},
            {
                "$set": {
                    "honors_course": "EM, CMPM",
                    "attendance_percentage": s["percentage"],
                    "is_detained": s["is_detained"],
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )

        # Update ongoing semester 5 academic_records if CMPM is missing
        sem5_rec = db.academic_records.find_one({"student_prn": prn, "semester": 5})
        if sem5_rec:
            existing_subs = sem5_rec.get("subjects", [])
            has_cmpm = any(sub.get("subject_code") == "CMPM" for sub in existing_subs)
            if not has_cmpm:
                score_factor = min(1.0, s["percentage"] / 100.0)
                tt1 = round(max(12.0, min(30.0, 22.0 * score_factor)), 1)
                tt2 = round(max(11.0, min(30.0, 21.5 * score_factor)), 1)
                tt_conv = round((tt1 + tt2) / 4.0, 2)
                apt = round(max(2.0, min(5.0, 4.0 * score_factor)), 1)
                skat = round(max(2.0, min(5.0, 3.9 * score_factor)), 1)
                ta = round(max(2.5, min(5.0, 4.2 * score_factor)), 1)
                mock = round(max(2.0, min(5.0, 4.0 * score_factor)), 1)
                pres = round(max(2.5, min(5.0, 4.1 * score_factor)), 1)
                internal = round(tt_conv + apt + skat + ta + mock + pres, 2)

                cmpm_entry = {
                    "subject_code": "CMPM",
                    "subject_name": "Honors – Computational Photography & Media",
                    "credits": 2,
                    "tt1_score": tt1,
                    "tt2_score": tt2,
                    "tt_converted": tt_conv,
                    "aptitude_score": apt,
                    "skat_score": skat,
                    "teacher_assessment_score": ta,
                    "mock_interview_score": mock,
                    "presentation_score": pres,
                    "internal_score": internal,
                    "ese_score": 0.0,
                    "total_marks": internal,
                    "grade_point": None,
                    "grade_letter": "Pending",
                    "is_evaluated": False,
                    "lecture_attended": s["subjects"]["CMPM"]["lecture_attended"],
                    "lecture_conducted": s["subjects"]["CMPM"]["lecture_conducted"],
                    "practical_attended": 0,
                    "practical_conducted": 0,
                }
                existing_subs.append(cmpm_entry)
                db.academic_records.update_one(
                    {"_id": sem5_rec["_id"]},
                    {"$set": {"subjects": existing_subs, "attendance_percentage": s["percentage"]}}
                )

    # 3. Ensure Dr. P.K. Patil faculty account exists
    patil = db.users.find_one({"prn_roll": "FAC_PATIL_PK"})
    if not patil:
        db.users.insert_one({
            "prn_roll": "FAC_PATIL_PK",
            "email": "patil.pk@rcpit.ac.in",
            "password_hash": bcrypt.generate_password_hash("Faculty@12345").decode("utf-8"),
            "role": "faculty",
            "name": "Dr. P.K. Patil",
            "branch": "CSE-DS",
            "admission_year": 2009,
            "assigned_subjects": ["CMPM", "AJL"],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        print("Created Dr. P.K. Patil faculty account.")
    else:
        db.users.update_one(
            {"prn_roll": "FAC_PATIL_PK"},
            {"$set": {"assigned_subjects": ["CMPM", "AJL"]}}
        )

    print("Migration complete!")

if __name__ == "__main__":
    migrate_honors()
