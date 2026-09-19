import pytest
from utils.resume_analyzer import analyze_resume_text


def test_analyze_resume_text_success():
    sample_resume = """
    Jane Doe - Full Stack Software Developer
    Email: jane.doe@example.com | Phone: +91 9876543210 | GitHub: github.com/janedoe | LinkedIn: linkedin.com/in/janedoe
    
    Professional Summary:
    Results-driven Full Stack Software Developer with extensive experience designing and deploying high-availability web applications and cloud services.
    
    Education:
    Bachelor of Technology in Computer Engineering, RCPIT (CGPA: 8.85 / 10.0) — 2021 - 2025
    
    Technical Skills:
    Languages: Python, JavaScript, TypeScript, HTML5, CSS3, SQL
    Frameworks & Libraries: React, Node.js, Express, Flask, Tailwind CSS, Redux
    Databases & Caching: PostgreSQL, MongoDB, Redis
    DevOps & Tools: Git, GitHub, Docker, REST APIs, Postman, Linux
    
    Experience & Projects:
    - Architected and deployed full-stack web applications using React, Node.js, and MongoDB, supporting 15,000+ monthly active users with 99.9% uptime.
    - Engineered modular RESTful microservices containerized with Docker, reducing API response latency by 38%.
    - Optimized database query performance on PostgreSQL using indexing and connection pooling, scaling query throughput by 50%.
    - Solved 350+ Data Structures and Algorithms problems across LeetCode and HackerRank.
    """

    report = analyze_resume_text(sample_resume, target_track="full_stack")
    assert report["ats_score"] >= 65.0
    assert "Python" in report["matched_skills"]
    assert "React" in report["matched_skills"]
    assert "Docker & Containers" in report["matched_skills"]
    assert report["readability"]["has_contact_info"] is True
    assert report["readability"]["has_github_or_linkedin"] is True


def test_analyze_resume_text_empty():
    report = analyze_resume_text("", target_track="data_science_ml")
    assert "error" in report
    assert report["ats_score"] == 0.0


def test_analyze_resume_gen_ai_and_helping_hand():
    sample_ai_resume = """
    Alex Smith - AI & Machine Learning Engineer
    Email: alex.smith@example.com | GitHub: github.com/alexsmith | LinkedIn: linkedin.com/in/alexsmith | Phone: 9876543210
    
    Summary:
    Passionate Machine Learning Engineer specializing in Large Language Models, Retrieval-Augmented Generation (RAG), and vector embeddings.
    
    Education:
    Bachelor of Technology in Artificial Intelligence & Data Science, RCPIT (CGPA: 9.1/10) - 2021 to 2025
    
    Technical Skills:
    Languages & Frameworks: Python, LangChain, LlamaIndex, PyTorch, Hugging Face, FastAPI, Docker
    Vector Databases: Pinecone, ChromaDB, FAISS
    Concepts: Large Language Models (LLMs), RAG, Prompt Engineering, Semantic Search, Fine-Tuning
    
    Experience & Projects:
    - Architected an enterprise RAG knowledge engine utilizing LangChain and ChromaDB, reducing hallucinations by 45% across 25,000+ queries.
    - Worked on fine-tuning Llama-3 using LoRA across 10,000 custom domain prompts, boosting model accuracy by 28%.
    - Helped with building vector similarity retrieval pipelines in Pinecone handling 500+ requests/sec.
    - Integrated multi-agent evaluation workflows with Ragas achieving 92% faithfulness score.
    """

    report = analyze_resume_text(sample_ai_resume, target_track="gen_ai_engineer")
    assert report["ats_score"] >= 65.0
    assert "LangChain & LlamaIndex" in report["matched_skills"]
    assert "RAG (Retrieval-Augmented Generation)" in report["matched_skills"]
    assert "Vector Databases (Pinecone / Chroma / FAISS)" in report["matched_skills"]

    # Verify Weak Verb detection
    assert len(report["weak_verbs_detected"]) > 0
    weak_words = [wv["found"] for wv in report["weak_verbs_detected"]]
    assert "worked on" in weak_words or "helped" in weak_words or "helped with" in weak_words

    # Verify Helping Hand blueprints generated for missing competencies
    assert len(report["helping_hand"]) > 0
    first_plan = report["helping_hand"][0]
    assert "skill" in first_plan
    assert "bullet_templates" in first_plan
    assert len(first_plan["bullet_templates"]) >= 1
    assert "project" in first_plan
    assert "title" in first_plan["project"]
    assert "deliverables" in first_plan["project"]
    assert "certifications" in first_plan

