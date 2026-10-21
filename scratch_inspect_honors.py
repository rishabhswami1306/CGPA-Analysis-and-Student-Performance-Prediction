from app import get_db

db = get_db()
users = list(db.users.find({"role": "student"}))
att_records = list(db.attendance_records.find())

print(f"Total students: {len(users)}, Total attendance records: {len(att_records)}")

# Find students with honors in users or attendance
honors_students = []
for u in users:
    h = u.get("honors_course")
    if h:
        honors_students.append((u["prn_roll"], u.get("name"), h))

print(f"Honors students count: {len(honors_students)}")
for prn, name, h in honors_students[:10]:
    print(f"  PRN: {prn} | Name: {name} | Honors: {h}")

# Check attendance records for these PRNs
att_with_honors = [a for a in att_records if a.get("honors_course")]
print(f"Attendance records with honors: {len(att_with_honors)}")
for a in att_with_honors[:5]:
    subjs = list(a.get("subjects", {}).keys())
    print(f"  PRN: {a.get('student_prn')} | Honors: {a.get('honors_course')} | Subjects: {subjs}")
