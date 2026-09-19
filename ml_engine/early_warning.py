import math
from typing import Dict, Any, List


def evaluate_early_warning_system(
    current_attendance: float,
    current_tt1_avg: float,
    current_tt2_avg: float,
    sgpa_mean: float,
    sgpa_trend_slope: float,
    active_backlogs: int,
    ongoing_subjects: List[Dict[str, Any]] = None,
    current_week: int = 9,
    semester_total_weeks: int = 15
) -> Dict[str, Any]:
    """
    Evaluates dynamic intra-semester milestone trajectory, trajectory divergence,
    and temporal 'Rescue Window' metrics.
    """
    # Weeks and Days remaining in instruction
    weeks_remaining = max(1, semester_total_weeks - current_week)
    days_to_ese = weeks_remaining * 7

    # Derive current milestone phase
    if current_tt2_avg > 0 and current_tt1_avg > 0:
        current_phase = "Phase 3: Post-TT2 & Internal Marks Consolidation"
        phase_code = "PHASE_3"
        assessments_remaining = ["Lab Term-work & Viva", "Course Project Presentation", "End-Semester Written Exams (ESE)"]
    elif current_tt1_avg > 0:
        current_phase = "Phase 2: Post-TT1 Mid-Semester Diagnostic"
        phase_code = "PHASE_2"
        assessments_remaining = ["Unit Test 2 (TT2)", "Continuous Lab Assessments", "Teacher Assessment / SKAT", "End-Semester Written Exams (ESE)"]
    else:
        current_phase = "Phase 1: Early Attendance & Engagement Baseline"
        phase_code = "PHASE_1"
        assessments_remaining = ["Unit Test 1 (TT1)", "Unit Test 2 (TT2)", "Continuous Evaluation", "End-Semester Written Exams (ESE)"]

    # Trajectory divergence calculation
    current_tt_norm = (current_tt1_avg + (current_tt2_avg if current_tt2_avg > 0 else current_tt1_avg)) / 2.0
    expected_tt = (sgpa_mean / 10.0) * 20.0
    tt_divergence_pct = round(((current_tt_norm - expected_tt) / (expected_tt or 15.0)) * 100.0, 1)

    # Determine Trajectory Status
    if current_attendance < 75.0 and (current_tt_norm < 12.0 or active_backlogs > 0):
        trajectory_status = "CRITICAL_DEFICIT"
        status_label = "Critical Deficit — Urgent Action Required"
        status_color = "red"
    elif current_attendance < 75.0 or tt_divergence_pct < -15.0 or sgpa_trend_slope < -0.3:
        trajectory_status = "DIVERGING_DOWNWARD"
        status_label = "Diverging Downward from Historical Baseline"
        status_color = "amber"
    elif tt_divergence_pct > 10.0 or sgpa_trend_slope > 0.25:
        trajectory_status = "ACCELERATING"
        status_label = "Accelerating Trajectory (Positive Momentum)"
        status_color = "emerald"
    else:
        trajectory_status = "STABLE"
        status_label = "Stable Trajectory (Tracking Expected Benchmark)"
        status_color = "blue"

    # Compute Mathematical Ceiling (Max Attainable SGPA if student scores 100% on all remaining work)
    # If 60% of marks (ESE) remain + partial TT2:
    if phase_code == "PHASE_3":
        # Internal marks ~30/40 locked. Only ESE (60 marks) remains
        est_curr_internal = (current_tt1_avg + current_tt2_avg) / 2.0 * 1.5
        max_possible_total = min(100.0, est_curr_internal + 60.0)
    else:
        # TT2 (20 marks) + ESE (60 marks) remain
        max_possible_total = min(100.0, (current_tt1_avg * 0.75) + 15.0 + 60.0)

    if max_possible_total >= 80.0:
        max_possible_sgpa = 10.0
    elif max_possible_total >= 75.0:
        max_possible_sgpa = 9.0
    elif max_possible_total >= 70.0:
        max_possible_sgpa = 8.0
    elif max_possible_total >= 60.0:
        max_possible_sgpa = 7.0
    else:
        max_possible_sgpa = 6.0

    # Salvageability classification
    if trajectory_status == "CRITICAL_DEFICIT":
        if current_attendance >= 65.0:
            salvage_status = "RECOVERABLE_WITH_INTENSE_EFFORT"
            salvage_label = "High Urgency: Attainable through Mandatory Tutoring & 100% Attendance"
        else:
            salvage_status = "MATHEMATICALLY_RESTRICTED"
            salvage_label = "Mathematically Restricted: Detention Waiver / HOD Appeal Required"
    elif trajectory_status == "DIVERGING_DOWNWARD":
        salvage_status = "FULLY_RECOVERABLE"
        salvage_label = "Fully Recoverable: Reversal Feasible within Remaining Instruction Window"
    else:
        salvage_status = "OPTIMAL_PROGRESS"
        salvage_label = "Optimal Progress: Continue Current Study Protocol"

    # Actionable Intervention Checklist
    checklist = []
    if current_attendance < 75.0:
        checklist.append({
            "task": "Daily Zero-Bunk Mandate",
            "urgency": "CRITICAL",
            "desc": "Attend every lecture without absence for the next 14 instructional days."
        })
    if current_tt_norm < 14.0:
        checklist.append({
            "task": "Remedial Question Bank & PYQ Practice",
            "urgency": "HIGH",
            "desc": "Complete previous 3 years' university question papers for lowest scoring subjects."
        })
    if active_backlogs > 0:
        checklist.append({
            "task": "Remedial Examination Registration",
            "urgency": "HIGH",
            "desc": f"Ensure exam forms are filed to clear {active_backlogs} standing backlog(s)."
        })
    if not checklist:
        checklist.append({
            "task": "Targeted Revision & Mock Exam Drill",
            "urgency": "NORMAL",
            "desc": "Maintain revision tempo and simulate full 3-hour mock exam conditions."
        })

    return {
        "current_phase": current_phase,
        "phase_code": phase_code,
        "current_week": current_week,
        "weeks_remaining": weeks_remaining,
        "days_to_ese": days_to_ese,
        "trajectory_status": trajectory_status,
        "status_label": status_label,
        "status_color": status_color,
        "divergence_pct": tt_divergence_pct,
        "assessments_remaining": assessments_remaining,
        "max_possible_sgpa": max_possible_sgpa,
        "salvage_status": salvage_status,
        "salvage_label": salvage_label,
        "intervention_checklist": checklist
    }
