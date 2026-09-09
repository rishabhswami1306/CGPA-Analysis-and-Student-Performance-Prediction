import pytest
from utils.resume_analyzer import analyze_resume_text


def test_analyze_resume_text_success():
    sample_resume = """
    Jane Doe - Full Stack Software Developer
    Email: jane.doe@example.com | GitHub: github.com/janedoe | LinkedIn: linkedin.com/in/janedoe
    
    Technical Skills:
    Languages: Python, JavaScript, TypeScript, HTML, CSS, SQL
    Frameworks & Libraries: React, Node.js, Express, Flask, Tailwind CSS
    Databases: PostgreSQL, MongoDB, Redis
    Developer Tools: Git, GitHub, Docker, REST APIs, Postman
    
    Experience & Projects:
    Developed responsive web applications using React and Node.js.
    Designed RESTful microservices with Docker containerization.
    Practiced Data Structures and Algorithms on LeetCode.
    """

    report = analyze_resume_text(sample_resume, target_track="full_stack")
    assert report["ats_score"] > 60.0
    assert "Python" in report["matched_skills"]
    assert "React" in report["matched_skills"]
    assert "Docker & Containers" in report["matched_skills"]
    assert report["readability"]["has_contact_info"] is True
    assert report["readability"]["has_github_or_linkedin"] is True


def test_analyze_resume_text_empty():
    report = analyze_resume_text("", target_track="data_science_ml")
    assert "error" in report
    assert report["ats_score"] == 0.0
