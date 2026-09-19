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

    # Partition into audited completed records (Sem 1 to 4) and active ongoing record (Sem 5)
    completed_records = [r for r in records if r.get("is_completed", True) and r.get("sgpa") is not None and r.get("semester", 0) <= 4]
    ongoing_record = next((r for r in records if r.get("semester") == 5), None)

    # Calculate Cumulative CGPA based strictly on completed semesters (Sem 1–4)
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(completed_records)

    # Calculate Department Percentile and Anonymized Rank Movement across completed semesters
    branch = user.get("branch", "CSE-DS")
    all_branch_students = list(db.users.find({"role": "student", "branch": branch}))
    peer_prns = [p.get("prn_roll") for p in all_branch_students]
    if student_prn not in peer_prns:
        peer_prns.append(student_prn)

    # Fetch completed academic records for peers in 1 batch query
    all_peer_records = list(db.academic_records.find({
        "student_prn": {"$in": peer_prns},
        "semester": {"$lte": 4}
    }))
    records_by_student = {}
    for r in all_peer_records:
        records_by_student.setdefault(r["student_prn"], []).append(r)

    # Calculate Current CGPA for all peers across completed semesters
    peer_cgpas = []
    for p_prn in peer_prns:
        p_recs = records_by_student.get(p_prn, [])
        p_cgpa, _, _ = compute_cumulative_cgpa(p_recs)
        peer_cgpas.append({"prn": p_prn, "cgpa": p_cgpa})

    # Sort descending by CGPA
    peer_cgpas.sort(key=lambda x: x["cgpa"], reverse=True)
    total_peers = len(peer_cgpas)
    current_rank = next((idx + 1 for idx, p in enumerate(peer_cgpas) if p["prn"] == student_prn), total_peers)
    percentile = round(((total_peers - current_rank + 1) / total_peers) * 100.0, 1) if total_peers > 0 else 100.0

    # Calculate true rank trajectory across completed semesters 1 to 4
    rank_history = []
    recorded_semesters = sorted(list({r.get("semester", 1) for r in completed_records})) if completed_records else [1]
    for s in recorded_semesters:
        s_peers = []
        for p_prn in peer_prns:
            p_s_recs = [r for r in records_by_student.get(p_prn, []) if r.get("semester", 1) <= s]
            p_s_cgpa, _, _ = compute_cumulative_cgpa(p_s_recs)
            s_peers.append({"prn": p_prn, "cgpa": p_s_cgpa})
        s_peers.sort(key=lambda x: x["cgpa"], reverse=True)
        s_rank = next((idx + 1 for idx, p in enumerate(s_peers) if p["prn"] == student_prn), len(s_peers))
        s_percentile = round(((len(s_peers) - s_rank + 1) / len(s_peers)) * 100.0, 1) if len(s_peers) > 0 else 100.0
        my_s_recs = [r for r in completed_records if r.get("semester", 1) <= s]
        my_s_cgpa, _, _ = compute_cumulative_cgpa(my_s_recs)
        rank_history.append({
            "semester": s,
            "rank": s_rank,
            "total": len(s_peers),
            "percentile": s_percentile,
            "cgpa": my_s_cgpa
        })

    # Fetch latest predictions and explainability (Predicts ongoing Semester 5)
    predictions = predict_student_analytics(student_prn)

    # Prepare SGPA trend data for Chart.js across completed semesters 1 to 4
    sgpa_trend = [{"semester": r.get("semester"), "sgpa": r.get("sgpa")} for r in completed_records]

    # Prepare Subject-wise Radar Chart & Competency Matrix for active Semester 5 subjects
    radar_subjects = []
    eval_sem = ongoing_record if ongoing_record else (completed_records[-1] if completed_records else None)
    if eval_sem:
        active_sem_num = eval_sem.get("semester", 5)
        # Compute class averages for this semester's subject scores
        class_sem_records = list(db.academic_records.find({"semester": active_sem_num}))
        class_sub_scores = {}
        for cr in class_sem_records:
            for sub_item in cr.get("subjects", []):
                code = sub_item.get("subject_code")
                score = float(sub_item.get("total_marks", 0.0) or (sub_item.get("tt1_score", 0.0) * 5))
                class_sub_scores.setdefault(code, []).append(score)

        class_averages = {code: round(float(np.mean(scores)), 1) for code, scores in class_sub_scores.items()}

        for sub in eval_sem.get("subjects", []):
            code = sub.get("subject_code")
            tt1 = float(sub.get("tt1_score", 0.0))
            tt2 = float(sub.get("tt2_score", 0.0))
            # Internal continuous assessment score out of 40
            internal = float(sub.get("internal_score", 0.0))
            if internal == 0.0:
                tt_c = (tt1 + tt2) / 4.0 if (tt1 > 20 or tt2 > 20) else (tt1 + tt2) / 2.0
                internal = min(40.0, round(tt_c + float(sub.get("aptitude_score", 0.0)) + float(sub.get("skat_score", 0.0)) + float(sub.get("teacher_assessment_score", 0.0)) + float(sub.get("mock_interview_score", 0.0)) + float(sub.get("presentation_score", 0.0)), 2))

            if sub.get("total_marks", 0.0) > 0 and sub.get("ese_score", 0.0) > 0:
                score_pct = min(100.0, max(0.0, round(float(sub.get("total_marks")), 1)))
            else:
                score_pct = round((internal / 40.0) * 100.0, 1) if internal > 0 else 75.0
            
            class_avg = class_averages.get(code, 70.0)
            radar_subjects.append({
                "subject_code": code,
                "subject_name": sub.get("subject_name"),
                "score_pct": score_pct,
                "class_avg": class_avg,
                "grade_letter": sub.get("grade_letter", "Pending"),
                "grade_point": sub.get("grade_point"),
                "credits": sub.get("credits", 4),
                "tt1_score": tt1,
                "tt2_score": tt2,
                "tt_converted": sub.get("tt_converted", round((tt1 + tt2) / 4.0, 2)),
                "aptitude_score": sub.get("aptitude_score", 0.0),
                "skat_score": sub.get("skat_score", 0.0),
                "teacher_assessment_score": sub.get("teacher_assessment_score", 0.0),
                "mock_interview_score": sub.get("mock_interview_score", 0.0),
                "presentation_score": sub.get("presentation_score", 0.0),
                "internal_score": internal,
                "ese_score": sub.get("ese_score", 0.0)
            })

    # Real attendance from attendance_records collection
    from utils.attendance_engine import compute_attendance_predictions
    att_record = db.attendance_records.find_one({"student_prn": student_prn})
    attendance_forecast = None
    if att_record:
        attendance_forecast = compute_attendance_predictions(student_prn, att_record)
        latest_att = att_record.get("percentage", 80.0)
    else:
        latest_att = completed_records[-1].get("attendance_percentage", 80.0) if completed_records else 80.0

    shortfall = predictions.get("shortfall_analysis", {})

    return render_template(
        "student/student_dashboard.html",
        user=user,
        records=completed_records,
        ongoing_record=ongoing_record,
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
    completed_records = [r for r in records if r.get("is_completed", True) and r.get("sgpa") is not None and r.get("semester", 0) <= 4]
    ongoing_record = next((r for r in records if r.get("semester") == 5), None)

    current_cgpa, _, total_credits = compute_cumulative_cgpa(completed_records)

    # Current ongoing Semester 5 subjects
    active_subjects = []
    if ongoing_record:
        for s in ongoing_record.get("subjects", []):
            active_subjects.append({
                "subject_code": s.get("subject_code"),
                "subject_name": s.get("subject_name"),
                "credits": s.get("credits", 4),
                "tt1_score": float(s.get("tt1_score", 0.0)),
                "tt2_score": float(s.get("tt2_score", 0.0)),
                "aptitude_score": float(s.get("aptitude_score", 0.0)),
                "skat_score": float(s.get("skat_score", 0.0)),
                "teacher_assessment_score": float(s.get("teacher_assessment_score", 0.0)),
                "mock_interview_score": float(s.get("mock_interview_score", 0.0)),
                "presentation_score": float(s.get("presentation_score", 0.0)),
                "internal_score": float(s.get("internal_score", 0.0)),
                "max_ese": 60.0
            })
    elif records:
        latest_rec = records[-1]
        for s in latest_rec.get("subjects", []):
            active_subjects.append({
                "subject_code": s.get("subject_code"),
                "subject_name": s.get("subject_name"),
                "credits": s.get("credits", 4),
                "tt1_score": float(s.get("tt1_score", 0.0)),
                "tt2_score": float(s.get("tt2_score", 0.0)),
                "aptitude_score": float(s.get("aptitude_score", 0.0)),
                "skat_score": float(s.get("skat_score", 0.0)),
                "teacher_assessment_score": float(s.get("teacher_assessment_score", 0.0)),
                "mock_interview_score": float(s.get("mock_interview_score", 0.0)),
                "presentation_score": float(s.get("presentation_score", 0.0)),
                "internal_score": float(s.get("internal_score", 0.0)),
                "max_ese": 60.0
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
    completed_records = [r for r in records if r.get("is_completed", True) and r.get("sgpa") is not None and r.get("semester", 0) <= 4]
    sem_filter = request.args.get("semester")
    sem_filter = int(sem_filter) if sem_filter else None

    base_url = request.host_url.rstrip("/")
    pdf_bytes = generate_student_transcript_pdf(user, completed_records, current_sem=sem_filter, base_url=base_url)

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
    completed_records = [r for r in records if r.get("is_completed", True) and r.get("sgpa") is not None and r.get("semester", 0) <= 4]
    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(completed_records)

    # Fetch live attendance and placement readiness score
    att_doc = db.attendance_records.find_one({"student_prn": student_prn})
    sem5_rec = next((r for r in records if r.get("semester") == 5), None)
    student_att = float(att_doc.get("percentage") if att_doc else (sem5_rec.get("attendance_percentage", 80.0) if sem5_rec else 80.0))

    try:
        from ml_engine.inference import predict_student_analytics
        pred = predict_student_analytics(student_prn)
        placement_score = float(pred.get("placement_readiness_score", 72.0))
    except Exception:
        placement_score = 72.0

    analysis = evaluate_company_eligibility(
        student_cgpa=cgpa,
        total_backlogs=total_backlogs,
        branch=user.get("branch", "CSE-DS"),
        completed_credits=total_credits,
        current_sem_credits=20,
        student_attendance=student_att,
        student_placement_score=placement_score,
        academic_gap_years=int(user.get("academic_gap_years", 0)),
        tenth_marks=float(user.get("tenth_marks", 82.0)),
        twelfth_marks=float(user.get("twelfth_marks", 80.0)),
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
    """Resume ATS match scoring, technical keyword extraction, and curricular remedial roadmap."""
    from utils.resume_analyzer import extract_text_from_file, analyze_resume_text, SAMPLE_RESUME_TEXT, TRACK_TAXONOMY

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
    selected_track = request.args.get("track", "full_stack")
    resume_input_text = ""
    job_description = ""

    # Check for 1-click sample resume request
    if request.args.get("sample") == "1" or request.form.get("load_sample") == "1":
        resume_input_text = SAMPLE_RESUME_TEXT
        selected_track = request.form.get("target_track") or selected_track
        report = analyze_resume_text(resume_input_text, target_track=selected_track)
        flash(f"Loaded verified sample resume! Overall ATS Score: {report.get('ats_score')}%", "success")

    elif request.method == "POST":
        selected_track = request.form.get("target_track", "full_stack")
        job_description = request.form.get("job_description", "").strip()
        paste_text = request.form.get("resume_text", "").strip()
        resume_file = request.files.get("resume_file")

        extracted_text = ""
        if paste_text:
            extracted_text = paste_text
            resume_input_text = paste_text
        elif resume_file and resume_file.filename:
            try:
                extracted_text = extract_text_from_file(resume_file, resume_file.filename)
                resume_input_text = extracted_text
            except Exception as e:
                flash(f"Error reading resume file: {str(e)}", "danger")

        if not extracted_text:
            flash("Please upload a PDF/text file or paste your resume text to run the ATS audit.", "warning")
        else:
            try:
                report = analyze_resume_text(extracted_text, target_track=selected_track, job_description=job_description)
                flash(f"ATS audit complete! Overall Match Score: {report.get('ats_score')}%", "success")
            except Exception as e:
                flash(f"Error processing resume: {str(e)}", "danger")

    if request.is_json:
        return jsonify(report or {}), 200

    return render_template(
        "student/resume_analyzer.html",
        user=user,
        report=report,
        selected_track=selected_track,
        resume_input_text=resume_input_text,
        job_description=job_description,
        tracks=TRACK_TAXONOMY,
        sample_resume=SAMPLE_RESUME_TEXT
    )

