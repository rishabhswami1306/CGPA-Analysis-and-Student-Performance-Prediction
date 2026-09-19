import math
from utils.db import get_db

DEFAULT_COMPANIES = [
    # ─── TIER 1: SUPER DREAM & CORE PRODUCT (12+ LPA) ───────────────────────────
    {
        "company_id": "google",
        "name": "Google",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 28.0,
        "min_cgpa": 8.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 75.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 75.0,
        "min_12th_marks": 75.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-brands fa-google text-red-500",
        "required_skills": ["Data Structures", "Algorithms", "System Design", "Python", "C++"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment (DSA + Aptitude)", "Technical Round 1 (Algorithms)", "Technical Round 2 (System Design)", "Googleyness & Leadership"],
        "location": "Bengaluru / Hyderabad",
        "description": "Leading global technology company specializing in search, cloud infrastructure, AI models, and distributed systems."
    },
    {
        "company_id": "apple",
        "name": "Apple",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 32.0,
        "min_cgpa": 8.5,
        "max_backlogs": 0,
        "min_attendance": 80.0,
        "min_placement_score": 80.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 80.0,
        "min_12th_marks": 80.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "EXTC"],
        "role_title": "Core OS & Systems Software Engineer",
        "icon_class": "fa-brands fa-apple text-slate-800",
        "required_skills": ["C/C++", "Swift", "Operating Systems", "Computer Networks", "Low-level Optimization"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Coding Challenge", "Systems & OS Deep Dive", "Architecture Design", "Director Interview"],
        "location": "Bengaluru / Hyderabad",
        "description": "World-class consumer electronics and software ecosystem building high-performance operating systems."
    },
    {
        "company_id": "nvidia",
        "name": "NVIDIA",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 26.0,
        "min_cgpa": 8.3,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 75.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 75.0,
        "min_12th_marks": 75.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "GPU Acceleration & AI Systems Engineer",
        "icon_class": "fa-solid fa-microchip text-emerald-600",
        "required_skills": ["CUDA", "C++", "Computer Architecture", "Deep Learning", "Python"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment", "Technical 1 (C++ & Architecture)", "Technical 2 (GPU/AI)", "HR Fit"],
        "location": "Bengaluru / Pune",
        "description": "Global leader in accelerated computing, AI GPUs, deep learning platforms, and graphics hardware."
    },
    {
        "company_id": "microsoft",
        "name": "Microsoft",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 24.0,
        "min_cgpa": 8.2,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 70.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Software Development Engineer (SDE-1)",
        "icon_class": "fa-brands fa-microsoft text-blue-500",
        "required_skills": ["Data Structures", "Algorithms", "C++", "Java", "Azure"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Codility Online Assessment", "Technical Round 1", "Technical Round 2 (DSA)", "AA / Partner Round"],
        "location": "Hyderabad / Noida",
        "description": "Pioneering enterprise computing, developer tools, AI copilot platforms, and cloud infrastructure."
    },
    {
        "company_id": "de_shaw",
        "name": "D. E. Shaw",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 35.0,
        "min_cgpa": 8.8,
        "max_backlogs": 0,
        "min_attendance": 80.0,
        "min_placement_score": 85.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 80.0,
        "min_12th_marks": 80.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Quantitative Software Developer",
        "icon_class": "fa-solid fa-chart-line text-indigo-700",
        "required_skills": ["Advanced Algorithms", "C++", "Python", "Low Latency Systems", "Discrete Math"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Coding & Math Assessment", "Technical 1 (Advanced DSA)", "Technical 2 (Systems & OOP)", "Behavioral Round"],
        "location": "Hyderabad",
        "description": "Global investment and technology development firm with quantitative, algorithmic focus."
    },
    {
        "company_id": "uber",
        "name": "Uber",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 27.0,
        "min_cgpa": 8.2,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 75.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Backend Distributed Systems Engineer",
        "icon_class": "fa-brands fa-uber text-slate-900",
        "required_skills": ["Go", "Java", "Kafka", "Microservices", "System Design"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["HackerRank Coding Test", "Technical Interview 1", "Technical Interview 2 (Concurrency)", "Bar Raiser"],
        "location": "Bengaluru / Hyderabad",
        "description": "Global mobility platform building hyper-scale routing, distributed tracking, and fintech systems."
    },
    {
        "company_id": "atlassian",
        "name": "Atlassian",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 25.0,
        "min_cgpa": 8.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 70.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Cloud Infrastructure & SRE Engineer",
        "icon_class": "fa-brands fa-atlassian text-blue-600",
        "required_skills": ["Java", "Go", "Distributed Systems", "AWS", "Kubernetes"],
        "work_mode": "Remote",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment", "Data Structures & Coding", "System Design & Cloud", "Values & Culture Fit"],
        "location": "Bengaluru (Work from Anywhere)",
        "description": "Enterprise collaboration platform creating Jira, Confluence, Trello, and Bitbucket."
    },
    {
        "company_id": "adobe",
        "name": "Adobe",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 23.0,
        "min_cgpa": 8.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 70.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Creative Cloud & Computer Vision Engineer",
        "icon_class": "fa-solid fa-cube text-red-600",
        "required_skills": ["C++", "Python", "Computer Vision", "Algorithms", "Multithreading"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["HackerEarth Online Test", "Technical Round 1", "Technical Round 2 (Algorithms)", "Director Round"],
        "location": "Noida / Bengaluru",
        "description": "Digital creativity and document cloud leader powering Photoshop, Premiere, and Firefly AI."
    },
    {
        "company_id": "amazon",
        "name": "Amazon",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 22.0,
        "min_cgpa": 7.8,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 70.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Software Development Engineer (SDE-I)",
        "icon_class": "fa-brands fa-amazon text-amber-500",
        "required_skills": ["DSA", "OOP", "System Design", "Java", "AWS"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment (1 & 2)", "Technical Interview 1 (DSA)", "Technical Interview 2 (OOP)", "Bar Raiser (LP)"],
        "location": "Bengaluru / Chennai / Hyderabad",
        "description": "Global e-commerce and cloud computing giant seeking strong problem solvers."
    },
    {
        "company_id": "salesforce",
        "name": "Salesforce",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 21.0,
        "min_cgpa": 7.8,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 68.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Cloud Platform Software Engineer",
        "icon_class": "fa-brands fa-salesforce text-sky-500",
        "required_skills": ["Java", "Cloud Architecture", "REST APIs", "Microservices", "DBMS"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["HackerRank OA", "Technical Round 1 (DSA)", "Technical Round 2 (Design)", "Hiring Manager"],
        "location": "Hyderabad / Bengaluru",
        "description": "World-leading CRM software platform delivering multi-tenant cloud enterprise solutions."
    },
    {
        "company_id": "goldman_sachs",
        "name": "Goldman Sachs",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 20.0,
        "min_cgpa": 8.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 70.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 75.0,
        "min_12th_marks": 75.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Engineering Analyst",
        "icon_class": "fa-solid fa-coins text-yellow-500",
        "required_skills": ["Algorithms", "Discrete Math", "Java", "Python", "SQL"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Aptitude & Coding OA", "Technical 1 (Math & DSA)", "Technical 2 (Core CS)", "HR Round"],
        "location": "Bengaluru",
        "description": "Tier-1 investment bank hiring high-performance computing engineers for electronic trading."
    },
    {
        "company_id": "morgan_stanley",
        "name": "Morgan Stanley",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 19.5,
        "min_cgpa": 7.8,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 68.0,
        "max_academic_gap_years": 0,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Technology Analyst — Investment Systems",
        "icon_class": "fa-solid fa-landmark text-blue-800",
        "required_skills": ["Core Java", "Spring Boot", "SQL", "Linux", "Multithreading"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment", "Technical 1 (Core Java & DBMS)", "Technical 2 (Problem Solving)", "Professional Fit"],
        "location": "Mumbai / Bengaluru",
        "description": "Global financial services leader engineering mission-critical trading and risk engines."
    },
    {
        "company_id": "qualcomm",
        "name": "Qualcomm",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 18.0,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 65.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Embedded Software & Wireless Systems Engineer",
        "icon_class": "fa-solid fa-signal text-cyan-600",
        "required_skills": ["C", "RTOS", "Device Drivers", "Computer Architecture", "Embedded Systems"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Aptitude & C Programming OA", "Technical Round 1 (C & OS)", "Technical Round 2 (Architecture)", "HR"],
        "location": "Hyderabad / Bengaluru / Chennai",
        "description": "Telecommunications and semiconductor pioneer developing Snapdragon processors and 5G connectivity."
    },
    {
        "company_id": "jpmorgan",
        "name": "JPMorgan Chase & Co.",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Super Dream",
        "package_lpa": 17.5,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 65.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 70.0,
        "min_12th_marks": 70.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Software Engineer — Global Technology",
        "icon_class": "fa-solid fa-building-columns text-slate-700",
        "required_skills": ["Python", "Java", "Cloud Computing", "Microservices", "Agile"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Coding Challenge (Code for Good)", "Technical Round 1", "Technical Round 2", "Values Interview"],
        "location": "Mumbai / Bengaluru / Hyderabad",
        "description": "Leading global financial institution investing heavily in cloud modernization and cyber security."
    },
    {
        "company_id": "cisco",
        "name": "Cisco Systems",
        "tier": "Tier 1 — High CTC / Product Core (12+ LPA)",
        "tier_level": 1,
        "hiring_category": "Dream",
        "package_lpa": 14.5,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 60.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Software Engineer (Networking & Security)",
        "icon_class": "fa-solid fa-network-wired text-cyan-600",
        "required_skills": ["Computer Networks", "Python", "Linux", "Operating Systems"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Networking & Coding OA", "Technical Round 1", "Technical Round 2", "Managerial & HR"],
        "location": "Bengaluru",
        "description": "World leader in networking hardware, software, and cybersecurity solutions."
    },

    # ─── TIER 2: PREMIER TECH SOLUTIONS & GROWTH PRODUCT (6–12 LPA) ─────────────
    {
        "company_id": "walmart",
        "name": "Walmart Global Tech",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 12.0,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 65.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-solid fa-cart-shopping text-yellow-500",
        "required_skills": ["Java", "Spring", "Microservices", "Docker", "NoSQL"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Online Assessment", "Technical 1 (DSA)", "Technical 2 (System Concepts)", "HR Round"],
        "location": "Bengaluru / Chennai",
        "description": "Technology arm of the Fortune 1 retail powerhouse building high-scale distributed supply chains."
    },
    {
        "company_id": "barclays",
        "name": "Barclays",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 11.5,
        "min_cgpa": 7.2,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 60.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Graduate Technology Developer",
        "icon_class": "fa-solid fa-shield-halved text-sky-600",
        "required_skills": ["Java", "Spring Boot", "AWS", "Angular/React", "CI/CD"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Online Technical Assessment", "Technical Interview", "Strength-Based Behavioral Interview"],
        "location": "Pune",
        "description": "British universal bank driving digital banking innovations, payments, and wealth platforms."
    },
    {
        "company_id": "amd",
        "name": "AMD",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 11.0,
        "min_cgpa": 7.2,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 60.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "EXTC"],
        "role_title": "Silicon & Software Design Engineer",
        "icon_class": "fa-solid fa-server text-red-500",
        "required_skills": ["C++", "Python", "Verilog/VHDL", "Operating Systems", "Linux"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Coding & Hardware OA", "Technical Round 1", "Technical Round 2", "HR"],
        "location": "Hyderabad / Bengaluru",
        "description": "Semiconductor innovator delivering processors, graphics cards, and datacenter solutions."
    },
    {
        "company_id": "oracle",
        "name": "Oracle",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 11.0,
        "min_cgpa": 7.2,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 60.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 65.0,
        "min_12th_marks": 65.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Associate Software Consultant",
        "icon_class": "fa-solid fa-database text-red-600",
        "required_skills": ["DBMS", "SQL", "Java", "Cloud Infrastructure"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Coding & Aptitude Test", "Technical Interview 1 (DBMS/SQL)", "Technical Interview 2 (DSA)", "HR Interview"],
        "location": "Bengaluru / Hyderabad",
        "description": "Premier database and enterprise cloud software solutions provider."
    },
    {
        "company_id": "zomato",
        "name": "Zomato",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 10.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 58.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Backend Platform Engineer",
        "icon_class": "fa-solid fa-bowl-food text-red-500",
        "required_skills": ["Python", "Node.js", "Redis", "MongoDB", "System Design"],
        "work_mode": "On-site",
        "service_bond_months": 0,
        "interview_rounds": ["Machine Coding Round", "Technical Problem Solving", "System Architecture", "Founders / Culture"],
        "location": "Gurugram",
        "description": "India's premier food ordering, delivery, and quick commerce engineering ecosystem."
    },
    {
        "company_id": "infosys_sp",
        "name": "Infosys Specialist Programmer (SP)",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 9.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 60.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Specialist Programmer",
        "icon_class": "fa-solid fa-code text-blue-700",
        "required_skills": ["Advanced Algorithms", "Competitive Programming", "Java", "Python"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["HackWithInfy Coding Contest", "Advanced DSA Interview", "Technical Assessment", "HR Round"],
        "location": "Bengaluru / Pune",
        "description": "Elite high-package coding role focusing on modern microservices and AI solutions."
    },
    {
        "company_id": "deloitte",
        "name": "Deloitte",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 8.5,
        "min_cgpa": 7.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 55.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Analyst — Technology Consulting",
        "icon_class": "fa-solid fa-briefcase text-emerald-600",
        "required_skills": ["Data Analytics", "Python", "SQL", "Consulting Problem Solving"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Cognitive & Technical OA", "Case Study / Group Discussion", "Technical Interview", "Partner Interview"],
        "location": "Mumbai / Pune / Hyderabad",
        "description": "Global advisory and digital transformation consulting leader."
    },
    {
        "company_id": "ibm",
        "name": "IBM",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 8.0,
        "min_cgpa": 6.8,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 50.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Cloud & Cognitive Software Developer",
        "icon_class": "fa-brands fa-ibm text-blue-800",
        "required_skills": ["Python", "Cloud Computing", "Red Hat Linux", "AI Basics", "SQL"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Cognitive Ability Games", "Coding Assessment", "Technical Interview", "HR Evaluation"],
        "location": "Bengaluru / Pune / Kochi",
        "description": "Enterprise cloud computing, watsonx AI, and foundational computing architecture leader."
    },
    {
        "company_id": "tcs_digital",
        "name": "TCS Digital",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 7.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 55.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Digital Technology Specialist",
        "icon_class": "fa-solid fa-laptop-code text-indigo-600",
        "required_skills": ["Data Structures", "Python", "Full Stack Development", "Cloud Basics"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["TCS NQT Advanced Cognitive & Coding", "Technical Interview", "Managerial Interview", "HR Interview"],
        "location": "Pan-India",
        "description": "High-growth digital engineering wing of Tata Consultancy Services."
    },
    {
        "company_id": "capgemini_digital",
        "name": "Capgemini Digital",
        "tier": "Tier 2 — Premier Tech Solutions (6–12 LPA)",
        "tier_level": 2,
        "hiring_category": "Dream",
        "package_lpa": 7.2,
        "min_cgpa": 6.8,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 50.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Senior Digital Analyst",
        "icon_class": "fa-solid fa-gem text-blue-500",
        "required_skills": ["Java", "Full Stack Web", "SQL", "Cloud Platforms"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Aptitude & Technical OA", "Game-Based Aptitude", "Technical Interview", "HR Round"],
        "location": "Mumbai / Pune / Bengaluru",
        "description": "Global business and digital engineering consulting company creating intelligent industry solutions."
    },

    # ─── TIER 3: MASS RECRUITMENT / FOUNDATION (3.5–6 LPA) ──────────────────────
    {
        "company_id": "persistent",
        "name": "Persistent Systems",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 5.0,
        "min_cgpa": 6.5,
        "max_backlogs": 0,
        "min_attendance": 75.0,
        "min_placement_score": 45.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS"],
        "role_title": "Software Engineer Trainee",
        "icon_class": "fa-solid fa-bolt text-amber-500",
        "required_skills": ["Core Java", "OOP", "Data Structures", "Git"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Coding & MCQs OA", "Technical Round 1", "HR Round"],
        "location": "Pune / Nagpur / Goa",
        "description": "Digital product engineering and enterprise modernization specialist."
    },
    {
        "company_id": "accenture_ase",
        "name": "Accenture",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 4.8,
        "min_cgpa": 6.5,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 45.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-solid fa-chevron-right text-purple-600",
        "required_skills": ["Core Programming", "SQL", "Agile Methodologies"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Cognitive & Technical Assessment", "Coding Assessment", "Communication Assessment", "HR Interview"],
        "location": "Pan-India",
        "description": "Global professional services company with leading digital capabilities."
    },
    {
        "company_id": "lti_mindtree",
        "name": "LTI Mindtree",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 4.5,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 40.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Graduate Engineer Trainee",
        "icon_class": "fa-solid fa-tree text-emerald-600",
        "required_skills": ["C#", ".NET", "Java", "SQL", "Cloud Fundamentals"],
        "work_mode": "Hybrid",
        "service_bond_months": 24,
        "interview_rounds": ["Online Technical & Aptitude Test", "Technical Interview", "HR Interview"],
        "location": "Mumbai / Pune / Chennai",
        "description": "Global technology consulting and digital solutions enterprise."
    },
    {
        "company_id": "cognizant_genc",
        "name": "Cognizant GenC",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 4.2,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 40.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Programmer Analyst Trainee",
        "icon_class": "fa-solid fa-gear text-teal-600",
        "required_skills": ["Java", "Database Basics", "Software Testing"],
        "work_mode": "Hybrid",
        "service_bond_months": 0,
        "interview_rounds": ["Aptitude & Communication Round", "Technical Interview", "HR Round"],
        "location": "Chennai / Pune / Coimbatore",
        "description": "Enterprise digital and modernization engineering partner."
    },
    {
        "company_id": "wipro_elite",
        "name": "Wipro Elite / Turbo",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 4.0,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 40.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Project Engineer",
        "icon_class": "fa-solid fa-circle-nodes text-blue-500",
        "required_skills": ["Java/Python", "Problem Solving", "DBMS", "Web Basics"],
        "work_mode": "Hybrid",
        "service_bond_months": 12,
        "interview_rounds": ["National Talent Hunt OA", "Written Communication Test", "Technical + HR Interview"],
        "location": "Pan-India",
        "description": "Leading technology services and consulting company driving digital agility."
    },
    {
        "company_id": "tech_mahindra",
        "name": "Tech Mahindra",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 3.8,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 40.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Associate Software Engineer",
        "icon_class": "fa-solid fa-cubes text-red-600",
        "required_skills": ["C/C++", "Java", "SQL", "Communication"],
        "work_mode": "Hybrid",
        "service_bond_months": 24,
        "interview_rounds": ["Aptitude Test", "Technical Assessment", "Conversational Test", "HR Interview"],
        "location": "Pune / Hyderabad / Noida",
        "description": "Connected world specialist providing digital solutions for telecoms and enterprises."
    },
    {
        "company_id": "tcs_ninja",
        "name": "TCS Ninja",
        "tier": "Tier 3 — Mass Recruitment / Foundation (3.5–6 LPA)",
        "tier_level": 3,
        "hiring_category": "Regular",
        "package_lpa": 3.8,
        "min_cgpa": 6.0,
        "max_backlogs": 1,
        "min_attendance": 75.0,
        "min_placement_score": 40.0,
        "max_academic_gap_years": 1,
        "min_10th_marks": 60.0,
        "min_12th_marks": 60.0,
        "eligible_branches": ["CSE", "CSE-DS", "IT", "AIDS", "EXTC"],
        "role_title": "Assistant System Engineer",
        "icon_class": "fa-solid fa-building text-slate-600",
        "required_skills": ["C/C++", "Analytical Aptitude", "Basic Scripting"],
        "work_mode": "Hybrid",
        "service_bond_months": 12,
        "interview_rounds": ["TCS NQT Foundation", "Technical Interview", "Managerial & HR Interview"],
        "location": "Pan-India",
        "description": "Foundational graduate technology engineering programme."
    }
]


def get_companies_list(db=None) -> list:
    """Fetches companies from MongoDB or seeds/syncs institutional catalog."""
    if db is None:
        db = get_db()

    try:
        # Upsert catalog items to ensure new companies and updated criteria are synced
        for c in DEFAULT_COMPANIES:
            db.companies.update_one({"company_id": c["company_id"]}, {"$set": c}, upsert=True)

        companies = list(db.companies.find({}))
        if companies:
            for c in companies:
                c.pop("_id", None)
            return companies
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
    student_attendance: float = 85.0,
    student_placement_score: float = 75.0,
    academic_gap_years: int = 0,
    tenth_marks: float = 85.0,
    twelfth_marks: float = 82.0,
    db=None
) -> dict:
    """
    Evaluates student against all recruitment companies with multiple institutional criteria:
    - Minimum CGPA
    - Backlog tolerance
    - Department / Branch restriction
    - Institutional Attendance compliance (e.g. >= 75%)
    - ML Placement Readiness Score
    - Academic Education Gap Years
    - 10th & 12th Marks Cutoffs
    Computes Dream Company Target Simulator metrics and breakdown.
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
        att_threshold = float(c.get("min_attendance", 75.0))
        attendance_ok = float(student_attendance) >= att_threshold
        min_score = float(c.get("min_placement_score", 0.0))
        placement_score_ok = float(student_placement_score) >= min_score
        max_gap = int(c.get("max_academic_gap_years", 1))
        gap_ok = int(academic_gap_years) <= max_gap
        tenth_ok = float(tenth_marks) >= float(c.get("min_10th_marks", 60.0))
        twelfth_ok = float(twelfth_marks) >= float(c.get("min_12th_marks", 60.0))

        is_eligible = (
            branch_ok and cgpa_ok and backlog_ok and attendance_ok and
            placement_score_ok and gap_ok and tenth_ok and twelfth_ok
        )

        # Determine detailed status tag & informative human label
        if is_eligible:
            status_tag = "ELIGIBLE"
            status_label = "Eligible for Placement Drive"
            status_color = "emerald"
        elif not attendance_ok:
            status_tag = "ATTENDANCE_SHORTFALL"
            status_label = f"Attendance Below Cutoff ({student_attendance:.1f}% / {att_threshold}%)"
            status_color = "purple"
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
        elif not backlog_ok:
            status_tag = "BACKLOG_RESTRICTED"
            status_label = f"Backlog Restriction (Max {c.get('max_backlogs')} Allowed)"
            status_color = "rose"
        elif not placement_score_ok:
            status_tag = "SCORE_SHORTFALL"
            status_label = f"Readiness Shortfall ({student_placement_score:.0f}% / {min_score:.0f}%)"
            status_color = "orange"
        else:
            status_tag = "ACADEMIC_CUTOFF_UNMET"
            status_label = "10th/12th or Academic Gap Cutoff Unmet"
            status_color = "slate"

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
            "attendance_ok": attendance_ok,
            "cgpa_ok": cgpa_ok,
            "backlog_ok": backlog_ok,
            "branch_ok": branch_ok,
            "placement_score_ok": placement_score_ok,
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
        "student_attendance": student_attendance,
        "student_placement_score": student_placement_score,
        "completed_credits": completed_credits,
        "total_companies": len(evaluated_companies),
        "eligible_count": eligible_count,
        "highest_eligible_package": highest_eligible_package,
        "avg_eligible_package": avg_eligible_package,
        "companies": evaluated_companies
    }
