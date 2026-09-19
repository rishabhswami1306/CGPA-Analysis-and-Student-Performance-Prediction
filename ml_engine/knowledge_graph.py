from typing import List, Dict, Any

# Curriculum Prerequisite Dependency Graph (DAG) for Computer Engineering & Data Science
CURRICULUM_PREREQUISITE_GRAPH = {
    # Active Course: [List of prerequisite courses with code, name, and key concepts]
    "DAA": [
        {"code": "CS201", "alt_codes": ["DS", "CS301"], "name": "Data Structures", "concepts": "Trees, Graphs, Sorting & Complexity Analysis", "weight": 0.85},
        {"code": "CS101", "alt_codes": ["CP", "PPS"], "name": "Programming in C / OOP", "concepts": "Pointers, Recursion, Memory Management", "weight": 0.65}
    ],
    "ML-II": [
        {"code": "DS401", "alt_codes": ["ML-I", "ML1"], "name": "Machine Learning - I", "concepts": "Regression, Classification, Bias-Variance Tradeoff", "weight": 0.90},
        {"code": "MA301", "alt_codes": ["EM", "M3", "MATH3"], "name": "Engineering Mathematics-III", "concepts": "Linear Algebra, Probability Distributions, Vector Calculus", "weight": 0.80}
    ],
    "IS": [
        {"code": "CS402", "alt_codes": ["CCN", "CN"], "name": "Computer Communication Networks", "concepts": "OSI Model, TCP/IP, Cryptographic Handshakes", "weight": 0.80},
        {"code": "CS302", "alt_codes": ["OS"], "name": "Operating Systems", "concepts": "Access Controls, Kernel Security, Privilege Separation", "weight": 0.60}
    ],
    "CCS": [
        {"code": "CS302", "alt_codes": ["OS"], "name": "Operating Systems", "concepts": "Virtualization, Thread Scheduling, Distributed Storage", "weight": 0.75},
        {"code": "CS402", "alt_codes": ["CCN"], "name": "Computer Communication Networks", "concepts": "Socket Programming, Subnets, Routing Protocols", "weight": 0.70}
    ],
    "CI": [
        {"code": "MA301", "alt_codes": ["EM", "M3"], "name": "Engineering Mathematics-III", "concepts": "Optimization, Convexity, Heuristics", "weight": 0.70}
    ]
}

# Bridge Remedial Modules corresponding to identified prerequisite weaknesses
REMEDIAL_BRIDGE_MODULES = {
    "Data Structures": {
        "title": "Data Structures & Algorithmic Foundations Bridge",
        "key_topics": ["Graph Traversals (BFS/DFS)", "Master Theorem for Divide & Conquer", "Dynamic Programming Memoization"],
        "est_hours": 8,
        "impact_courses": ["DAA", "Core Placement Coding"]
    },
    "Engineering Mathematics-III": {
        "title": "Linear Algebra & Probability Foundations for ML",
        "key_topics": ["Eigenvalues & SVD Decompositions", "Multivariate Normal Distributions", "Bayes Rule & Maximum Likelihood"],
        "est_hours": 6,
        "impact_courses": ["ML-II", "CI"]
    },
    "Computer Communication Networks": {
        "title": "Network Protocols & Cyber Defense Bridge",
        "key_topics": ["Public Key Infrastructure (PKI)", "TLS/SSL Protocol Architecture", "Packet Sniffing & Firewall Rules"],
        "est_hours": 5,
        "impact_courses": ["IS", "CCS"]
    },
    "Operating Systems": {
        "title": "Systems Virtualization & Concurrency Bridge",
        "key_topics": ["Process Concurrency & Mutex Locks", "Containerization Primitives (cgroups/namespaces)", "Virtual Memory Paging"],
        "est_hours": 6,
        "impact_courses": ["CCS", "IS"]
    }
}


def analyze_prerequisite_knowledge_graph(
    completed_records: List[Dict[str, Any]],
    active_subjects: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Traces past student performance along the curriculum DAG to compute
    Prerequisite Vulnerability Index (PVI) and prescribe bridge modules.
    """
    # Build historical course mastery map: {course_code_or_name: grade_point}
    mastery_map = {}
    for rec in completed_records:
        for sub in rec.get("subjects", []):
            code = sub.get("subject_code", "").upper()
            name = sub.get("subject_name", "").upper()
            grade_pt = sub.get("grade_point")
            total = sub.get("total_marks")
            
            if grade_pt is None:
                if total is not None:
                    if total >= 80: grade_pt = 10
                    elif total >= 70: grade_pt = 8
                    elif total >= 60: grade_pt = 7
                    elif total >= 40: grade_pt = 4
                    else: grade_pt = 0
                else:
                    grade_pt = 7.0
            
            mastery_map[code] = float(grade_pt)
            mastery_map[name] = float(grade_pt)

    vulnerable_courses = []
    recommended_bridge_modules = []
    seen_bridges = set()

    for active_sub in active_subjects:
        active_code = active_sub.get("subject_code", "")
        prereqs = CURRICULUM_PREREQUISITE_GRAPH.get(active_code, [])
        if not prereqs:
            continue

        course_vulnerabilities = []
        max_pvi = 0.0

        for prereq in prereqs:
            # Check mastery of prerequisite
            p_code = prereq["code"].upper()
            alt_codes = [c.upper() for c in prereq.get("alt_codes", [])]
            p_name = prereq["name"].upper()

            # Find matching grade in history
            matching_grade = None
            for key in [p_code] + alt_codes:
                if key in mastery_map:
                    matching_grade = mastery_map[key]
                    break
            if matching_grade is None:
                for hist_key, g in mastery_map.items():
                    if prereq["name"].upper() in hist_key:
                        matching_grade = g
                        break

            # If grade not found or low (grade point <= 6 or marks < 60)
            if matching_grade is not None and matching_grade < 7.0:
                # Weakness detected in prerequisite!
                # PVI = (7.0 - grade) / 7.0 * weight
                deficit = max(0.0, 7.0 - matching_grade)
                pvi = round((deficit / 7.0) * prereq["weight"] * 100.0, 1)
                
                if pvi > max_pvi:
                    max_pvi = pvi

                vuln_entry = {
                    "prerequisite_name": prereq["name"],
                    "prerequisite_code": prereq["code"],
                    "historical_grade_point": matching_grade,
                    "historical_grade_label": "Grade C / Marginal Pass" if matching_grade <= 5 else "Grade B",
                    "vulnerability_score": pvi,
                    "critical_concepts": prereq["concepts"]
                }
                course_vulnerabilities.append(vuln_entry)

                # Add bridge module recommendation
                b_name = prereq["name"]
                if b_name in REMEDIAL_BRIDGE_MODULES and b_name not in seen_bridges:
                    seen_bridges.add(b_name)
                    b_data = REMEDIAL_BRIDGE_MODULES[b_name]
                    recommended_bridge_modules.append({
                        "bridge_name": b_data["title"],
                        "target_prerequisite": b_name,
                        "key_topics": b_data["key_topics"],
                        "estimated_hours": b_data["est_hours"],
                        "remedies_course": active_sub.get("subject_name", active_code)
                    })

        if course_vulnerabilities:
            vulnerable_courses.append({
                "subject_code": active_code,
                "subject_name": active_sub.get("subject_name", active_code),
                "pvi_score": max_pvi,
                "severity": "HIGH" if max_pvi >= 40.0 else "MODERATE",
                "severity_color": "red" if max_pvi >= 40.0 else "amber",
                "prerequisite_deficits": course_vulnerabilities
            })

    return {
        "vulnerable_active_courses": vulnerable_courses,
        "vulnerable_count": len(vulnerable_courses),
        "has_vulnerabilities": len(vulnerable_courses) > 0,
        "recommended_bridge_modules": recommended_bridge_modules,
        "graph_health_status": "VULNERABILITIES_DETECTED" if vulnerable_courses else "PREREQUISITES_ROBUST"
    }
