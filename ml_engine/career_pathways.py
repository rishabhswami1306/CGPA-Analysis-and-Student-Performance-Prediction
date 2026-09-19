from typing import Dict, Any, List
import numpy as np


def evaluate_multi_pathway_careers(
    cgpa: float,
    active_backlogs: int,
    attendance_pct: float,
    completed_records: List[Dict[str, Any]],
    ongoing_subjects: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates student academic profile across 4 distinct post-graduation tracks:
    1. Software Engineering / Tech Product Core
    2. Higher Studies & Global Research (MS / PhD)
    3. Competitive Exams & Public Sector (GATE / PSU)
    4. Techno-Management / Consulting / MBA
    """
    # Extract subject scores across history
    subject_marks = {}
    presentation_scores = []
    aptitude_scores = []
    math_scores = []
    core_cs_scores = []

    all_records = (completed_records or []) + ([{"subjects": ongoing_subjects}] if ongoing_subjects else [])
    
    for rec in all_records:
        for s in rec.get("subjects", []):
            code = s.get("subject_code", "").upper()
            total = float(s.get("total_marks", 0.0) or (s.get("tt1_score", 0.0) * 5.0) or 70.0)
            subject_marks[code] = total

            if any(k in code for k in ["M1", "M2", "M3", "EM", "MATH", "STATS"]):
                math_scores.append(total)
            if any(k in code for k in ["DS", "DAA", "OS", "CCN", "CN", "DBMS", "CS301", "CS302"]):
                core_cs_scores.append(total)
            
            if s.get("presentation_score") is not None:
                presentation_scores.append(float(s["presentation_score"]))
            if s.get("aptitude_score") is not None:
                aptitude_scores.append(float(s["aptitude_score"]))

    avg_math = float(np.mean(math_scores)) if math_scores else 70.0
    avg_core_cs = float(np.mean(core_cs_scores)) if core_cs_scores else 72.0
    avg_pres = float(np.mean(presentation_scores)) if presentation_scores else 7.5
    avg_apt = float(np.mean(aptitude_scores)) if aptitude_scores else 7.0

    # 1. TRACK 1: Software Engineering / Tech Product Core (SWE)
    # Weights: Core CS (40%), CGPA (30%), Zero Backlogs (20%), Aptitude (10%)
    swe_score = (avg_core_cs * 0.40) + ((cgpa / 10.0) * 100.0 * 0.30) + ((avg_apt / 10.0) * 100.0 * 0.10)
    if active_backlogs > 0:
        swe_score -= (active_backlogs * 15.0)
    swe_fit = min(98.0, max(20.0, round(swe_score, 1)))

    swe_strengths = ["Strong core computer science fundamentals" if avg_core_cs >= 70 else "Developing algorithmic foundation"]
    swe_gaps = []
    if avg_core_cs < 75: swe_gaps.append("Reinforce DSA & system design fundamentals")
    if active_backlogs > 0: swe_gaps.append("Clear active backlogs to unblock corporate drive eligibility")

    # 2. TRACK 2: Higher Studies & Global Research (MS / PhD / GRE)
    # Weights: CGPA (45%), Math/Stats (35%), Research/Theory consistency (20%)
    ms_score = ((cgpa / 10.0) * 100.0 * 0.45) + (avg_math * 0.35) + (avg_core_cs * 0.20)
    if active_backlogs > 0:
        ms_score -= (active_backlogs * 20.0)
    ms_fit = min(98.0, max(15.0, round(ms_score, 1)))

    ms_strengths = ["Consistent academic pedigree suitable for top-tier university admissions" if cgpa >= 8.0 else "Solid analytical base"]
    ms_gaps = []
    if cgpa < 8.0: ms_gaps.append("Push cumulative CGPA above 8.0+ for competitive global scholarships")
    if avg_math < 75: ms_gaps.append("Strengthen statistical rigor for university admissions tests (GRE/IELTS)")

    # 3. TRACK 3: Competitive Exams & Public Sector (GATE / PSU / IES)
    # Weights: Core CS breadth (45%), Math (35%), Consistency/Attendance (20%)
    gate_score = (avg_core_cs * 0.45) + (avg_math * 0.35) + (attendance_pct * 0.20)
    gate_fit = min(96.0, max(20.0, round(gate_score, 1)))

    gate_strengths = ["Solid conceptual mastery across formal syllabus subjects" if avg_core_cs >= 70 else "Moderate syllabus coverage"]
    gate_gaps = []
    if avg_math < 75: gate_gaps.append("Engineering Mathematics carries 15% of GATE marks — focus on Calculus & Linear Algebra")
    if avg_core_cs < 75: gate_gaps.append("Comprehensive revision of Operating Systems and Compiler Design")

    # 4. TRACK 4: Techno-Management / Consulting / MBA
    # Weights: Presentation/Communication (35%), Aptitude (30%), CGPA (25%), Attendance (10%)
    mba_score = ((avg_pres / 10.0) * 100.0 * 0.35) + ((avg_apt / 10.0) * 100.0 * 0.30) + ((cgpa / 10.0) * 100.0 * 0.25) + (attendance_pct * 0.10)
    mba_fit = min(98.0, max(25.0, round(mba_score, 1)))

    mba_strengths = ["Strong verbal presentation and interpersonal engagement" if avg_pres >= 7.5 else "Analytical mindset"]
    mba_gaps = []
    if avg_apt < 7.5: mba_gaps.append("Intensify quantitative aptitude & data interpretation speed for CAT/GMAT")

    # Determine highest fit track
    tracks = [
        {"id": "swe", "title": "Software Engineering & Product Core", "fit_pct": swe_fit, "icon": "fa-code", "color": "blue"},
        {"id": "ms", "title": "Higher Studies & Global Research (MS/PhD)", "fit_pct": ms_fit, "icon": "fa-graduation-cap", "color": "purple"},
        {"id": "gate", "title": "Public Sector & GATE (PSU/M.Tech)", "fit_pct": gate_fit, "icon": "fa-building-columns", "color": "emerald"},
        {"id": "mba", "title": "Techno-Management & Consulting (MBA)", "fit_pct": mba_fit, "icon": "fa-briefcase", "color": "amber"}
    ]
    tracks.sort(key=lambda x: x["fit_pct"], reverse=True)
    primary_recommendation = tracks[0]

    return {
        "primary_track": primary_recommendation["title"],
        "primary_track_id": primary_recommendation["id"],
        "primary_fit_pct": primary_recommendation["fit_pct"],
        "tracks": [
            {
                "id": "swe",
                "title": "Software Product & Tech Core",
                "category": "Corporate Engineering",
                "fit_percentage": swe_fit,
                "fit_label": "Exceptional Fit" if swe_fit >= 80 else ("High Fit" if swe_fit >= 65 else "Moderate Fit"),
                "color": "blue",
                "icon": "fa-laptop-code",
                "strengths": swe_strengths,
                "gap_areas": swe_gaps or ["Maintain LeetCode consistency"],
                "roadmap_milestones": [
                    "Complete 150+ LeetCode Medium problems across Trees, Graphs, and DP",
                    "Build an end-to-end full-stack or ML systems portfolio project with Docker deployment",
                    "Target Tier-1 Campus Placement Drives (12+ LPA)"
                ]
            },
            {
                "id": "ms",
                "title": "Higher Studies & Research (MS / PhD)",
                "category": "Academic & Research",
                "fit_percentage": ms_fit,
                "fit_label": "Exceptional Fit" if ms_fit >= 80 else ("High Fit" if ms_fit >= 65 else "Moderate Fit"),
                "color": "purple",
                "icon": "fa-microscope",
                "strengths": ms_strengths,
                "gap_areas": ms_gaps or ["Publish an IEEE/Springer conference paper"],
                "roadmap_milestones": [
                    "Collaborate with faculty on an IEEE/Springer conference publication",
                    "Prepare for GRE/IELTS and build a research statement of purpose (SOP)",
                    "Shortlist 10 target US/European universities for Fall admissions"
                ]
            },
            {
                "id": "gate",
                "title": "Public Sector & GATE (PSUs)",
                "category": "Government & Public Sector",
                "fit_percentage": gate_fit,
                "fit_label": "Exceptional Fit" if gate_fit >= 80 else ("High Fit" if gate_fit >= 65 else "Moderate Fit"),
                "color": "emerald",
                "icon": "fa-landmark",
                "strengths": gate_strengths,
                "gap_areas": gate_gaps or ["Take full-length timed mock tests"],
                "roadmap_milestones": [
                    "Master Engineering Mathematics and General Aptitude (30 total marks)",
                    "Complete topic-wise previous 15 years' GATE questions (PYQs)",
                    "Target All India Rank (AIR) < 500 for Direct PSU recruitment (IOCL, ONGC, ISRO)"
                ]
            },
            {
                "id": "mba",
                "title": "Techno-Management & Consulting",
                "category": "Business & Strategy",
                "fit_percentage": mba_fit,
                "fit_label": "Exceptional Fit" if mba_fit >= 80 else ("High Fit" if mba_fit >= 65 else "Moderate Fit"),
                "color": "amber",
                "icon": "fa-chart-line",
                "strengths": mba_strengths,
                "gap_areas": mba_gaps or ["Build case study problem-solving frameworks"],
                "roadmap_milestones": [
                    "Practice CAT/GMAT Quantitative Aptitude and Data Interpretation speed drills",
                    "Assume leadership positions in university technical committees or festivals",
                    "Target top consulting / product management corporate roles or IIMs"
                ]
            }
        ]
    }
