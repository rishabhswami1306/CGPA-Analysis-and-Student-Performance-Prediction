import math
from typing import List, Dict, Any

# Calibrated course difficulty factors (higher = historically steeper failure rates / higher variance)
COURSE_DIFFICULTY_INDEX = {
    "DAA": 1.25,     # Design and Analysis of Algorithms
    "ML-II": 1.20,   # Machine Learning - II
    "IS": 1.15,      # Information Security
    "EM": 1.25,      # Engineering Mathematics / Applied Mathematics
    "CCN": 1.10,     # Computer Communication Networks
    "CCS": 1.08,     # Cloud Computing & Security
    "CI": 1.05,      # Computational Intelligence
    "AJL": 0.95,     # Advanced Java Lab
    "DEFAULT": 1.05
}


def compute_subject_risk_profile(
    subject: Dict[str, Any],
    student_attendance: float = 80.0,
    class_averages: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Computes subject-specific grade projection, KT/backlog risk probability,
    and exact End-Semester Exam (ESE) target thresholds.
    """
    code = subject.get("subject_code", "GENERIC")
    name = subject.get("subject_name", code)
    credits = int(subject.get("credits", 4))
    
    tt1 = float(subject.get("tt1_score", 0.0))
    tt2 = float(subject.get("tt2_score", 0.0))
    
    # Internal continuous assessment out of 40
    internal = float(subject.get("internal_score", 0.0))
    if internal == 0.0:
        tt_conv = (tt1 + tt2) / 4.0 if (tt1 > 20 or tt2 > 20) else (tt1 + tt2) / 2.0
        apt = float(subject.get("aptitude_score", 0.0))
        skat = float(subject.get("skat_score", 0.0))
        ta = float(subject.get("teacher_assessment_score", 0.0))
        mock = float(subject.get("mock_interview_score", 0.0))
        pres = float(subject.get("presentation_score", 0.0))
        internal = round(min(40.0, tt_conv + apt + skat + ta + mock + pres), 2)

    difficulty = COURSE_DIFFICULTY_INDEX.get(code, COURSE_DIFFICULTY_INDEX["DEFAULT"])
    class_avg = class_averages.get(code, 65.0) if class_averages else 65.0

    # University Thresholds (Internal 40 + ESE 60 = 100 Total)
    # Standard engineering university rule: Must score min 40% overall AND min 24/60 (40%) in ESE
    min_ese_to_pass = max(24.0, round(40.0 - internal, 1))
    min_ese_for_grade_a = max(min_ese_to_pass, round(70.0 - internal, 1))
    min_ese_for_grade_o = max(min_ese_to_pass, round(80.0 - internal, 1))

    # Existing ESE score if final exam completed
    existing_ese = float(subject.get("ese_score", 0.0))
    is_completed = existing_ese > 0.0 or subject.get("total_marks", 0.0) > 0.0

    if is_completed:
        ese_final = existing_ese if existing_ese > 0 else (float(subject.get("total_marks", 0.0)) - internal)
        total_projected = round(internal + ese_final, 1)
        projected_ese = ese_final
    else:
        # Trajectory extrapolation based on internal score + subject difficulty penalty
        internal_ratio = internal / 40.0
        projected_ese_raw = (internal_ratio * 60.0) / (difficulty ** 0.5)
        # Attendance factor adjustment (+/- 5%)
        att_factor = (student_attendance - 75.0) * 0.05
        projected_ese = min(60.0, max(0.0, round(projected_ese_raw + att_factor, 1)))
        total_projected = round(internal + projected_ese, 1)

    # Determine projected grade
    if total_projected >= 80.0:
        proj_grade = "O"
        grade_point = 10
    elif total_projected >= 75.0:
        proj_grade = "A+"
        grade_point = 9
    elif total_projected >= 70.0:
        proj_grade = "A"
        grade_point = 8
    elif total_projected >= 60.0:
        proj_grade = "B+"
        grade_point = 7
    elif total_projected >= 50.0:
        proj_grade = "B"
        grade_point = 6
    elif total_projected >= 45.0:
        proj_grade = "C"
        grade_point = 5
    elif total_projected >= 40.0:
        proj_grade = "P"
        grade_point = 4
    else:
        proj_grade = "F"
        grade_point = 0

    # Backlog Probability calculation
    # Driven by distance of internal from safe benchmark (20/40), attendance, and difficulty
    deficit = (22.0 - internal) * 0.25 + (75.0 - student_attendance) * 0.04
    logit = (deficit * difficulty) - 0.8
    kt_prob = round(1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, logit)))), 3)

    if is_completed and proj_grade != "F":
        kt_prob = 0.01

    if kt_prob >= 0.45 or proj_grade == "F" or (internal < 14.0 and not is_completed):
        risk_level = "CRITICAL_KT_RISK"
        risk_color = "red"
        risk_label = "Critical Backlog Risk"
        recommendation = f"Severe risk of KT. Target minimum {min_ese_to_pass} marks in ESE and attend remedial tutorials."
    elif kt_prob >= 0.22 or proj_grade in ["C", "P"]:
        risk_level = "MODERATE_RISK"
        risk_color = "amber"
        risk_label = "Moderate Risk"
        recommendation = f"Scoring cushion is thin. Needs at least {min_ese_for_grade_a} marks in ESE to achieve Grade A."
    else:
        risk_level = "SAFE"
        risk_color = "emerald"
        risk_label = "On Track"
        recommendation = f"Solid performance. Maintain standard revision to secure Grade {proj_grade}."

    return {
        "subject_code": code,
        "subject_name": name,
        "credits": credits,
        "internal_score": internal,
        "projected_ese": projected_ese,
        "total_projected": total_projected,
        "projected_grade": proj_grade,
        "grade_point": grade_point,
        "backlog_probability": kt_prob,
        "backlog_risk_pct": round(kt_prob * 100.0, 1),
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_label": risk_label,
        "difficulty_index": difficulty,
        "min_ese_to_pass": min_ese_to_pass,
        "min_ese_for_grade_a": min_ese_for_grade_a,
        "min_ese_for_grade_o": min_ese_for_grade_o,
        "is_achievable_grade_a": min_ese_for_grade_a <= 60.0,
        "recommendation": recommendation
    }


def analyze_all_enrolled_subjects(
    subjects: List[Dict[str, Any]],
    student_attendance: float = 80.0,
    class_averages: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Analyzes all active subjects for a student and aggregates risk metrics.
    """
    profiles = [compute_subject_risk_profile(s, student_attendance, class_averages) for s in subjects]
    
    total_subjects = len(profiles)
    critical_count = sum(1 for p in profiles if p["risk_level"] == "CRITICAL_KT_RISK")
    moderate_count = sum(1 for p in profiles if p["risk_level"] == "MODERATE_RISK")
    safe_count = sum(1 for p in profiles if p["risk_level"] == "SAFE")
    
    avg_backlog_prob = round(sum(p["backlog_probability"] for p in profiles) / total_subjects, 3) if total_subjects else 0.0

    return {
        "profiles": profiles,
        "total_subjects": total_subjects,
        "critical_backlog_count": critical_count,
        "moderate_risk_count": moderate_count,
        "safe_count": safe_count,
        "average_backlog_prob_pct": round(avg_backlog_prob * 100.0, 1),
        "overall_subject_health": "CRITICAL" if critical_count > 0 else ("WARNING" if moderate_count > 1 else "HEALTHY")
    }
