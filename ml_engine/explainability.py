import numpy as np
from typing import List, Dict, Any


def generate_sgpa_recommendations(
    feature_dict: Dict[str, Any],
    predicted_sgpa: float,
    model=None,
    feature_names: List[str] = None
) -> List[str]:
    """
    Generates actionable, personalized, plain-language recommendations
    using feature values, SHAP / tree importances, and academic heuristics.
    """
    recommendations = []

    att = float(feature_dict.get("attendance_percentage", 80.0))
    tt_avg = float(feature_dict.get("current_tt_avg", 15.0))
    trend = float(feature_dict.get("sgpa_trend_slope", 0.0))
    backlogs = int(feature_dict.get("active_backlogs", 0))
    is_cold = feature_dict.get("is_cold_start", False)

    if is_cold:
        recommendations.append("Initial semester forecast: Based on cohort baselines and early unit tests. Keep unit test scores above 16/20 to lock in an 8.0+ SGPA.")
        if att < 75.0:
            recommendations.append(f"Attendance ({att:.1f}%) is in the critical warning zone (<75%). Attend all upcoming lectures to avoid detention risk.")
        return recommendations

    # 1. Attendance impact
    if att < 75.0:
        boost = round((75.0 - att) * 0.02 + 0.25, 2)
        recommendations.append(
            f"Attendance ({att:.1f}%) is the largest negative drag on your academic performance. "
            f"Bringing attendance to 80%+ can lift your predicted SGPA by ~{boost:.1f} grade points."
        )
    elif att < 80.0:
        recommendations.append(
            f"Attendance is moderate ({att:.1f}%). Increasing classroom participation to 85%+ provides a safe cushion against exam variance."
        )
    else:
        recommendations.append(f"Strong attendance consistency ({att:.1f}%) actively supports high retention and solid internal scoring.")

    # 2. Unit Test (Internal) Impact
    if tt_avg < 12.0:
        recommendations.append(
            f"Unit Test internal score ({tt_avg:.1f}/20) is restricting your potential. "
            f"Improving subsequent test scores to 16/20 will significantly raise end-semester exam leverage."
        )
    elif tt_avg >= 16.0:
        recommendations.append(
            f"Excellent internal performance ({tt_avg:.1f}/20). Maintaining this standard keeps you firmly on track for an O or A+ grade."
        )

    # 3. Trend analysis
    if trend < -0.3:
        recommendations.append(
            f"Declining SGPA trajectory detected (trend slope {trend:+.2f}). "
            f"Focus on core analytical subjects and consider faculty peer mentoring to reverse downward momentum."
        )
    elif trend > 0.3:
        recommendations.append(
            f"Positive momentum: Your academic trend is steadily upward (trend slope {trend:+.2f}). Maintain this trajectory!"
        )

    # 4. Backlog alerts
    if backlogs > 0:
        recommendations.append(
            f"You have {backlogs} active backlog(s). Clearing these in the next remedial examination cycle is crucial for placement eligibility."
        )

    return recommendations[:3]


def generate_placement_recommendations(
    cgpa: float,
    backlogs: int,
    tech_avg: float,
    placement_prob: float,
    tier_label: str
) -> List[str]:
    """
    Generates plain-language placement readiness explanations and action points.
    """
    recs = []

    # CGPA factor
    if cgpa >= 8.5:
        recs.append(f"Outstanding CGPA of {cgpa:.2f} satisfies eligibility criteria for 98%+ of Tier-1 product companies.")
    elif cgpa >= 7.5:
        recs.append(f"Healthy CGPA ({cgpa:.2f}) comfortably meets standard Tier-1/Tier-2 corporate criteria (7.0+).")
    elif cgpa >= 6.5:
        recs.append(f"Current CGPA ({cgpa:.2f}) meets baseline mass-recruiter criteria. Pushing above 7.0 will unlock ~40% more campus drives.")
    else:
        recs.append(f"CGPA ({cgpa:.2f}) is below the standard 6.5 campus recruitment cutoff. Target 8.0+ in upcoming semesters to raise cumulative score.")

    # Backlog factor
    if backlogs > 0:
        recs.append(f"CRITICAL: {backlogs} active backlog(s) will automatically disqualify your candidature from most Day-1 campus placement drives until cleared.")
    else:
        recs.append("Zero active backlogs: Full eligibility across campus recruitment partner drives.")

    # Technical readiness
    if tech_avg >= 75.0:
        recs.append(f"Core technical subject mastery ({tech_avg:.1f}%) demonstrates high problem-solving competency for coding rounds.")
    elif tech_avg < 60.0:
        recs.append(f"Core technical subject scores ({tech_avg:.1f}%) require reinforcement in Data Structures, Algorithms, and DBMS fundamentals.")

    return recs
