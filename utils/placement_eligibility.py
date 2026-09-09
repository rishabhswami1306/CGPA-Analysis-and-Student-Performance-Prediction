import math
from utils.db import get_db

DEFAULT_COMPANIES = [
    {
        "company_id": "google",
        "name": "Google",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "package_lpa": 28.0,
        "min_cgpa": 8.5,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-brands fa-google text-red-500",
        "required_skills": ["Data Structures", "Algorithms", "System Design", "Python", "C++"],
        "location": "Bengaluru / Hyderabad",
        "description": "Leading global technology company specializing in cloud, search, and AI innovations."
    },
    {
        "company_id": "microsoft",
        "name": "Microsoft",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "package_lpa": 24.0,
        "min_cgpa": 8.2,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Software Development Engineer (SDE-1)",
        "icon_class": "fa-brands fa-microsoft text-blue-500",
        "required_skills": ["Data Structures", "Algorithms", "C++", "Java", "Azure"],
        "location": "Hyderabad / Noida",
        "description": "Pioneering enterprise computing, developer tools, and cloud infrastructure."
    },
    {
        "company_id": "amazon",
        "name": "Amazon",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "package_lpa": 22.0,
        "min_cgpa": 7.8,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Software Development Engineer (SDE-I)",
        "icon_class": "fa-brands fa-amazon text-amber-500",
        "required_skills": ["DSA", "OOP", "System Design", "Java", "AWS"],
        "location": "Bengaluru / Chennai",
        "description": "Global e-commerce and cloud computing giant seeking strong problem solvers."
    },
    {
        "company_id": "goldman_sachs",
        "name": "Goldman Sachs",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "package_lpa": 20.0,
        "min_cgpa": 8.0,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Engineering Analyst",
        "icon_class": "fa-solid fa-coins text-yellow-500",
        "required_skills": ["Algorithms", "Discrete Math", "Java", "Python", "SQL"],
        "location": "Bengaluru",
        "description": "Tier-1 investment bank hiring high-performance computing engineers."
    },
    {
        "company_id": "cisco",
        "name": "Cisco Systems",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "package_lpa": 14.5,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Software Engineer (Networking & Security)",
        "icon_class": "fa-solid fa-network-wired text-cyan-600",
        "required_skills": ["Computer Networks", "Python", "Linux", "Operating Systems"],
        "location": "Bengaluru",
        "description": "World leader in networking hardware, software, and cybersecurity solutions."
    },
    {
        "company_id": "oracle",
        "name": "Oracle",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "package_lpa": 11.0,
        "min_cgpa": 7.2,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Associate Software Consultant",
        "icon_class": "fa-solid fa-database text-red-600",
        "required_skills": ["DBMS", "SQL", "Java", "Cloud Infrastructure"],
        "location": "Bengaluru / Hyderabad",
        "description": "Premier database and enterprise cloud software solutions provider."
    },
    {
        "company_id": "deloitte",
        "name": "Deloitte",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "package_lpa": 8.5,
        "min_cgpa": 7.0,
        "max_backlogs": 1,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Analyst — Technology Consulting",
        "icon_class": "fa-solid fa-briefcase text-emerald-600",
        "required_skills": ["Data Analytics", "Python", "SQL", "Consulting Problem Solving"],
        "location": "Mumbai / Pune / Hyderabad",
        "description": "Global advisory and digital transformation consulting leader."
    },
    {
        "company_id": "tcs_digital",
        "name": "TCS Digital",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "package_lpa": 7.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Digital Technology Specialist",
        "icon_class": "fa-solid fa-laptop-code text-indigo-600",
        "required_skills": ["Data Structures", "Python", "Full Stack Development", "Cloud Basics"],
        "location": "Pan-India",
        "description": "High-growth digital engineering wing of Tata Consultancy Services."
    },
    {
        "company_id": "infosys_sp",
        "name": "Infosys Specialist Programmer (SP)",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "package_lpa": 9.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Specialist Programmer",
        "icon_class": "fa-solid fa-code text-blue-700",
        "required_skills": ["Advanced Algorithms", "Competitive Programming", "Java", "Python"],
        "location": "Bengaluru / Pune",
        "description": "Elite high-package coding role focusing on modern microservices and AI solutions."
    },
    {
        "company_id": "accenture_ase",
        "name": "Accenture",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "package_lpa": 4.8,
        "min_cgpa": 6.5,
        "max_backlogs": 1,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-solid fa-chevron-right text-purple-600",
        "required_skills": ["Core Programming", "SQL", "Agile Methodologies"],
        "location": "Pan-India",
        "description": "Global professional services company with leading digital capabilities."
    },
    {
        "company_id": "cognizant_genc",
        "name": "Cognizant GenC",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "package_lpa": 4.2,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Programmer Analyst Trainee",
        "icon_class": "fa-solid fa-gear text-teal-600",
        "required_skills": ["Java", "Database Basics", "Software Testing"],
        "location": "Chennai / Pune / Coimbatore",
        "description": "Enterprise digital and modernization engineering partner."
    },
    {
        "company_id": "tcs_ninja",
        "name": "TCS Ninja",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "package_lpa": 3.8,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Assistant System Engineer",
        "icon_class": "fa-solid fa-building text-slate-600",
        "required_skills": ["C/C++", "Analytical Aptitude", "Basic Scripting"],
        "location": "Pan-India",
        "description": "Foundational graduate technology engineering programme."
    }
]


def get_companies_list(db=None) -> list:
    """Fetches companies from MongoDB or falls back to standard institutional seed catalog."""
    if db is None:
        db = get_db()
    
    try:
        companies = list(db.companies.find({}))
        if companies:
            for c in companies:
                c.pop("_id", None)
            return companies
        
        # Seed into DB if collection is empty
        for c in DEFAULT_COMPANIES:
            db.companies.update_one({"company_id": c["company_id"]}, {"$set": c}, upsert=True)
        return DEFAULT_COMPANIES
    except Exception:
        return DEFAULT_COMPANIES


def solve_dream_target_sgpa(
    current_cgpa: float,
    completed_credits: int,
    target_cgpa: float,
    next_sem_credits: int = 20
) -> dict:
    """
    Solves the exact next-semester SGPA required to reach target_cgpa:
    Target CGPA = (Current CGPA * Completed Credits + Required SGPA * Next Sem Credits) / (Completed + Next Sem)
    Required SGPA = [Target CGPA * (Completed + Next Sem) - (Current CGPA * Completed)] / Next Sem
    """
    if completed_credits <= 0:
        return {
            "required_sgpa": round(target_cgpa, 2),
            "is_achievable_next_sem": target_cgpa <= 10.0,
            "cgpa_gap": 0.0,
            "target_cgpa": target_cgpa,
            "feasibility": "ACHIEVABLE" if target_cgpa <= 10.0 else "IMPOSSIBLE"
        }

    total_credits_after = completed_credits + next_sem_credits
    required_points = (target_cgpa * total_credits_after) - (current_cgpa * completed_credits)
    required_sgpa = required_points / float(next_sem_credits)

    cgpa_gap = max(0.0, round(target_cgpa - current_cgpa, 2))

    if required_sgpa <= 10.0:
        feasibility = "EASY" if required_sgpa <= (current_cgpa + 0.3) else "ACHIEVABLE"
    elif required_sgpa <= 10.5:
        feasibility = "STRETCH_GOAL"
    else:
        feasibility = "MULTI_SEMESTER_NEEDED"

    return {
        "required_sgpa": round(required_sgpa, 2),
        "is_achievable_next_sem": required_sgpa <= 10.0,
        "cgpa_gap": cgpa_gap,
        "target_cgpa": target_cgpa,
        "next_sem_credits": next_sem_credits,
        "feasibility": feasibility
    }


def evaluate_company_eligibility(
    student_cgpa: float,
    total_backlogs: int,
    branch: str,
    completed_credits: int,
    current_sem_credits: int = 20,
    db=None
) -> dict:
    """
    Evaluates student against all recruitment companies, categorizes eligibility,
    and computes the Dream Company Target Simulator metrics.
    """
    companies = get_companies_list(db)
    student_branch = (branch or "CSE").strip().upper()

    evaluated_companies = []
    eligible_count = 0
    total_eligible_package = 0.0
    highest_eligible_package = 0.0

    for c in companies:
        branch_ok = student_branch in [b.upper() for b in c.get("eligible_branches", [])]
        cgpa_ok = student_cgpa >= c.get("min_cgpa", 6.0)
        backlog_ok = total_backlogs <= c.get("max_backlogs", 0)

        is_eligible = branch_ok and cgpa_ok and backlog_ok

        # Determine detailed status tag & reason
        if is_eligible:
            status_tag = "ELIGIBLE"
            status_label = "Eligible for Placement Drive"
            status_color = "emerald"
        elif not branch_ok:
            status_tag = "BRANCH_RESTRICTED"
            status_label = f"Department Restriction (Requires: {', '.join(c.get('eligible_branches', []))})"
            status_color = "slate"
        elif not cgpa_ok and not backlog_ok:
            status_tag = "CGPA_AND_BACKLOG"
            status_label = f"Shortfall: CGPA & {total_backlogs} Active Backlog(s)"
            status_color = "red"
        elif not cgpa_ok:
            cgpa_diff = round(c.get("min_cgpa") - student_cgpa, 2)
            status_tag = "CGPA_SHORTFALL"
            status_label = f"CGPA Shortfall (-{cgpa_diff:.2f})"
            status_color = "amber"
        else:
            status_tag = "BACKLOG_RESTRICTED"
            status_label = f"Backlog Restriction (Max {c.get('max_backlogs')} Allowed)"
            status_color = "rose"

        # Calculate Dream Unlocker target if not eligible due to CGPA
        unlock_target = solve_dream_target_sgpa(
            current_cgpa=student_cgpa,
            completed_credits=completed_credits,
            target_cgpa=c.get("min_cgpa", 7.0),
            next_sem_credits=current_sem_credits
        )

        comp_data = dict(c)
        comp_data.update({
            "is_eligible": is_eligible,
            "status_tag": status_tag,
            "status_label": status_label,
            "status_color": status_color,
            "unlock_target": unlock_target
        })

        if is_eligible:
            eligible_count += 1
            pkg = float(c.get("package_lpa", 0.0))
            total_eligible_package += pkg
            if pkg > highest_eligible_package:
                highest_eligible_package = pkg

        evaluated_companies.append(comp_data)

    # Sort: Eligible first (highest package to lowest), then locked by package descending
    evaluated_companies.sort(
        key=lambda x: (1 if x["is_eligible"] else 0, x.get("package_lpa", 0.0)),
        reverse=True
    )

    avg_eligible_package = round(total_eligible_package / eligible_count, 1) if eligible_count > 0 else 0.0

    return {
        "student_cgpa": student_cgpa,
        "student_backlogs": total_backlogs,
        "student_branch": student_branch,
        "completed_credits": completed_credits,
        "total_companies": len(evaluated_companies),
        "eligible_count": eligible_count,
        "highest_eligible_package": highest_eligible_package,
        "avg_eligible_package": avg_eligible_package,
        "companies": evaluated_companies
    }
