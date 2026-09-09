"""
Attendance Engine: Academic Calendar, Timetable & Predictive Analytics
SES's R. C. Patel Institute of Technology, Shirpur
TY BTech DS (A) - Academic Year 2026-27, Semester I (Odd)
"""

import math
from datetime import date, timedelta

# ─── ACADEMIC CALENDAR CONSTANTS ────────────────────────────────────────────
SEM_START = date(2026, 7, 20)
SEM_END   = date(2026, 11, 6)     # Teaching end (Term-work deadline)

# Holidays (no classes held on these dates)
HOLIDAYS = {
    date(2026, 8, 15),   # Independence Day
    date(2026, 8, 26),   # Eid-e-Milad (approx)
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
}

# Term Test weeks – no regular lectures (approx)
TERM_TEST_DAYS = {
    date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2),    # TT-1
    date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24), # TT-2
}

NO_CLASS_DATES = HOLIDAYS | TERM_TEST_DAYS

# ─── TIMETABLE: Weekly lecture/practical slots per subject ──────────────────
# Format: day -> list of (subject_code, session_type, batch)
# Days: 0=Mon,1=Tue,2=Wed,3=Thu,4=Fri,5=Sat
# Session types: 'L' lecture, 'P' practical, 'T' tutorial

TIMETABLE = {
    # Monday
    0: [
        ("HONORS", "L", None),   # 11:40-12:30 Honors (CMPM or EM – student dependent)
        ("ML-II",  "P", "T1"),   # 12:30-01:20
        ("ML-II",  "P", "T1"),   # 01:20-02:10 (2-hr practical slot)
        ("DAA",    "L", None),   # 02:20-03:10
        ("CCN",    "L", None),   # 03:10-04:00
        ("CCS",    "L", None),   # 04:10-05:00
        ("CI",     "L", None),   # 05:00-05:50
    ],
    # Tuesday
    1: [
        ("HONORS", "L", None),   # Honors CMPM
        ("DAA",    "P", "T1"),   # 12:30-01:20
        ("CCN",    "P", "T1"),   # (combined slot)
        ("CCS",    "P", "T1"),   # CCS, CCN, AJL practicals spread across batches
        ("CCN",    "P", "T2"),
        ("AJL",    "P", "T3"),
        ("CCS",    "L", None),   # 04:10-05:00
        ("IS",     "L", None),   # 05:00-05:50
    ],
    # Wednesday
    2: [
        ("HONORS", "L", None),
        ("AJL",    "P", "T1"),   # 12:30-01:20
        ("IS",     "P", "T2"),   # (practicals)
        ("IS",     "L", None),   # 02:20-03:10
        ("DAA",    "L", None),   # 03:10-04:00
        ("ML-II",  "L", None),   # 04:10-05:00
        ("CCN",    "L", None),   # 05:00-05:50
    ],
    # Thursday
    3: [
        ("HONORS", "L", None),   # Honors EM
        ("CCN",    "P", "T1"),
        ("ML-II",  "P", "T2"),
        ("DAA",    "P", "T2"),
        ("ML-II",  "L", None),   # 02:20-03:10
        ("CCS",    "L", None),   # 03:10-04:00
        ("AJL",    "P", "T1"),   # 04:10-05:00
        ("CCS",    "P", "T3"),   # 05:00-05:50 (TH+PR combined)
    ],
    # Friday
    4: [
        ("HONORS", "L", None),   # Honors EM
        ("IS",     "P", "T1"),
        ("DAA",    "P", "T2"),
        ("AJL",    "P", "T2"),
        ("CCN",    "L", None),   # 02:20-03:10
        ("ML-II",  "L", None),   # 03:10-04:00
        ("ML-II",  "L", None),   # 04:10-05:00
    ],
    # Saturday
    5: [
        ("HONORS", "L", None),   # Honors EM
        ("SEM_PROJECT", "L", None),  # Sem Project / LG meeting (12:30-02:10)
        ("SEM_PROJECT", "L", None),
        ("SEM_PROJECT", "L", None),  # 04:10-05:00
        ("SEM_PROJECT", "L", None),  # 05:00-05:50
    ],
}

# Simpler: THEORY lectures per subject per week (for attendance calculation)
# Based on official timetable image analysis
WEEKLY_THEORY_LECTURES = {
    "ML-II": 4,   # Mon+Wed+Thu+Fri
    "IS":    3,   # Wed+Fri (lectures) + Tue
    "DAA":   3,   # Mon+Wed+Thu
    "CCN":   4,   # Mon+Wed+Thu+Fri
    "CCS":   3,   # Mon+Tue+Thu
    "CI":    1,   # Mon (theory)
    "EM":    2,   # Honors Elective (Thu+Fri+Sat) 3 sessions
    "CMPM":  2,   # Honors Elective (Mon+Tue+Wed)
}

# Practicals per 2-week cycle (because batches T1/T2/T3 rotate)
FORTNIGHTLY_PRACTICALS = {
    "ML-II": 2,  # sessions per 2 weeks (each batch gets ~1 slot per fortnight)
    "IS":    2,
    "DAA":   2,
    "CCN":   2,
    "CCS":   2,
    "AJL":   2,
}

# Subjects in the semester (for TY DS A, 2026-27 Sem 1)
SUBJECTS = ["ML-II", "IS", "DAA", "CCN", "CCS", "CI"]
HONORS_SUBJECTS = ["EM", "CMPM"]   # One per student
PRACTICAL_SUBJECTS = ["ML-II", "IS", "DAA", "CCN", "CCS", "AJL"]

# Teaching staff
TEACHING_STAFF = {
    "ML-II": {"theory": "Mrs. P.D. Lanjewar", "practical": "Mrs. P.D. Lanjewar"},
    "DAA":   {"theory": "Prof. S.P. Salunkhe", "practical": "Prof. S.P. Salunkhe"},
    "IS":    {"theory": "Dr. P.S. Sanjekar",  "practical": "Dr. P.S. Sanjekar"},
    "CCS":   {"theory": "Dr. M.S. Patil",     "practical": "Dr. M.S. Patil"},
    "CCN":   {"theory": "Mr. K.D. Deore",     "practical": "Mr. K.D. Deore"},
    "CI":    {"theory": "Dr. P.S. Sanjekar",  "practical": None},
    "AJL":   {"theory": None, "practical": "PKP(T1&T3), Talware-T2"},
    "CMPM":  {"theory": "Dr. P.K. Patil",     "practical": None},
    "EM":    {"theory": "Prof. U.B. Chimankar", "practical": None},
}


# ─── CALENDAR UTILITIES ─────────────────────────────────────────────────────

def is_teaching_day(d: date) -> bool:
    """Returns True if the given date is a valid teaching day."""
    if d < SEM_START or d > SEM_END:
        return False
    if d.weekday() == 6:   # Sunday – no classes
        return False
    if d in NO_CLASS_DATES:
        return False
    return True


def count_teaching_days(start: date, end: date) -> int:
    """Count effective teaching days between two dates (inclusive)."""
    count = 0
    d = start
    while d <= end:
        if is_teaching_day(d):
            count += 1
        d += timedelta(days=1)
    return count


def count_teaching_weeks(start: date, end: date) -> float:
    """Approximate teaching weeks between two dates."""
    return count_teaching_days(start, end) / 5.0


def compute_remaining_lectures(as_of: date, subject: str, session_type: str = "theory") -> int:
    """
    Estimate remaining lectures/practicals from as_of to SEM_END for a subject.
    session_type: 'theory' or 'practical'
    """
    remaining_days = 0
    d = as_of + timedelta(days=1)  # Start from next day
    while d <= SEM_END:
        if is_teaching_day(d):
            remaining_days += 1
        d += timedelta(days=1)

    remaining_weeks = remaining_days / 5.0

    if session_type == "theory":
        rate = WEEKLY_THEORY_LECTURES.get(subject, 2)
        return round(remaining_weeks * rate)
    else:  # practical
        rate = FORTNIGHTLY_PRACTICALS.get(subject, 1)
        return round((remaining_weeks / 2.0) * rate)


def get_semester_milestones():
    """Return key academic calendar milestones for 2026-27 Sem I."""
    today = date.today()
    total_days = (SEM_END - SEM_START).days
    elapsed_days = max(0, (today - SEM_START).days)
    progress_pct = round(min(100, (elapsed_days / total_days) * 100), 1)

    milestones = [
        {"label": "Semester Begins", "date": "20 Jul 2026", "icon": "🎓", "done": True},
        {"label": "Independence Day", "date": "15 Aug 2026", "icon": "🇮🇳", "done": today > date(2026, 8, 15)},
        {"label": "Eid-e-Milad Holiday", "date": "26 Aug 2026", "icon": "🌙", "done": today > date(2026, 8, 26)},
        {"label": "Term Test 1", "date": "31 Aug – 2 Sep 2026", "icon": "📝", "done": today > date(2026, 9, 2)},
        {"label": "First Detention List", "date": "02 Sep 2026", "icon": "⚠️", "done": today > date(2026, 9, 2)},
        {"label": "Ganesh Chaturthi", "date": "14 Sep 2026", "icon": "🎉", "done": today > date(2026, 9, 14)},
        {"label": "Gandhi Jayanti", "date": "02 Oct 2026", "icon": "🕊️", "done": today > date(2026, 10, 2)},
        {"label": "Term Test 2", "date": "22–24 Oct 2026", "icon": "📝", "done": today > date(2026, 10, 24)},
        {"label": "Dussehra", "date": "20 Oct 2026", "icon": "🎊", "done": today > date(2026, 10, 20)},
        {"label": "Teaching Ends", "date": "06 Nov 2026", "icon": "🏁", "done": today > date(2026, 11, 6)},
        {"label": "End Semester Exam", "date": "Nov 2026 (TBD)", "icon": "📚", "done": False},
    ]

    return {
        "milestones": milestones,
        "progress_pct": progress_pct,
        "sem_start": SEM_START.strftime("%d %b %Y"),
        "sem_end": SEM_END.strftime("%d %b %Y"),
        "days_remaining": max(0, (SEM_END - today).days),
        "total_holidays": len(HOLIDAYS),
        "total_term_test_days": len(TERM_TEST_DAYS),
    }


# ─── ATTENDANCE PREDICTION ENGINE ───────────────────────────────────────────

def compute_subject_prediction(attended: int, conducted: int, remaining: int,
                                target_pct: float = 75.0) -> dict:
    """
    Core prediction algorithm for a single subject.
    Returns a rich prediction dict with must_attend, can_miss, achievability.
    """
    if conducted == 0:
        return {
            "current_pct": 0.0,
            "is_detained": True,
            "status": "No Data",
            "must_attend_now": 0,
            "can_miss_now": 0,
            "min_to_attend_remaining": remaining,
            "safe_bunks_remaining": 0,
            "max_achievable_pct": 0.0,
            "is_achievable": remaining > 0,
            "remaining_classes": remaining,
        }

    current_pct = round((attended / conducted) * 100, 2)
    is_detained = current_pct < target_pct

    # Max achievable if attending every remaining class
    max_achievable_pct = round(((attended + remaining) / (conducted + remaining)) * 100, 2) if (conducted + remaining) > 0 else current_pct

    if is_detained:
        # Must attend x consecutive classes to hit target_pct
        # (attended + x) / (conducted + x) >= target_pct/100
        # => attended + x >= (target_pct/100) * (conducted + x)
        # => 100*attended + 100*x >= target_pct * conducted + target_pct * x
        # => x(100 - target_pct) >= target_pct * conducted - 100 * attended
        # => x >= (target_pct * conducted - 100 * attended) / (100 - target_pct)
        numerator = target_pct * conducted - 100.0 * attended
        denominator = 100.0 - target_pct
        must_attend_now = max(0, math.ceil(numerator / denominator)) if denominator > 0 else 0
        can_miss_now = 0
        # Min classes to attend from remaining to reach target across full semester
        total_required = math.ceil(target_pct / 100 * (conducted + remaining))
        min_to_attend_remaining = max(0, total_required - attended)
        safe_bunks_remaining = max(0, remaining - min_to_attend_remaining)
        is_achievable = max_achievable_pct >= target_pct and min_to_attend_remaining <= remaining
        status = "Detained"
    else:
        must_attend_now = 0
        # Can miss y classes right now without dropping below target
        # (attended) / (conducted + y) >= target_pct/100
        # => 100 * attended >= target_pct * (conducted + y)
        # => y <= (100 * attended - target_pct * conducted) / target_pct
        numerator = 100.0 * attended - target_pct * conducted
        can_miss_now = max(0, math.floor(numerator / target_pct))
        # Safe bunks in remaining semester
        total_required = math.ceil(target_pct / 100 * (conducted + remaining))
        min_to_attend_remaining = max(0, total_required - attended)
        safe_bunks_remaining = max(0, remaining - min_to_attend_remaining)
        is_achievable = True
        status = "Safe" if current_pct >= 85 else ("Borderline" if current_pct >= 80 else "At Risk")

    return {
        "current_pct": current_pct,
        "is_detained": is_detained,
        "status": status,
        "must_attend_now": must_attend_now,
        "can_miss_now": can_miss_now,
        "min_to_attend_remaining": min_to_attend_remaining,
        "safe_bunks_remaining": safe_bunks_remaining,
        "max_achievable_pct": max_achievable_pct,
        "is_achievable": is_achievable,
        "remaining_classes": remaining,
    }


def compute_attendance_predictions(student_prn: str, attendance_record: dict,
                                    as_of_date: date = None, target_pct: float = 75.0) -> dict:
    """
    Main entry point: compute full attendance analytics for a student.
    attendance_record is a dict keyed by subject with attended/conducted counts.
    Returns full prediction for each subject and overall.
    """
    if as_of_date is None:
        as_of_date = date.today()

    subjects_data = attendance_record.get("subjects", {})
    honors_subject = attendance_record.get("honors_course")

    result = {
        "student_prn": student_prn,
        "class_name": attendance_record.get("class_name", "TY DS (A)"),
        "as_of": as_of_date.strftime("%d %b %Y"),
        "sem_end": SEM_END.strftime("%d %b %Y"),
        "days_remaining": max(0, (SEM_END - as_of_date).days),
        "target_pct": target_pct,
        "subjects": {},
        "overall": {},
        "honors": None,
    }

    total_attended = 0
    total_conducted = 0
    total_remaining = 0

    all_subjects = list(SUBJECTS) + (["AJL"] if "AJL" in subjects_data else [])
    if honors_subject and honors_subject in HONORS_SUBJECTS:
        all_subjects.append(honors_subject)

    for subj in all_subjects:
        subj_data = subjects_data.get(subj, {})
        lect_att = subj_data.get("lecture_attended", 0)
        lect_con = subj_data.get("lecture_conducted", 0)
        prac_att = subj_data.get("practical_attended", 0) or subj_data.get("tutorial_attended", 0)
        prac_con = subj_data.get("practical_conducted", 0) or subj_data.get("tutorial_conducted", 0)

        att = lect_att + prac_att
        con = lect_con + prac_con

        # Estimate remaining
        rem_lect = compute_remaining_lectures(as_of_date, subj, "theory")
        rem_prac = compute_remaining_lectures(as_of_date, subj, "practical") if subj in PRACTICAL_SUBJECTS else 0
        remaining = rem_lect + rem_prac

        pred = compute_subject_prediction(att, con, remaining, target_pct)
        pred["lecture_attended"] = lect_att
        pred["lecture_conducted"] = lect_con
        pred["practical_attended"] = prac_att
        pred["practical_conducted"] = prac_con
        pred["total_attended"] = att
        pred["total_conducted"] = con
        pred["remaining_lectures"] = rem_lect
        pred["remaining_practicals"] = rem_prac
        pred["teacher"] = TEACHING_STAFF.get(subj, {}).get("theory", "")
        pred["is_honors"] = subj in HONORS_SUBJECTS

        if subj in HONORS_SUBJECTS:
            result["honors"] = {
                "subject": subj,
                "teacher": TEACHING_STAFF.get(subj, {}).get("theory", ""),
                **pred
            }
        else:
            result["subjects"][subj] = pred
            total_attended += att
            total_conducted += con
            total_remaining += remaining

    # Overall prediction (excluding honors)
    overall_pred = compute_subject_prediction(total_attended, total_conducted,
                                               total_remaining, target_pct)
    overall_pred["total_attended"] = total_attended
    overall_pred["total_conducted"] = total_conducted
    overall_pred["remaining_classes"] = total_remaining
    result["overall"] = overall_pred

    return result


def simulate_what_if(attended: int, conducted: int, remaining: int,
                     extra_attend: int = 0, extra_miss: int = 0,
                     target_pct: float = 75.0) -> dict:
    """
    What-If simulator: given hypothetical extra attended and extra missed classes,
    compute projected attendance percentage.
    """
    new_attended = attended + extra_attend
    new_conducted = conducted + extra_attend + extra_miss
    new_remaining = max(0, remaining - extra_attend - extra_miss)

    if new_conducted == 0:
        return {"projected_pct": 0.0, "status": "No Data", "delta": 0.0}

    projected_pct = round((new_attended / new_conducted) * 100, 2)
    current_pct = round((attended / conducted) * 100, 2) if conducted > 0 else 0.0
    delta = round(projected_pct - current_pct, 2)

    is_safe = projected_pct >= target_pct
    status = "Safe" if projected_pct >= 85 else ("At Risk" if projected_pct >= 75 else "Detained")

    return {
        "projected_pct": projected_pct,
        "current_pct": current_pct,
        "delta": delta,
        "is_safe": is_safe,
        "status": status,
        "new_attended": new_attended,
        "new_conducted": new_conducted,
        "remaining_classes": new_remaining,
        "gap_to_target": round(target_pct - projected_pct, 2) if not is_safe else 0.0,
    }
