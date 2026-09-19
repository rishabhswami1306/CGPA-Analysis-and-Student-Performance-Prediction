import math
from typing import Dict, Any, List


def solve_what_if_target(
    target_cgpa: float,
    current_cgpa: float,
    completed_credits: int,
    current_sem_credits: int,
    subjects: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Algebraic What-If Solver for semester exam targets.
    
    :param target_cgpa: Desired cumulative CGPA (e.g. 8.5)
    :param current_cgpa: Current CGPA prior to current semester
    :param completed_credits: Total credits earned so far
    :param current_sem_credits: Total credits in current semester (e.g. 20)
    :param subjects: List of dicts with keys: subject_code, subject_name, credits, tt1_score, tt2_score, max_ese
    :return: Comprehensive target breakdown per subject and feasibility report
    """
    total_target_credits = completed_credits + current_sem_credits
    
    # Total grade points needed
    points_so_far = current_cgpa * completed_credits
    points_needed_total = target_cgpa * total_target_credits
    points_needed_current_sem = points_needed_total - points_so_far
    
    if current_sem_credits <= 0:
        current_sem_credits = 20

    required_sgpa = points_needed_current_sem / current_sem_credits
    required_sgpa = round(required_sgpa, 2)

    # Check maximum possible CGPA (if SGPA = 10.0)
    max_possible_cgpa = round((points_so_far + (10.0 * current_sem_credits)) / total_target_credits, 2)

    is_achievable = required_sgpa <= 10.0
    
    # If student is in sem 1, current_cgpa = 0 and completed_credits = 0
    if completed_credits == 0:
        required_sgpa = round(target_cgpa, 2)
        is_achievable = target_cgpa <= 10.0
        max_possible_cgpa = 10.0

    # Determine grade point needed per subject
    # Minimum total marks needed for standard grade points:
    # 10 -> 80, 9 -> 75, 8 -> 70, 7 -> 60, 6 -> 50, 5 -> 45, 4 -> 40
    grade_thresholds = [
        (10.0, 80.0, "O (10)"),
        (9.0, 75.0, "A+ (9)"),
        (8.0, 70.0, "A (8)"),
        (7.0, 60.0, "B+ (7)"),
        (6.0, 50.0, "B (6)"),
        (5.0, 45.0, "C (5)"),
        (4.0, 40.0, "P (4)")
    ]

    target_gp = max(4.0, min(10.0, math.ceil(required_sgpa))) if is_achievable else 10.0
    
    subject_recommendations = []
    for sub in subjects:
        tt1 = float(sub.get("tt1_score", 0.0))
        tt2 = float(sub.get("tt2_score", 0.0))
        apt = float(sub.get("aptitude_score", 0.0))
        skat = float(sub.get("skat_score", 0.0))
        ta = float(sub.get("teacher_assessment_score", 0.0))
        mock = float(sub.get("mock_interview_score", 0.0))
        pres = float(sub.get("presentation_score", 0.0))
        max_ese = float(sub.get("max_ese", 60.0))

        # Check if full internal score is provided or compute it
        if "internal_score" in sub and sub["internal_score"] is not None:
            internal = float(sub["internal_score"])
        elif tt1 > 20.0 or tt2 > 20.0 or apt > 0 or skat > 0 or ta > 0 or mock > 0 or pres > 0 or max_ese == 60.0:
            tt_conv = (min(30.0, tt1) + min(30.0, tt2)) / 4.0
            internal = min(40.0, tt_conv + apt + skat + ta + mock + pres)
        else:
            # Legacy fallback
            internal = (tt1 + tt2) / 2.0
            if max_ese != 60.0 and max_ese == 80.0:
                pass

        # Find threshold marks for target_gp
        threshold_marks = 80.0
        for gp_val, marks_val, _ in grade_thresholds:
            if gp_val == target_gp:
                threshold_marks = marks_val
                break

        # Required ESE marks (out of 60)
        needed_scaled_ese = max(0.0, threshold_marks - internal)
        if max_ese == 60.0:
            needed_raw_ese = round(min(max_ese, needed_scaled_ese), 1)
        else:
            needed_raw_ese = round((needed_scaled_ese / 60.0) * max_ese, 1)

        # Min pass requirement (40 total marks)
        pass_needed = max(0.0, 40.0 - internal)
        pass_raw_ese = round(min(max_ese, pass_needed) if max_ese == 60.0 else (pass_needed / 60.0) * max_ese, 1)

        sub_feasible = needed_scaled_ese <= 60.0

        # Provide a table of what ESE score gives what grade in this subject
        matrix = []
        for gp_val, marks_val, label in grade_thresholds:
            needed_scaled = max(0.0, marks_val - internal)
            needed_raw = round(needed_scaled if max_ese == 60.0 else (needed_scaled / 60.0) * max_ese, 1)
            possible = needed_raw <= max_ese
            matrix.append({
                "target_grade": label,
                "grade_point": gp_val,
                "required_ese_marks": needed_raw if possible else "Unattainable",
                "max_marks": max_ese,
                "is_attainable": possible
            })

        subject_recommendations.append({
            "subject_code": sub.get("subject_code", ""),
            "subject_name": sub.get("subject_name", ""),
            "credits": sub.get("credits", 4),
            "internal_score": round(internal, 2),
            "tt_avg_score": round((tt1 + tt2) / 4.0 if (tt1 > 20 or tt2 > 20) else (tt1 + tt2) / 2.0, 2),
            "max_ese": max_ese,
            "target_grade_point": target_gp,
            "needed_ese_score": needed_raw_ese if sub_feasible else f"{needed_raw_ese} (Exceeds Max {max_ese})",
            "minimum_pass_ese": pass_raw_ese,
            "is_feasible": sub_feasible,
            "grade_matrix": matrix
        })

    advice_message = ""
    if not is_achievable:
        advice_message = (
            f"Target CGPA of {target_cgpa} is mathematically unattainable in the current semester alone "
            f"(requires {required_sgpa} SGPA, max possible is {max_possible_cgpa}). "
            f"Aim for a 10.0 SGPA this semester to reach {max_possible_cgpa} CGPA."
        )
    elif required_sgpa <= 0:
        advice_message = f"You have already met or exceeded your target CGPA of {target_cgpa}! Maintain passing grades to stay secure."
    else:
        advice_message = (
            f"To achieve your target CGPA of {target_cgpa}, you need an estimated SGPA of {required_sgpa:.2f} "
            f"in the current semester. See subject-by-subject target scores below."
        )

    return {
        "target_cgpa": target_cgpa,
        "current_cgpa": current_cgpa,
        "required_sgpa": required_sgpa,
        "max_possible_cgpa": max_possible_cgpa,
        "is_achievable": is_achievable,
        "advice_message": advice_message,
        "subject_breakdown": subject_recommendations
    }
