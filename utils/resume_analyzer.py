import io
import re
import logging
from typing import Dict, List, Tuple
import pypdf

logger = logging.getLogger(__name__)

TRACK_TAXONOMY = {
    "full_stack": {
        "title": "Full Stack Software Engineering",
        "description": "Modern web platforms, distributed backends, RESTful APIs, and frontend architectures.",
        "skills": [
            {"name": "Python", "patterns": [r"\bpython\b", r"\bdjango\b", r"\bflask\b", r"\bfastapi\b"]},
            {"name": "JavaScript", "patterns": [r"\bjavascript\b", r"\bjs\b", r"\bes6\b"]},
            {"name": "TypeScript", "patterns": [r"\btypescript\b", r"\bts\b"]},
            {"name": "React", "patterns": [r"\breact\b", r"\breactjs\b", r"\bnext\.?js\b"]},
            {"name": "Node.js", "patterns": [r"\bnode(?:\.js)?\b", r"\bexpress(?:\.js)?\b"]},
            {"name": "HTML & CSS", "patterns": [r"\bhtml5?\b", r"\bcss3?\b", r"\btailwind\b", r"\bbootstrap\b"]},
            {"name": "SQL & Relational DB", "patterns": [r"\bsql\b", r"\bpostgresql\b", r"\bmysql\b", r"\bsqlite\b"]},
            {"name": "NoSQL / MongoDB", "patterns": [r"\bmongodb\b", r"\bnosql\b", r"\bredis\b"]},
            {"name": "Git & Version Control", "patterns": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"]},
            {"name": "REST APIs", "patterns": [r"\brest(?:ful)?\b", r"\bapi[s]?\b", r"\bgraphql\b", r"\bpostman\b"]},
            {"name": "Data Structures & Algorithms", "patterns": [r"\bdata structures\b", r"\balgorithms\b", r"\bdsa\b", r"\bleetcode\b"]},
            {"name": "Docker & Containers", "patterns": [r"\bdocker\b", r"\bcontainers?\b", r"\bk8s\b", r"\bkubernetes\b"]},
            {"name": "Cloud Deployment", "patterns": [r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bcloud\b", r"\bci/cd\b"]}
        ]
    },
    "data_science_ml": {
        "title": "Data Science & Machine Learning",
        "description": "Predictive modeling, deep learning architectures, feature engineering, and analytics.",
        "skills": [
            {"name": "Python", "patterns": [r"\bpython\b"]},
            {"name": "Pandas & NumPy", "patterns": [r"\bpandas\b", r"\bnumpy\b"]},
            {"name": "Scikit-Learn", "patterns": [r"\bscikit-learn\b", r"\bsklearn\b"]},
            {"name": "Machine Learning Algorithms", "patterns": [r"\bmachine learning\b", r"\bml\b", r"\bregression\b", r"\bclassification\b", r"\brandom forest\b", r"\bxgboost\b"]},
            {"name": "Deep Learning / Neural Nets", "patterns": [r"\bdeep learning\b", r"\btensorflow\b", r"\bpytorch\b", r"\bkeras\b", r"\bcnn\b", r"\brnn\b"]},
            {"name": "Natural Language Processing (NLP)", "patterns": [r"\bnlp\b", r"\bnatural language processing\b", r"\bbert\b", r"\bllm\b", r"\btransformers\b"]},
            {"name": "SQL & Data Extraction", "patterns": [r"\bsql\b", r"\bdatabase\b", r"\bquery\b"]},
            {"name": "Data Visualization", "patterns": [r"\bmatplotlib\b", r"\bseaborn\b", r"\bplotly\b", r"\btableau\b", r"\bpower\s?bi\b"]},
            {"name": "Statistical Analysis", "patterns": [r"\bstatistics\b", r"\bhypothesis testing\b", r"\bprobability\b"]},
            {"name": "Git & Reproducibility", "patterns": [r"\bgit\b", r"\bgithub\b", r"\bjupyter\b"]},
            {"name": "Feature Engineering", "patterns": [r"\bfeature engineering\b", r"\bpreprocessing\b", r"\bdata cleaning\b", r"\bshap\b"]},
            {"name": "Big Data / Cloud Analytics", "patterns": [r"\bspark\b", r"\bpyspark\b", r"\bbigquery\b", r"\bhadoop\b", r"\baws\b"]}
        ]
    },
    "cloud_devops": {
        "title": "Cloud Computing & DevOps",
        "description": "Infrastructure as Code, CI/CD pipelines, container orchestration, and reliability.",
        "skills": [
            {"name": "Linux & Bash", "patterns": [r"\blinux\b", r"\bbash\b", r"\bshell script(?:ing)?\b", r"\bubuntu\b"]},
            {"name": "Docker & Containerization", "patterns": [r"\bdocker\b", r"\bcontainer(?:s)?\b", r"\bdocker-compose\b"]},
            {"name": "Kubernetes", "patterns": [r"\bkubernetes\b", r"\bk8s\b", r"\bhelm\b"]},
            {"name": "AWS / Cloud Infrastructure", "patterns": [r"\baws\b", r"\bec2\b", r"\bs3\b", r"\blambda\b", r"\bcloud\b"]},
            {"name": "CI/CD Automation", "patterns": [r"\bci/cd\b", r"\bjenkins\b", r"\bgithub actions\b", r"\bgitlab ci\b"]},
            {"name": "Terraform / IaC", "patterns": [r"\bterraform\b", r"\bansible\b", r"\biac\b", r"\binfrastructure as code\b"]},
            {"name": "Git & Branching", "patterns": [r"\bgit\b", r"\bgithub\b", r"\bversion control\b"]},
            {"name": "Networking & Protocols", "patterns": [r"\btcp/ip\b", r"\bdns\b", r"\bhttp[s]?\b", r"\bssh\b", r"\bnginx\b", r"\bvpc\b"]},
            {"name": "Monitoring & Observability", "patterns": [r"\bprometheus\b", r"\bgrafana\b", r"\belk\b", r"\blogging\b"]},
            {"name": "Python / Scripting", "patterns": [r"\bpython\b", r"\bgolang\b", r"\bgo\b"]}
        ]
    },
    "core_cs": {
        "title": "Core Systems & Software Engineering",
        "description": "Low-level systems programming, operating system internals, computer architecture, and algorithms.",
        "skills": [
            {"name": "C / C++", "patterns": [r"\bc\+\+\b", r"\bcpp\b", r"\bc programming\b", r"\bpointers\b"]},
            {"name": "Data Structures & Algorithms", "patterns": [r"\bdsa\b", r"\bdata structures\b", r"\balgorithms\b", r"\btree[s]?\b", r"\bgraph[s]?\b"]},
            {"name": "Operating Systems", "patterns": [r"\boperating systems?\b", r"\bthreads?\b", r"\bconcurrency\b", r"\bmemory management\b", r"\bmutex\b"]},
            {"name": "Computer Networks", "patterns": [r"\bcomputer networks?\b", r"\bsocket programming\b", r"\btcp\b", r"\budp\b", r"\bosi model\b"]},
            {"name": "Database Management Systems (DBMS)", "patterns": [r"\bdbms\b", r"\bsql\b", r"\bacid\b", r"\bindexing\b", r"\btransactions\b"]},
            {"name": "Object-Oriented Programming (OOP)", "patterns": [r"\boop\b", r"\bpolymorphism\b", r"\binheritance\b", r"\bdesign patterns\b"]},
            {"name": "Linux / System Programming", "patterns": [r"\blinux\b", r"\bposix\b", r"\bsystem calls?\b", r"\bgdb\b"]},
            {"name": "System Design", "patterns": [r"\bsystem design\b", r"\bscalability\b", r"\bcaching\b", r"\bload balanc(?:er|ing)\b"]}
        ]
    }
}

ACADEMIC_COURSE_MAPPINGS = {
    "Operating Systems": {"code": "CS401", "name": "Operating Systems", "tip": "Review process scheduling, deadlocks, and POSIX multithreading from CS401 labs."},
    "Computer Networks": {"code": "CS403", "name": "Computer Networks", "tip": "Revise TCP 3-way handshake, OSI layers, and socket programming experiments from CS403."},
    "Database Management Systems (DBMS)": {"code": "CS304", "name": "Database Management Systems", "tip": "Emphasize SQL queries, ACID transactions, and normalization from CS304."},
    "SQL & Relational DB": {"code": "CS304", "name": "Database Management Systems", "tip": "Practice complex JOINs, indexing strategies, and aggregation in MySQL/PostgreSQL."},
    "Data Structures & Algorithms": {"code": "CS301 / CS402", "name": "DSA & Design of Algorithms", "tip": "Review dynamic programming, tree traversals, and graph algorithms on LeetCode."},
    "Machine Learning Algorithms": {"code": "DS501", "name": "Machine Learning Fundamentals", "tip": "Solidify supervised vs unsupervised loss functions and model evaluation metrics."},
    "Cloud Deployment": {"code": "CS503", "name": "Cloud Computing & DevOps", "tip": "Deploy a containerized project to AWS or Render to validate practical cloud skills."},
    "Docker & Containerization": {"code": "CS503", "name": "Cloud Computing & DevOps", "tip": "Add a Dockerfile and multi-container Docker Compose workflow to your project repositories."},
    "C / C++": {"code": "FE204", "name": "Object-Oriented Programming (C++)", "tip": "Implement custom memory allocators or standard data structures in modern C++17."}
}


def extract_text_from_pdf(file_stream) -> str:
    """Extracts raw plain text from an uploaded PDF stream."""
    try:
        reader = pypdf.PdfReader(file_stream)
        text_pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
        return "\n".join(text_pages).strip()
    except Exception as e:
        logger.warning(f"Error parsing PDF with pypdf: {e}")
        return ""


def analyze_resume_text(resume_text: str, target_track: str = "full_stack") -> dict:
    """
    Parses resume text, benchmarks against target domain skill requirements,
    and produces an ATS compatibility report with curricular action items.
    """
    if not resume_text:
        return {
            "error": "Resume could not be read or is empty. Please ensure it is a text-based PDF.",
            "ats_score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "recommendations": []
        }

    track_key = target_track if target_track in TRACK_TAXONOMY else "full_stack"
    track_info = TRACK_TAXONOMY[track_key]
    track_skills = track_info["skills"]

    cleaned_text = resume_text.lower()
    # Replace non-alphanumeric except + and # with spaces
    cleaned_text = re.sub(r"[^\w\+\#\.\s]", " ", cleaned_text)

    matched_skills = []
    missing_skills = []

    for skill in track_skills:
        skill_name = skill["name"]
        patterns = skill["patterns"]
        found = False
        for pat in patterns:
            if re.search(pat, cleaned_text, re.IGNORECASE):
                found = True
                break
        if found:
            matched_skills.append(skill_name)
        else:
            missing_skills.append(skill_name)

    total_expected = len(track_skills)
    match_count = len(matched_skills)
    ats_score = round((match_count / float(total_expected)) * 100.0, 1) if total_expected > 0 else 0.0

    # Categorize score rating
    if ats_score >= 80.0:
        rating_label = "EXCELLENT — Tier 1 ATS Ready"
        rating_color = "emerald"
        verdict = "Your resume strongly matches the industry skill profile for this role. Shortlisting probability is high."
    elif ats_score >= 60.0:
        rating_label = "COMPETITIVE — Strong Foundation"
        rating_color = "blue"
        verdict = "You have a solid core skillset. Incorporating the few missing technical competencies will maximize Tier-1 shortlisting."
    elif ats_score >= 40.0:
        rating_label = "DEVELOPING — Moderate Match"
        rating_color = "amber"
        verdict = "Foundational skills are present, but key track-specific technologies are missing from your resume keywords."
    else:
        rating_label = "NEEDS ENHANCEMENT — Low Keyword Match"
        rating_color = "rose"
        verdict = "Significant skill gaps detected. Ensure your project experience and technical proficiencies are clearly listed."

    # Build actionable recommendations linking missing skills with college coursework
    recommendations = []
    for m in missing_skills:
        mapping = ACADEMIC_COURSE_MAPPINGS.get(m)
        if mapping:
            recommendations.append({
                "skill": m,
                "course_code": mapping["code"],
                "course_name": mapping["name"],
                "action": mapping["tip"]
            })
        else:
            recommendations.append({
                "skill": m,
                "course_code": "Industry Elective",
                "course_name": f"Practical {m} Implementation",
                "action": f"Build a demonstrated GitHub repository featuring {m} to substantiate this keyword on your resume."
            })

    # Word count and ATS readability stats
    words = resume_text.split()
    word_count = len(words)
    ats_readability = {
        "word_count": word_count,
        "length_status": "OPTIMAL" if 350 <= word_count <= 800 else ("TOO_SHORT" if word_count < 350 else "VERBOSE"),
        "has_contact_info": bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", resume_text)),
        "has_github_or_linkedin": bool(re.search(r"(?:github\.com|linkedin\.com)", cleaned_text))
    }

    return {
        "target_track": track_key,
        "track_title": track_info["title"],
        "track_description": track_info["description"],
        "ats_score": ats_score,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "verdict": verdict,
        "matched_count": match_count,
        "total_skills": total_expected,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "recommendations": recommendations,
        "readability": ats_readability
    }
