import math
from flask import Blueprint, request, jsonify, render_template, send_file, make_response, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import io
import numpy as np

from utils.db import get_db
from utils.decorators import role_required, student_ownership_required
from utils.grade_calculator import compute_cumulative_cgpa, compute_attendance_shortfall
from utils.what_if_solver import solve_what_if_target
from utils.pdf_generator import generate_student_transcript_pdf
from ml_engine.inference import predict_student_analytics

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard", methods=["GET"])
@role_required(["student", "admin", "faculty"])
def dashboard_view():
    """Student academic performance dashboard with real-time analytics."""
    claims = get_jwt()
    current_prn = get_jwt_identity()

    # Target student PRN (passed via query parameter, or defaults to logged-in user)
    target_prn = request.args.get("student_prn")
    student_prn = target_prn if target_prn else current_prn

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        flash("Student profile not found.", "danger")
        return redirect(url_for("auth.login_view"))

    # Fetch academic records
    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))

    # Calculate Cumulative CGPA
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(records)

    # Calculate Department Percentile and Anonymized Rank Movement
    branch = user.get("branch", "CSE")
    all_branch_students = list(db.users.find({"role": "student", "branch": branch}))
    
    # Calculate CGPA for all peers in branch
    peer_cgpas = []
    for peer in all_branch_students:
        peer_prn = peer.get("prn_roll")
        p_recs = list(db.academic_records.find({"student_prn": peer_prn}))
        p_cgpa, _, _ = compute_cumulative_cgpa(p_recs)
        peer_cgpas.append({"prn": peer_prn, "cgpa": p_cgpa})

    # Sort descending
    peer_cgpas.sort(key=lambda x: x["cgpa"], reverse=True)
    total_peers = len(peer_cgpas)
    current_rank = next((idx + 1 for idx, p in enumerate(peer_cgpas) if p["prn"] == student_prn), total_peers)
    percentile = round(((total_peers - current_rank + 1) / total_peers) * 100.0, 1) if total_peers > 0 else 100.0

    # Calculate rank movement across semesters
    rank_history = []
    max_sems = max([len(records)] + [1])
    for s in range(1, max_sems + 1):
        # Calculate rank at sem s
        s_peers = []
        for peer in all_branch_students:
            peer_prn = peer.get("prn_roll")
            p_s_recs = list(db.academic_records.find({"student_prn": peer_prn, "semester": {"$lte": s}}))
            p_s_cgpa, _, _ = compute_cumulative_cgpa(p_s_recs)
            s_peers.append({"prn": peer_prn, "cgpa": p_s_cgpa})
        s_peers.sort(key=lambda x: x["cgpa"], reverse=True)
        s_rank = next((idx + 1 for idx, p in enumerate(s_peers) if p["prn"] == student_prn), len(s_peers))
        rank_history.append({"semester": s, "rank": s_rank, "total": len(s_peers)})

    # Fetch latest predictions and explainability
    predictions = predict_student_analytics(student_prn)

    # Prepare SGPA trend data for Chart.js
    sgpa_trend = [{"semester": r.get("semester"), "sgpa": r.get("sgpa")} for r in records]

    # Prepare Subject-wise Radar Chart Competency (Percentage Normalized)
    radar_subjects = []
    if records:
        latest_sem = records[-1]
        for sub in latest_sem.get("subjects", []):
            total_score = float(sub.get("total_marks", 0.0))
            # Normalize to percentage of 100
            pct_score = min(100.0, max(0.0, round(total_score, 1)))
            radar_subjects.append({
                "subject_code": sub.get("subject_code"),
                "subject_name": sub.get("subject_name"),
                "score_pct": pct_score,
                "grade_letter": sub.get("grade_letter", "P")
            })

    # Real attendance from attendance_records collection
    from utils.attendance_engine import compute_attendance_predictions
    att_record = db.attendance_records.find_one({"student_prn": student_prn})
    attendance_forecast = None
    if att_record:
        attendance_forecast = compute_attendance_predictions(student_prn, att_record)
        latest_att = att_record.get("percentage", 80.0)
    else:
        latest_att = records[-1].get("attendance_percentage", 80.0) if records else 80.0

    shortfall = predictions.get("shortfall_analysis", {})

    return render_template(
        "student/student_dashboard.html",
        user=user,
        records=records,
        cgpa=cgpa,
        total_backlogs=total_backlogs,
        total_credits=total_credits,
        rank=current_rank,
        total_peers=total_peers,
        percentile=percentile,
        rank_history=rank_history,
        predictions=predictions,
        sgpa_trend=sgpa_trend,
        radar_subjects=radar_subjects,
        latest_attendance=latest_att,
        shortfall=shortfall,
        att_record=att_record,
        attendance_forecast=attendance_forecast
    )


@student_bp.route("/what-if", methods=["GET", "POST"])
@role_required(["student", "admin", "faculty"])
def what_if_view():
    """Prescriptive What-If Goal Planner."""
    current_prn = get_jwt_identity()
    target_prn = request.args.get("student_prn") or current_prn
    db = get_db()
    user = db.users.find_one({"prn_roll": target_prn})
    records = list(db.academic_records.find({"student_prn": target_prn}).sort("semester", 1))

    current_cgpa, _, total_credits = compute_cumulative_cgpa(records)

    # Current subjects in progress (either latest sem or mock upcoming)
    active_subjects = []
    if records:
        latest_rec = records[-1]
        for s in latest_rec.get("subjects", []):
            active_subjects.append({
                "subject_code": s.get("subject_code"),
                "subject_name": s.get("subject_name"),
                "credits": s.get("credits", 4),
                "tt1_score": s.get("tt1_score", 15.0),
                "tt2_score": s.get("tt2_score", 15.0),
                "max_ese": 80.0
            })
    else:
        # Default mock subjects for sem 1 student
        active_subjects = [
            {"subject_code": "CS101", "subject_name": "Data Structures & Algorithms", "credits": 4, "tt1_score": 16.0, "tt2_score": 15.0, "max_ese": 80.0},
            {"subject_code": "CS102", "subject_name": "Database Management Systems", "credits": 4, "tt1_score": 14.0, "tt2_score": 16.0, "max_ese": 80.0},
            {"subject_code": "CS103", "subject_name": "Computer Networks", "credits": 3, "tt1_score": 15.0, "tt2_score": 14.0, "max_ese": 80.0},
            {"subject_code": "MA101", "subject_name": "Engineering Mathematics III", "credits": 4, "tt1_score": 13.0, "tt2_score": 14.0, "max_ese": 80.0},
            {"subject_code": "CS104", "subject_name": "Web Technologies & Cloud", "credits": 3, "tt1_score": 18.0, "tt2_score": 17.0, "max_ese": 80.0},
        ]

    target_cgpa = float(request.args.get("target_cgpa", 8.5))
    if request.method == "POST" and request.is_json:
        data = request.get_json()
        target_cgpa = float(data.get("target_cgpa", 8.5))
        if "subjects" in data and isinstance(data["subjects"], list):
            active_subjects = data["subjects"]

    analysis = solve_what_if_target(
        target_cgpa=target_cgpa,
        current_cgpa=current_cgpa,
        completed_credits=total_credits,
        current_sem_credits=sum(s["credits"] for s in active_subjects),
        subjects=active_subjects
    )

    if request.is_json:
        return jsonify(analysis), 200

    return render_template(
        "student/goal_planner.html",
        user=user,
        current_cgpa=current_cgpa,
        total_credits=total_credits,
        active_subjects=active_subjects,
        target_cgpa=target_cgpa,
        analysis=analysis
    )


@student_bp.route("/transcript/pdf", methods=["GET"])
@role_required(["student", "admin", "faculty"])
def download_transcript_pdf():
    """Generates and downloads formal PDF academic transcript."""
    current_prn = get_jwt_identity()
    claims = get_jwt()
    target_prn = request.args.get("student_prn")
    student_prn = target_prn if target_prn else current_prn

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        return jsonify({"error": "Student not found"}), 404

    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))
    sem_filter = request.args.get("semester")
    sem_filter = int(sem_filter) if sem_filter else None

    base_url = request.host_url.rstrip("/")
    pdf_bytes = generate_student_transcript_pdf(user, records, current_sem=sem_filter, base_url=base_url)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Transcript_{student_prn}.pdf"
    )


@student_bp.route("/placement-eligibility", methods=["GET", "POST"])
@role_required(["student", "admin", "faculty"])
def placement_eligibility_view():
    """Campus recruitment company eligibility matrix and dream company target simulator."""
    from utils.placement_eligibility import evaluate_company_eligibility

    current_prn = get_jwt_identity()
    claims = get_jwt()
    target_prn = request.args.get("student_prn")
    if target_prn and claims.get("role") in ["admin", "faculty"]:
        student_prn = target_prn
    else:
        student_prn = current_prn

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})
    if not user:
        flash("Student profile not found.", "danger")
        return redirect(url_for("auth.login_view"))

    records = list(db.academic_records.find({"student_prn": student_prn}).sort("semester", 1))
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(records)

    analysis = evaluate_company_eligibility(
        student_cgpa=cgpa,
        total_backlogs=total_backlogs,
        branch=user.get("branch", "CSE"),
        completed_credits=total_credits,
        current_sem_credits=20,
        db=db
    )

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify(analysis), 200

    return render_template(
        "student/placement_eligibility.html",
        user=user,
        analysis=analysis
    )


@student_bp.route("/resume-analyzer", methods=["GET", "POST"])
@role_required(["student", "admin", "faculty"])
def resume_analyzer_view():
    """PDF Resume ATS match scoring, technical keyword extraction, and curricular remedial roadmap."""
    from utils.resume_analyzer import extract_text_from_pdf, analyze_resume_text

    current_prn = get_jwt_identity()
    claims = get_jwt()
    target_prn = request.args.get("student_prn")
    if target_prn and claims.get("role") in ["admin", "faculty"]:
        student_prn = target_prn
    else:
        student_prn = current_prn

    db = get_db()
    user = db.users.find_one({"prn_roll": student_prn})

    report = None
    selected_track = "full_stack"

    if request.method == "POST":
        selected_track = request.form.get("target_track", "full_stack")
        resume_file = request.files.get("resume_file")

        if not resume_file or resume_file.filename == "":
            flash("Please upload a valid PDF resume file.", "warning")
        elif not resume_file.filename.lower().endswith(".pdf"):
            flash("Only .pdf file format is supported for resume ATS audit.", "danger")
        else:
            try:
                pdf_bytes = io.BytesIO(resume_file.read())
                extracted_text = extract_text_from_pdf(pdf_bytes)
                if not extracted_text:
                    flash("Unable to extract text from the PDF. Ensure it contains selectable text.", "danger")
                else:
                    report = analyze_resume_text(extracted_text, target_track=selected_track)
                    flash(f"ATS audit complete! Match score: {report.get('ats_score')}%", "success")
            except Exception as e:
                flash(f"Error processing resume: {str(e)}", "danger")

    return render_template(
        "student/resume_analyzer.html",
        user=user,
        report=report,
        selected_track=selected_track
    )

