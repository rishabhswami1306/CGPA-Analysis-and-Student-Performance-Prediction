import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone
import random
from utils.db import get_db
from utils.grade_calculator import compute_cumulative_cgpa, compute_subject_internal, compute_subject_total, calculate_grade_point, compute_semester_sgpa
from scripts.seed_data import HISTORICAL_CURRICULUM, make_ongoing_sem5_subjects
from ml_engine.inference import predict_student_analytics

db = get_db()
prn = "241106005"
score_factor = 0.81  # ~8.1 SGPA range

# 1. Update Sem 3 real marksheet record
sem3_rec = db.academic_records.find_one({"student_prn": prn, "semester": 3})
if sem3_rec:
    subs = sem3_rec.get("subjects", [])
    for s in subs:
        ca = float(s.get("ca_marks", 0.0))
        ese = float(s.get("ese_marks", 0.0))
        tot = float(s.get("total_marks", ca + ese))
        s["course_code"] = s.get("subject_code")
        s["course_name"] = s.get("subject_name")
        s["internal_score"] = ca
        s["total_internal_40"] = ca
        s["ese_score"] = ese
        s["total_100"] = tot
        s["tt_converted"] = round(ca * 0.5, 2)
        s["tt1_score"] = round(ca * 0.75, 1)
        s["tt2_score"] = round(ca * 0.75, 1)
    db.academic_records.update_one(
        {"_id": sem3_rec["_id"]},
        {"$set": {
            "subjects": subs,
            "courses": subs,
            "attendance_percentage": 78.0,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    print("Updated Sem 3 real marksheet record.")

# 2. Ensure Sem 1, 2, 4 exist
for sem in [1, 2, 4]:
    existing = db.academic_records.find_one({"student_prn": prn, "semester": sem})
    if not existing:
        courses = HISTORICAL_CURRICULUM.get(sem, [])
        sem_subs = []
        for c in courses:
            eff = min(1.0, max(0.6, score_factor * random.uniform(0.96, 1.04)))
            tt1 = round(21.0 * eff, 1)
            tt2 = round(22.0 * eff, 1)
            tt_conv = round((tt1 + tt2) / 4.0, 2)
            apt = 4.0
            skat = 4.0
            ta = 4.0
            mock = 4.0
            pres = 4.0
            internal = compute_subject_internal(tt1, tt2, apt, skat, ta, mock, pres)
            ese = round(44.0 * eff, 1)
            tot = compute_subject_total(tt1=tt1, tt2=tt2, ese=ese, max_ese=60.0, aptitude=apt, skat=skat, teacher_assessment=ta, mock_interview=mock, presentation=pres, internal_score=internal)
            gp, letter = calculate_grade_point(tot)
            sem_subs.append({
                "subject_code": c["code"],
                "course_code": c["code"],
                "subject_name": c["name"],
                "course_name": c["name"],
                "credits": c["credits"],
                "tt1_score": tt1,
                "tt2_score": tt2,
                "tt_converted": tt_conv,
                "aptitude_score": apt,
                "skat_score": skat,
                "teacher_assessment_score": ta,
                "mock_interview_score": mock,
                "presentation_score": pres,
                "internal_score": internal,
                "total_internal_40": internal,
                "ese_score": ese,
                "ese_marks": ese,
                "total_marks": tot,
                "total_100": tot,
                "grade_point": gp,
                "grade_letter": letter
            })
        sgpa, backlogs, creds = compute_semester_sgpa(sem_subs)
        db.academic_records.insert_one({
            "student_prn": prn,
            "semester": sem,
            "academic_year": f"202{3 + (sem-1)//2}-2{4 + (sem-1)//2}",
            "subjects": sem_subs,
            "courses": sem_subs,
            "sgpa": sgpa,
            "active_backlogs": backlogs,
            "credits_earned": creds,
            "attendance_percentage": 80.0,
            "is_completed": True,
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        print(f"Inserted historical Semester {sem} record (SGPA: {sgpa}).")

# 3. Ensure Ongoing Semester 5 exists
existing_sem5 = db.academic_records.find_one({"student_prn": prn, "semester": 5})
if not existing_sem5:
    att_mock = {"percentage": 78.0, "total_conducted": 140, "total_attended": 109}
    sem5_subs = make_ongoing_sem5_subjects(att_mock)
    for s in sem5_subs:
        s["course_code"] = s["subject_code"]
        s["course_name"] = s["subject_name"]
        s["total_internal_40"] = s.get("internal_score", 0.0)
        s["total_100"] = s.get("total_marks", 0.0)
    db.academic_records.insert_one({
        "student_prn": prn,
        "semester": 5,
        "academic_year": "2026-27",
        "subjects": sem5_subs,
        "courses": sem5_subs,
        "sgpa": None,
        "attendance_percentage": 78.0,
        "active_backlogs": 0,
        "is_completed": False,
        "status": "ongoing",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    print("Inserted ongoing Semester 5 record.")

# 4. Ensure attendance record
db.attendance_records.update_one(
    {"student_prn": prn},
    {"$set": {
        "student_prn": prn,
        "student_name": "Rishabh Swami",
        "semester": 5,
        "total_conducted": 140,
        "total_attended": 109,
        "percentage": 78.0,
        "attendance_percentage": 78.0,
        "bunk_safe_lectures": 3,
        "lectures_needed": 0,
        "is_critical": False,
        "status": "Safe (Above 75%)",
        "updated_at": datetime.now(timezone.utc)
    }},
    upsert=True
)

# 5. Recompute cumulative CGPA
completed = list(db.academic_records.find({"student_prn": prn, "semester": {"$lte": 4}, "is_completed": True}).sort("semester", 1))
cgpa, backlogs, creds = compute_cumulative_cgpa(completed)
db.users.update_one(
    {"prn_roll": prn},
    {"$set": {
        "cgpa": cgpa,
        "active_backlogs": backlogs,
        "credits_earned": creds,
        "current_semester": 5,
        "current_year": "Third Year",
        "class_name": "TY BTech DS (A)",
        "branch": "Computer Science and Engineering (Data Science)",
        "attendance_percentage": 78.0,
        "updated_at": datetime.now(timezone.utc)
    }}
)
print(f"User profile updated: CGPA={cgpa}, credits={creds}, sem=5")

# 6. Re-predict analytics
pred = predict_student_analytics(prn, force_recalculate=True)
print("Predictions updated successfully:", pred.get("predicted_next_sgpa"), "target sem:", pred.get("target_semester"))
print("ALL DONE SUCCESSFULLY!")
