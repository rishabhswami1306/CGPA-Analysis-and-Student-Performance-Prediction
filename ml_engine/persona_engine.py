from typing import Dict, Any, List
import numpy as np


def classify_student_persona(
    attendance_pct: float,
    current_tt_avg: float,
    sgpa_mean: float,
    sgpa_trend_slope: float,
    active_backlogs: int,
    completed_records: List[Dict[str, Any]] = None,
    ongoing_subjects: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes unsupervised learning persona archetype and 5-dimensional
    trait radar vector for personalized pedagogical intervention.
    """
    # 1. Compute 5 Trait Dimensions (0 - 100 scale)
    # Trait 1: Discipline & Attendance
    discipline = min(100.0, max(10.0, float(attendance_pct)))

    # Trait 2: Continuous Internal Mastery
    # 20 is max for TT
    tt_norm = min(20.0, current_tt_avg)
    internal_mastery = round((tt_norm / 20.0) * 100.0, 1)

    # Trait 3: Exam Clutch Factor (ESE written performance relative to internal)
    # Estimate from past semester ESE scores or heuristic
    ese_scores = []
    practical_scores = []
    if completed_records:
        for r in completed_records:
            for s in r.get("subjects", []):
                if s.get("ese_score") is not None and s.get("ese_score") > 0:
                    ese_scores.append(float(s["ese_score"]))
                if s.get("total_marks") is not None:
                    practical_scores.append(float(s["total_marks"]))
    
    if ese_scores:
        avg_ese_pct = (float(np.mean(ese_scores)) / 60.0) * 100.0
    else:
        avg_ese_pct = (sgpa_mean / 10.0) * 100.0

    exam_clutch = min(100.0, max(20.0, round(avg_ese_pct, 1)))

    # Trait 4: Practical & Technical Aptitude
    if practical_scores:
        practical_apt = min(100.0, max(30.0, round(float(np.mean(practical_scores)), 1)))
    else:
        practical_apt = round(min(100.0, (current_tt_avg / 20.0) * 70.0 + 30.0), 1)

    # Trait 5: Momentum & Academic Resilience
    # Baseline 65, adjusted by trend slope and backlog status
    resilience_raw = 65.0 + (sgpa_trend_slope * 40.0) - (active_backlogs * 18.0)
    momentum_resilience = min(100.0, max(15.0, round(resilience_raw, 1)))

    radar_traits = {
        "discipline_attendance": discipline,
        "internal_mastery": internal_mastery,
        "exam_clutch": exam_clutch,
        "practical_aptitude": practical_apt,
        "momentum_resilience": momentum_resilience
    }

    # 2. Archetype Classification Logic
    if active_backlogs > 0 or (attendance_pct < 75.0 and sgpa_trend_slope < -0.2):
        archetype_code = "VULNERABLE_SLIDER"
        archetype_name = "The Vulnerable Slider"
        archetype_title = "At-Risk / Recovery Focus"
        archetype_color = "red"
        archetype_icon = "fa-triangle-exclamation"
        summary = "Experiencing multi-semester academic drag or attendance deficits. Highly susceptible to exam bottlenecks if continuous assessments slip."
        strategy = "Prioritize backlog clearance, maintain a daily zero-bunk attendance mandate, and schedule mandatory weekly mentor check-ins."

    elif practical_apt >= 75.0 and exam_clutch < 68.0 and discipline >= 75.0:
        archetype_code = "PRACTICAL_BUILDER"
        archetype_name = "The Practical Specialist"
        archetype_title = "Hands-On Builder & Developer"
        archetype_color = "indigo"
        archetype_icon = "fa-code"
        summary = "Excels in software development, laboratory experimentation, and practical implementation, but underperforms in traditional rote written university exams."
        strategy = "Leverage strength in technical interviews while drilling formal written university exam question blueprints and diagram structures."

    elif exam_clutch >= 72.0 and internal_mastery <= 65.0:
        archetype_code = "EXAM_SPRINTER"
        archetype_name = "The End-Semester Sprinter"
        archetype_title = "High-Stakes Final Exam Clutch"
        archetype_color = "blue"
        archetype_icon = "fa-bolt-lightning"
        summary = "Tends to coast through early internal assessments, relying on intense late-semester cramming to salvage final semester grades."
        strategy = "Stop leaving easy internal marks on the table. Scoring just +3 marks in Unit Test 2 will immediately elevate your cumulative CGPA by ~0.4."

    else:
        archetype_code = "CONSISTENT_ACHIEVER"
        archetype_name = "The Consistent High-Achiever"
        archetype_title = "Structured & High Academic Discipline"
        archetype_color = "emerald"
        archetype_icon = "fa-award"
        summary = "Maintains strong attendance, reliable internal scoring, and solid semester-over-semester momentum with low performance variance."
        strategy = "Maintain standard exam routines while pushing into advanced competitive programming, research paper publication, or Tier-1 hackathons."

    return {
        "archetype_code": archetype_code,
        "archetype_name": archetype_name,
        "archetype_title": archetype_title,
        "archetype_color": archetype_color,
        "archetype_icon": archetype_icon,
        "summary": summary,
        "tailored_strategy": strategy,
        "radar_traits": radar_traits
    }
