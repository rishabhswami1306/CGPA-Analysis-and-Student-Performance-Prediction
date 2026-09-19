import math
from typing import Dict, Any, List


def generate_counterfactual_pathways(
    current_cgpa: float,
    completed_credits: int,
    ongoing_credits: int,
    current_tt1_avg: float,
    current_tt2_avg: float,
    current_attendance: float,
    target_sgpa: float = None,
    target_cgpa: float = None,
    subjects: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes algorithmic minimal-effort counterfactual intervention pathways
    to reach a target SGPA or cumulative CGPA.
    """
    total_target_credits = completed_credits + (ongoing_credits or 20)
    
    # Determine target SGPA
    if target_sgpa is None:
        if target_cgpa is not None and completed_credits > 0:
            points_needed = (target_cgpa * total_target_credits) - (current_cgpa * completed_credits)
            target_sgpa = round(points_needed / (ongoing_credits or 20), 2)
        else:
            target_sgpa = min(10.0, round(max(current_cgpa, 7.0) + 0.75, 2))

    target_sgpa = max(4.0, min(10.0, target_sgpa))
    
    # Current TT average
    current_tt = (current_tt1_avg + current_tt2_avg) / 2.0 if (current_tt1_avg <= 20 and current_tt2_avg <= 20) else (current_tt1_avg + current_tt2_avg) / 4.0
    
    # Standard grade threshold math: Target SGPA maps to total required marks percentage
    # SGPA 10 -> 80%, SGPA 9 -> 75%, SGPA 8 -> 70%, SGPA 7 -> 60%, SGPA 6 -> 50%
    if target_sgpa >= 9.5:
        target_marks_pct = 82.0
    elif target_sgpa >= 8.5:
        target_marks_pct = 76.0
    elif target_sgpa >= 7.5:
        target_marks_pct = 68.0
    elif target_sgpa >= 6.5:
        target_marks_pct = 58.0
    else:
        target_marks_pct = 48.0

    # 1. PATHWAY 1: Balanced Progression (Optimal Multi-Variable Distribution)
    # Distribute effort across upcoming TT2, moderate attendance boost, and ESE
    tt2_boost = max(0.0, min(20.0 - current_tt2_avg, round(max(1.5, (target_marks_pct - 60.0) * 0.25), 1)))
    new_tt2 = round(min(20.0, current_tt2_avg + tt2_boost), 1)
    
    att_boost = max(0.0, min(100.0 - current_attendance, 5.0 if current_attendance < 80.0 else 2.5))
    new_att = round(current_attendance + att_boost, 1)
    
    # Required ESE average out of 60
    # Internal estimate: (TT1 + new_TT2)/2 + assignment/attendance components (~18-35 out of 40)
    est_internal_p1 = min(40.0, (current_tt1_avg + new_tt2) / 2.0 + (new_att / 100.0) * 12.0 + 6.0)
    req_ese_p1 = max(24.0, min(60.0, round(target_marks_pct - est_internal_p1, 1)))
    
    feasibility_p1 = max(10, min(98, int(100 - (tt2_boost * 4.0) - max(0, req_ese_p1 - 42) * 2.5)))

    pathway_1 = {
        "title": "Balanced Progression Strategy",
        "description": "Distributes minimal incremental effort equally across TT2, attendance, and final exam prep.",
        "feasibility_score": feasibility_p1,
        "feasibility_label": "High Feasibility" if feasibility_p1 >= 80 else ("Moderate" if feasibility_p1 >= 60 else "Challenging"),
        "color": "emerald",
        "actions": [
            {"parameter": "Unit Test 2 Score", "current": f"{current_tt2_avg:.1f}/20", "target": f"{new_tt2:.1f}/20", "delta": f"+{tt2_boost:.1f} marks"},
            {"parameter": "Class Attendance", "current": f"{current_attendance:.1f}%", "target": f"{new_att:.1f}%", "delta": f"+{att_boost:.1f}% (+{int(att_boost * 0.7)} classes)"},
            {"parameter": "ESE Exam Average", "current": "Baseline (~36/60)", "target": f"{req_ese_p1:.1f}/60", "delta": "Target Avg"}
        ],
        "key_takeaway": f"Targeting {new_tt2:.1f} in TT2 and attending {int(att_boost * 0.7) or 3} additional lectures eases the ESE exam target to an achievable {req_ese_p1:.1f}/60."
    }

    # 2. PATHWAY 2: Exam Sprint (Zero Attendance Change)
    # Student keeps attendance unchanged, relying purely on written exam mastery
    est_internal_p2 = min(40.0, (current_tt1_avg + current_tt2_avg) / 2.0 + (current_attendance / 100.0) * 12.0 + 6.0)
    req_ese_p2 = max(24.0, min(60.0, round(target_marks_pct - est_internal_p2, 1)))
    feasibility_p2 = max(10, min(95, int(100 - max(0, req_ese_p2 - 38) * 3.5)))

    pathway_2 = {
        "title": "Exam Blitz Strategy (Zero Attendance Overtime)",
        "description": "Keeps attendance commitments as-is and channels 100% focus into scoring high in End-Semester Exams.",
        "feasibility_score": feasibility_p2,
        "feasibility_label": "High Feasibility" if feasibility_p2 >= 80 else ("Moderate" if feasibility_p2 >= 60 else "Challenging"),
        "color": "blue",
        "actions": [
            {"parameter": "Unit Test 2 Score", "current": f"{current_tt2_avg:.1f}/20", "target": f"{current_tt2_avg:.1f}/20", "delta": "Maintain"},
            {"parameter": "Class Attendance", "current": f"{current_attendance:.1f}%", "target": f"{current_attendance:.1f}%", "delta": "+0% (Unchanged)"},
            {"parameter": "ESE Exam Average", "current": "Baseline", "target": f"{req_ese_p2:.1f}/60", "delta": f"High ESE Target"}
        ],
        "key_takeaway": f"If attendance remains at {current_attendance:.1f}%, you must score a rigorous {req_ese_p2:.1f}/60 average across all written papers."
    }

    # 3. PATHWAY 3: Attendance Cushion & Internal Mastery (Low Exam Stress)
    # Maximize attendance & internal evaluation to minimize exam pressure
    target_cushion_att = min(92.0, max(85.0, current_attendance + 8.0))
    att_cushion_boost = round(target_cushion_att - current_attendance, 1)
    target_cushion_tt2 = min(20.0, max(17.0, current_tt2_avg + 3.0))
    
    est_internal_p3 = min(40.0, (current_tt1_avg + target_cushion_tt2) / 2.0 + (target_cushion_att / 100.0) * 12.0 + 8.0)
    req_ese_p3 = max(24.0, min(60.0, round(target_marks_pct - est_internal_p3, 1)))
    feasibility_p3 = max(10, min(99, int(100 - (att_cushion_boost * 1.5) - max(0, req_ese_p3 - 40) * 2.0)))

    pathway_3 = {
        "title": "Attendance Cushion & Internal Shield",
        "description": "Max out classroom attendance and continuous internals to insulate your SGPA against tough exam papers.",
        "feasibility_score": feasibility_p3,
        "feasibility_label": "Very High Feasibility" if feasibility_p3 >= 85 else ("High" if feasibility_p3 >= 70 else "Moderate"),
        "color": "purple",
        "actions": [
            {"parameter": "Unit Test 2 Score", "current": f"{current_tt2_avg:.1f}/20", "target": f"{target_cushion_tt2:.1f}/20", "delta": f"+{target_cushion_tt2 - current_tt2_avg:.1f} marks"},
            {"parameter": "Class Attendance", "current": f"{current_attendance:.1f}%", "target": f"{target_cushion_att:.1f}%", "delta": f"+{att_cushion_boost:.1f}% (+{int(att_cushion_boost * 0.8)} classes)"},
            {"parameter": "ESE Exam Average", "current": "Baseline", "target": f"{req_ese_p3:.1f}/60", "delta": "Reduced ESE Stress"}
        ],
        "key_takeaway": f"Building attendance up to {target_cushion_att:.1f}% shields your grade, dropping your required ESE mark to just {req_ese_p3:.1f}/60."
    }

    return {
        "target_sgpa": target_sgpa,
        "current_cgpa": current_cgpa,
        "target_cgpa": target_cgpa,
        "target_marks_percentage": target_marks_pct,
        "pathways": [pathway_1, pathway_2, pathway_3]
    }
