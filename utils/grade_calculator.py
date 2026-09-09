import math
from typing import List, Dict, Any, Tuple


def calculate_grade_point(total_marks: float) -> Tuple[float, str]:
    """
    Standard deterministic university grading scale:
    >= 80: 10 (O - Outstanding)
    >= 75: 9 (A+ - Excellent)
    >= 70: 8 (A - Very Good)
    >= 60: 7 (B+ - Good)
    >= 50: 6 (B - Above Average)
    >= 45: 5 (C - Average)
    >= 40: 4 (P - Pass)
    < 40: 0 (F - Fail / Backlog)
    """
    marks = round(total_marks, 2)
    if marks >= 80.0:
        return 10.0, "O"
    elif marks >= 75.0:
        return 9.0, "A+"
    elif marks >= 70.0:
        return 8.0, "A"
    elif marks >= 60.0:
        return 7.0, "B+"
    elif marks >= 50.0:
        return 6.0, "B"
    elif marks >= 45.0:
        return 5.0, "C"
    elif marks >= 40.0:
        return 4.0, "P"
    else:
        return 0.0, "F"


def compute_subject_total(tt1: float, tt2: float, ese: float, max_ese: float = 80.0) -> float:
    """
    Calculates total marks out of 100:
    Internal Unit Test avg (out of 20) + Scaled ESE (scaled to 80 if max_ese is not 80, or direct sum).
    """
    internal_avg = (tt1 + tt2) / 2.0  # Out of 20
    if max_ese != 80.0 and max_ese > 0:
        scaled_ese = (ese / max_ese) * 80.0
    else:
        scaled_ese = ese
    total = internal_avg + scaled_ese
    return min(100.0, max(0.0, round(total, 2)))


def compute_semester_sgpa(subjects: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """
    Calculates SGPA from list of subjects.
    Each subject has credits and grade_point (or scores to calculate).
    Returns (sgpa, active_backlogs, total_credits).
    """
    total_credit_points = 0.0
    total_credits = 0
    active_backlogs = 0

    for sub in subjects:
        credits = int(sub.get("credits", 4))
        
        # If grade_point is not present, calculate it from scores
        if "grade_point" in sub and sub["grade_point"] is not None:
            gp = float(sub["grade_point"])
        else:
            tt1 = float(sub.get("tt1_score", 0.0))
            tt2 = float(sub.get("tt2_score", 0.0))
            ese = float(sub.get("ese_score", 0.0))
            max_ese = float(sub.get("max_ese", 80.0))
            total = compute_subject_total(tt1, tt2, ese, max_ese)
            sub["total_marks"] = total
            gp, grade = calculate_grade_point(total)
            sub["grade_point"] = gp
            sub["grade_letter"] = grade

        if gp == 0.0:
            active_backlogs += 1

        total_credit_points += (credits * gp)
        total_credits += credits

    if total_credits == 0:
        return 0.0, 0, 0

    sgpa = round(total_credit_points / total_credits, 2)
    return sgpa, active_backlogs, total_credits


def compute_cumulative_cgpa(semester_records: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """
    Calculates cumulative CGPA across multiple semesters.
    Returns (cgpa, total_active_backlogs, total_credits_earned).
    """
    if not semester_records:
        return 0.0, 0, 0

    total_credit_points = 0.0
    total_credits = 0
    total_backlogs = 0

    for sem in semester_records:
        sgpa = float(sem.get("sgpa", 0.0))
        subjects = sem.get("subjects", [])
        sem_credits = sum(int(s.get("credits", 4)) for s in subjects) or 20
        total_credit_points += (sgpa * sem_credits)
        total_credits += sem_credits
        total_backlogs += int(sem.get("active_backlogs", 0))

    if total_credits == 0:
        return 0.0, 0, 0

    cgpa = round(total_credit_points / total_credits, 2)
    return cgpa, total_backlogs, total_credits


def compute_attendance_shortfall(attended_lectures: int, total_lectures: int, target_pct: float = 75.0) -> Dict[str, Any]:
    """
    Deterministic attendance shortfall algebra:
    Minimum lectures required to reach target_pct (e.g. 75%).
    (attended + x) / (total + x) >= target_pct/100
    attended + x >= (target_pct/100)*total + (target_pct/100)*x
    x * (1 - target_pct/100) >= (target_pct/100)*total - attended
    x >= (target_pct * total - 100 * attended) / (100 - target_pct)
    """
    if total_lectures <= 0:
        return {
            "current_percentage": 0.0,
            "is_at_risk": True,
            "lectures_needed": 0,
            "status": "NO_DATA",
            "message": "No lecture history recorded yet."
        }

    current_pct = round((attended_lectures / total_lectures) * 100.0, 2)
    
    if current_pct >= target_pct:
        # Can afford to miss any lectures?
        # (attended) / (total + m) >= 0.75 => attended >= 0.75*(total + m) => m <= (attended/0.75) - total
        missable = max(0, math.floor((attended_lectures / (target_pct / 100.0)) - total_lectures))
        return {
            "current_percentage": current_pct,
            "is_at_risk": False,
            "lectures_needed": 0,
            "can_miss_lectures": missable,
            "status": "SAFE",
            "message": f"Attendance is safe at {current_pct}%. You can afford to miss up to {missable} lecture(s)."
        }
    else:
        # Shortfall
        numerator = (target_pct * total_lectures) - (100.0 * attended_lectures)
        denominator = 100.0 - target_pct
        needed = math.ceil(numerator / denominator)
        needed = max(1, needed)
        return {
            "current_percentage": current_pct,
            "is_at_risk": True,
            "lectures_needed": needed,
            "can_miss_lectures": 0,
            "status": "SHORTFALL",
            "message": f"Attendance shortfall alert ({current_pct}% < {target_pct}%). You must attend the next {needed} consecutive lectures to reach {target_pct}%."
        }
