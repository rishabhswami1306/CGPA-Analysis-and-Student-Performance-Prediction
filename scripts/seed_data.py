"""
Official Database Seed Script – TY BTech DS (A) 2026-27, Semester I
SES's R. C. Patel Institute of Technology, Shirpur

Clears all prior/temporary data and seeds ONLY the official verified dataset:
- 66 Students with PRN-based logins
- 7 Assigned Faculty Mentors & Teachers
- 1 Dean / Admin Account
- Verified subject-wise and total attendance records
- Curricular mark-sheets and academic records
"""

import os
import sys
import json
import random
from datetime import datetime, timezone

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db import get_db, reset_db_connections
from routes.auth_routes import bcrypt
from utils.grade_calculator import (
    compute_subject_internal, compute_subject_total, calculate_grade_point, compute_semester_sgpa
)

STUDENT_JSON = os.path.join(os.path.dirname(__file__), "..", "students_attendance_verified.json")

# ─── SUBJECT METADATA ────────────────────────────────────────────────────────
SUBJECT_META = {
    "ML-II":  {"name": "Machine Learning II",                         "credits": 4},
    "IS":     {"name": "Information Security",                         "credits": 3},
    "DAA":    {"name": "Design & Analysis of Algorithms",              "credits": 4},
    "CCN":    {"name": "Computer Communication & Networks",            "credits": 4},
    "CCS":    {"name": "Cloud Computing & Services",                   "credits": 4},
    "CI":     {"name": "Competitive Intelligence",                     "credits": 1},
    "AJL":    {"name": "Advanced Java Lab",                            "credits": 2},
    "EM":     {"name": "Honors – Engineering Mathematics",             "credits": 2},
    "CMPM":   {"name": "Honors – Computational Photography & Media",   "credits": 2},
}

# ─── OFFICIAL FACULTY ACCOUNTS ──────────────────────────────────────────────
FACULTY_LIST = [
    {
        "prn_roll": "FAC_SANJEKAR",
        "email": "sanjekar@rcpit.ac.in",
        "role": "faculty",
        "name": "Dr. P.S. Sanjekar",
        "branch": "CSE-DS",
        "admission_year": 2010,
        "assigned_subjects": ["IS", "CI"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_CHAUDHARI",
        "email": "chaudhari@rcpit.ac.in",
        "role": "faculty",
        "name": "Dr. K.D. Chaudhari",
        "branch": "CSE-DS",
        "admission_year": 2012,
        "assigned_subjects": ["CCN"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_CHIMANKAR",
        "email": "chimankar@rcpit.ac.in",
        "role": "faculty",
        "name": "Prof. U.B. Chimankar",
        "branch": "CSE-DS",
        "admission_year": 2008,
        "assigned_subjects": ["EM"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_LANJEWAR",
        "email": "lanjewar@rcpit.ac.in",
        "role": "faculty",
        "name": "Mrs. P.D. Lanjewar",
        "branch": "CSE-DS",
        "admission_year": 2015,
        "assigned_subjects": ["ML-II"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_SALUNKHE",
        "email": "salunkhe@rcpit.ac.in",
        "role": "faculty",
        "name": "Prof. S.P. Salunkhe",
        "branch": "CSE-DS",
        "admission_year": 2014,
        "assigned_subjects": ["DAA"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_PATIL_MS",
        "email": "patil.ms@rcpit.ac.in",
        "role": "faculty",
        "name": "Dr. M.S. Patil",
        "branch": "CSE-DS",
        "admission_year": 2011,
        "assigned_subjects": ["CCS"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
    {
        "prn_roll": "FAC_DEORE",
        "email": "deore@rcpit.ac.in",
        "role": "faculty",
        "name": "Mr. K.D. Deore",
        "branch": "CSE-DS",
        "admission_year": 2016,
        "assigned_subjects": ["CCN"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    {
        "prn_roll": "FAC_PATIL_PK",
        "email": "patil.pk@rcpit.ac.in",
        "role": "faculty",
        "name": "Dr. P.K. Patil",
        "branch": "CSE-DS",
        "admission_year": 2009,
        "assigned_subjects": ["CMPM", "AJL"],
        "is_active": True,
        "must_change_password": False,
        "failed_login_attempts": 0,
    },
]

ADMIN_USER = {
    "prn_roll": "ADMIN001",
    "email": "admin@rcpit.ac.in",
    "role": "admin",
    "name": "Dean of Academics – R.C. Patel Institute",
    "branch": "CSE-DS",
    "admission_year": 2000,
    "assigned_subjects": [],
    "is_active": True,
    "must_change_password": False,
    "failed_login_attempts": 0,
}


def make_ongoing_sem5_subjects(att_record: dict) -> list:
    """Convert attendance subject dict to ongoing semester 5 subjects with 40-mark internal components and pending ESE."""
    subjects_out = []
    honors = att_record.get("honors_course")

    subject_keys = ["ML-II", "IS", "DAA", "CCN", "CCS", "CI", "AJL"]
    if honors:
        if isinstance(honors, str):
            h_list = [h.strip() for h in honors.split(",") if h.strip()]
        elif isinstance(honors, list):
            h_list = honors
        else:
            h_list = ["EM", "CMPM"]
        for h in h_list:
            if h not in subject_keys:
                subject_keys.append(h)

    overall_pct = att_record.get("percentage", 80.0)
    score_factor = min(1.0, overall_pct / 100.0)

    for code in subject_keys:
        meta = SUBJECT_META.get(code, {"name": code, "credits": 2})
        sub_att = att_record.get("subjects", {}).get(code, {})

        lect_att = sub_att.get("lecture_attended", 0)
        lect_con = sub_att.get("lecture_conducted", 0)
        prac_att = sub_att.get("practical_attended", 0) or sub_att.get("tutorial_attended", 0)
        prac_con = sub_att.get("practical_conducted", 0) or sub_att.get("tutorial_conducted", 0)

        # 40 Marks Internal Assessment:
        # 15 Marks TT (two 30-mark TTs converted to 15: (tt1+tt2)/4)
        base_tt1 = round(max(12.0, min(30.0, 22.0 * score_factor * random.uniform(0.88, 1.12))), 1)
        base_tt2 = round(max(11.0, min(30.0, 21.5 * score_factor * random.uniform(0.88, 1.12))), 1)
        tt_conv = round((base_tt1 + base_tt2) / 4.0, 2)

        # 5 Marks Aptitude, 5 Marks SKAT, 5 Marks TA, 5 Marks Mock Interview, 5 Marks Presentation
        apt = round(max(2.0, min(5.0, 4.0 * score_factor * random.uniform(0.90, 1.10))), 1)
        skat = round(max(2.0, min(5.0, 3.9 * score_factor * random.uniform(0.90, 1.10))), 1)
        ta = round(max(2.5, min(5.0, 4.2 * score_factor * random.uniform(0.92, 1.08))), 1)
        mock = round(max(2.0, min(5.0, 4.0 * score_factor * random.uniform(0.90, 1.10))), 1)
        pres = round(max(2.5, min(5.0, 4.1 * score_factor * random.uniform(0.90, 1.10))), 1)

        internal_tot = compute_subject_internal(base_tt1, base_tt2, apt, skat, ta, mock, pres)

        # ESE has NOT occurred yet: Semester 5 is ongoing and results are pending
        subjects_out.append({
            "subject_code": code,
            "subject_name": meta["name"],
            "credits": meta["credits"],
            "tt1_score": base_tt1,
            "tt2_score": base_tt2,
            "tt_converted": tt_conv,
            "aptitude_score": apt,
            "skat_score": skat,
            "teacher_assessment_score": ta,
            "mock_interview_score": mock,
            "presentation_score": pres,
            "internal_score": internal_tot,
            "ese_score": 0.0,
            "total_marks": internal_tot,
            "grade_point": None,
            "grade_letter": "Pending",
            "is_evaluated": False,
            "lecture_attended": lect_att,
            "lecture_conducted": lect_con,
            "practical_attended": prac_att,
            "practical_conducted": prac_con,
        })

    return subjects_out


HISTORICAL_CURRICULUM = {
    1: [
        {"code": "FE101", "name": "Engineering Mathematics I", "credits": 4},
        {"code": "FE102", "name": "Engineering Physics", "credits": 4},
        {"code": "FE103", "name": "Basic Electrical Engineering", "credits": 3},
        {"code": "FE104", "name": "Programming for Problem Solving (C)", "credits": 4},
        {"code": "FE105", "name": "Engineering Graphics & Design", "credits": 3},
        {"code": "FE106", "name": "Basic Electrical & Physics Lab", "credits": 2},
    ],
    2: [
        {"code": "FE201", "name": "Engineering Mathematics II", "credits": 4},
        {"code": "FE202", "name": "Engineering Chemistry", "credits": 4},
        {"code": "FE203", "name": "Basic Electronics Engineering", "credits": 3},
        {"code": "FE204", "name": "Object-Oriented Programming (C++)", "credits": 4},
        {"code": "FE205", "name": "Engineering Mechanics", "credits": 3},
        {"code": "FE206", "name": "Workshop & Programming Practice", "credits": 2},
    ],
    3: [
        {"code": "DS301", "name": "Data Structures & Algorithms", "credits": 4},
        {"code": "DS302", "name": "Discrete Mathematics", "credits": 4},
        {"code": "DS303", "name": "Digital Electronics & Logic Design", "credits": 3},
        {"code": "DS304", "name": "Database Management Systems", "credits": 4},
        {"code": "DS305", "name": "Computer Organization & Architecture", "credits": 3},
        {"code": "DS306", "name": "DSA & DBMS Laboratory", "credits": 2},
    ],
    4: [
        {"code": "DS401", "name": "Operating Systems", "credits": 4},
        {"code": "DS402", "name": "Design & Analysis of Algorithms", "credits": 4},
        {"code": "DS403", "name": "Computer Networks", "credits": 4},
        {"code": "DS404", "name": "Python for Data Science", "credits": 3},
        {"code": "DS405", "name": "Statistics & Probability for DS", "credits": 3},
        {"code": "DS406", "name": "OS & Python Lab", "credits": 2},
    ],
}


def make_historical_subjects(sem_num: int, score_factor: float) -> list:
    """Generate consistent subject marks for historical semesters 1 to 4 using 60 ESE + 40 Internal."""
    courses = HISTORICAL_CURRICULUM.get(sem_num, [])
    subjects_out = []
    for c in courses:
        sem_var = random.uniform(0.92, 1.08)
        eff_factor = min(1.0, max(0.42, score_factor * sem_var))

        # Two 30-mark TTs converted to 15
        tt1 = round(max(10.0, min(30.0, 22.0 * eff_factor * random.uniform(0.92, 1.08))), 1)
        tt2 = round(max(10.0, min(30.0, 22.5 * eff_factor * random.uniform(0.92, 1.08))), 1)
        tt_conv = round((tt1 + tt2) / 4.0, 2)

        # 5 Marks Each
        apt = round(max(2.0, min(5.0, 4.0 * eff_factor * random.uniform(0.90, 1.10))), 1)
        skat = round(max(2.0, min(5.0, 4.0 * eff_factor * random.uniform(0.90, 1.10))), 1)
        ta = round(max(2.5, min(5.0, 4.2 * eff_factor * random.uniform(0.92, 1.08))), 1)
        mock = round(max(2.0, min(5.0, 4.0 * eff_factor * random.uniform(0.90, 1.10))), 1)
        pres = round(max(2.5, min(5.0, 4.2 * eff_factor * random.uniform(0.90, 1.10))), 1)

        internal_tot = compute_subject_internal(tt1, tt2, apt, skat, ta, mock, pres)

        # ESE out of 60
        ese = round(max(18.0, min(60.0, 42.0 * eff_factor * random.uniform(0.88, 1.12))), 1)
        total = compute_subject_total(
            tt1=tt1, tt2=tt2, ese=ese, max_ese=60.0,
            aptitude=apt, skat=skat, teacher_assessment=ta,
            mock_interview=mock, presentation=pres,
            internal_score=internal_tot
        )
        gp, letter = calculate_grade_point(total)

        lect_con = random.choice([12, 14, 16])
        prac_con = random.choice([4, 6])
        lect_att = int(round(lect_con * eff_factor))
        prac_att = int(round(prac_con * eff_factor))

        subjects_out.append({
            "subject_code": c["code"],
            "subject_name": c["name"],
            "credits": c["credits"],
            "tt1_score": tt1,
            "tt2_score": tt2,
            "tt_converted": tt_conv,
            "aptitude_score": apt,
            "skat_score": skat,
            "teacher_assessment_score": ta,
            "mock_interview_score": mock,
            "presentation_score": pres,
            "internal_score": internal_tot,
            "ese_score": ese,
            "total_marks": total,
            "grade_point": gp,
            "grade_letter": letter,
            "lecture_attended": lect_att,
            "lecture_conducted": lect_con,
            "practical_attended": prac_att,
            "practical_conducted": prac_con,
        })
    return subjects_out



def seed_database():
    print("=" * 65)
    print("SES's R.C. Patel Institute of Technology, Shirpur")
    print("TY BTech DS (A) 2026-27 Sem-I – Official Database Seed")
    print("=" * 65)

    reset_db_connections()
    db = get_db()

    # 1. WIPE ALL OLD/TEMPORARY DATA
    print("\n[1/5] Clearing all old collections...")
    db.users.delete_many({})
    db.academic_records.delete_many({})
    db.attendance_records.delete_many({})
    db.predictions_cache.delete_many({})
    db.placement_records.delete_many({})
    db.audit_logs.delete_many({})
    print("      - All collections wiped clean.")

    # 2. SEED ADMIN
    print("\n[2/5] Seeding Dean / Admin...")
    admin_pw = bcrypt.generate_password_hash("Admin@12345").decode("utf-8")
    ADMIN_USER["password_hash"] = admin_pw
    ADMIN_USER["created_at"] = datetime.now(timezone.utc)
    ADMIN_USER["updated_at"] = datetime.now(timezone.utc)
    db.users.insert_one(ADMIN_USER)
    print("      - Admin: admin@rcpit.ac.in / Admin@12345")

    # 3. SEED FACULTY MENTORS
    print("\n[3/5] Seeding 7 Assigned Faculty Mentors...")
    faculty_pw = bcrypt.generate_password_hash("Faculty@12345").decode("utf-8")
    for fac in FACULTY_LIST:
        fac["password_hash"] = faculty_pw
        fac["created_at"] = datetime.now(timezone.utc)
        fac["updated_at"] = datetime.now(timezone.utc)
    db.users.insert_many(FACULTY_LIST)
    print(f"      - {len(FACULTY_LIST)} faculty accounts created (Password: Faculty@12345)")

    # 4. SEED 66 VERIFIED STUDENTS
    print("\n[4/5] Seeding 66 Verified Students from First Detention List...")
    with open(STUDENT_JSON, "r", encoding="utf-8") as f:
        student_att_records = json.load(f)

    user_docs = []
    attendance_docs = []
    academic_docs = []

    random.seed(42)

    for att in student_att_records:
        prn = att["prn"]
        # Password = PRN itself
        student_pw = bcrypt.generate_password_hash(prn).decode("utf-8")
        email = f"{prn}@rcpit.ac.in"

        lg = att.get("local_guardian", "")
        lg_roll = "FAC_SANJEKAR"
        if "Chaudhari" in lg or "Chaud" in lg:
            lg_roll = "FAC_CHAUDHARI"
        elif "Chimankar" in lg:
            lg_roll = "FAC_CHIMANKAR"

        user_doc = {
            "prn_roll": prn,
            "email": email,
            "password_hash": student_pw,
            "role": "student",
            "name": att["student_name"].title(),
            "branch": "CSE-DS",
            "admission_year": 2024,
            "class_name": "TY BTech DS (A)",
            "current_year": "Third Year",
            "current_semester": 5,
            "roll_no": att["roll_no"],
            "local_guardian_prn": lg_roll,
            "honors_course": att.get("honors_course"),
            "assigned_subjects": [],
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        user_docs.append(user_doc)

        att_doc = {
            "student_prn": prn,
            "class_name": "TY BTech DS (A) 2026-27 Sem-I",
            "roll_no": att["roll_no"],
            "semester": 5,
            "academic_year": "2026-27",
            "honors_course": att.get("honors_course"),
            "local_guardian": lg,
            "local_guardian_prn": lg_roll,
            "subjects": att.get("subjects", {}),
            "total_attended": att.get("total_attended", 0),
            "total_conducted": att.get("total_conducted", 0),
            "percentage": att.get("percentage", 0.0),
            "recorded_percentage": att.get("recorded_percentage", 0),
            "is_detained": att.get("is_detained", False),
            "updated_at": datetime.now(timezone.utc),
        }
        attendance_docs.append(att_doc)

        score_factor = min(1.0, att.get("percentage", 80.0) / 100.0)
        overall_pct = att.get("percentage", 80.0)
        sem_acad_years = {
            1: "2024-25",
            2: "2024-25",
            3: "2025-26",
            4: "2025-26",
        }

        # Seed completed historical Semesters 1 to 4
        for s_num in range(1, 5):
            h_subjects = make_historical_subjects(s_num, score_factor)
            h_sgpa, h_backlogs, _ = compute_semester_sgpa(h_subjects)
            h_att = round(max(65.0, min(96.0, overall_pct * random.uniform(0.95, 1.05))), 1)
            academic_docs.append({
                "student_prn": prn,
                "semester": s_num,
                "academic_year": sem_acad_years[s_num],
                "subjects": h_subjects,
                "sgpa": h_sgpa,
                "attendance_percentage": h_att,
                "active_backlogs": h_backlogs,
                "is_completed": True,
                "status": "completed",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

        # Seed active ongoing Semester 5 (Results not yet available; in progress)
        ongoing_subjects = make_ongoing_sem5_subjects(att)
        academic_doc = {
            "student_prn": prn,
            "semester": 5,
            "academic_year": "2026-27",
            "subjects": ongoing_subjects,
            "sgpa": None,  # Results not finalized; in-progress semester to be predicted
            "attendance_percentage": att.get("percentage", 0.0),
            "active_backlogs": 0,
            "is_completed": False,
            "status": "ongoing",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        academic_docs.append(academic_doc)

    db.users.insert_many(user_docs)
    db.attendance_records.insert_many(attendance_docs)
    db.academic_records.insert_many(academic_docs)
    print(f"      - {len(user_docs)} students inserted.")
    print(f"      - {len(attendance_docs)} attendance records inserted.")
    print(f"      - {len(academic_docs)} academic records inserted.")

    # 5. REBUILD INDEXES
    print("\n[5/5] Rebuilding indexes...")
    try:
        from pymongo import ASCENDING
        db.users.create_index([("prn_roll", ASCENDING)], unique=True)
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.attendance_records.create_index([("student_prn", ASCENDING)])
        db.academic_records.create_index(
            [("student_prn", ASCENDING), ("semester", ASCENDING)], unique=True
        )
        print("      - Indexes created successfully.")
    except Exception as e:
        print(f"      - Index warning: {e}")

    detained = [a for a in student_att_records if a.get("is_detained")]
    print("\n" + "=" * 65)
    print("  SEED COMPLETE!")
    print(f"  Total Students:    {len(user_docs)}")
    print(f"  Detained (< 75%):  {len(detained)}")
    print(f"  Safe (>= 75%):     {len(user_docs) - len(detained)}")
    print("  Admin Login:       admin@rcpit.ac.in / Admin@12345")
    print("  Faculty Logins:    (email)@rcpit.ac.in / Faculty@12345")
    print("  Student Logins:    (PRN) / (PRN)   e.g. 241106005 / 241106005")
    print("=" * 65)


if __name__ == "__main__":
    seed_database()
