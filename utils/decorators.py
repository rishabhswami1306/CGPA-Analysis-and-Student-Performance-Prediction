from functools import wraps
from flask import request, jsonify, redirect, url_for, flash
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from utils.db import get_db


def role_required(allowed_roles):
    """
    Decorator to restrict route access to specific roles.
    Works with both API and web view endpoints.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request(optional=False)
            except Exception:
                # If HTML request, redirect to login
                if request.headers.get("Accept", "").find("text/html") != -1 or not request.is_json:
                    flash("Please log in to continue.", "warning")
                    return redirect(url_for("auth.login_view"))
                return jsonify({"error": "Authentication required. Missing or invalid token."}), 401

            claims = get_jwt()
            user_role = claims.get("role")

            if not user_role or user_role not in allowed_roles:
                if request.headers.get("Accept", "").find("text/html") != -1 or not request.is_json:
                    flash("Access denied: You do not have permission for this resource.", "danger")
                    return redirect(url_for("auth.login_view"))
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Access denied. Requires one of roles: {allowed_roles}"
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def student_ownership_required(fn):
    """
    Ensures that a student can only view/modify their own records.
    Admins and Faculty can bypass this check.
    Prevents Insecure Direct Object Reference (IDOR).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=False)
        except Exception:
            return jsonify({"error": "Authentication required."}), 401

        claims = get_jwt()
        user_role = claims.get("role")
        current_prn = get_jwt_identity()

        # Target PRN from kwargs, query params, or JSON body
        target_prn = kwargs.get("student_prn") or request.args.get("student_prn")
        if not target_prn and request.is_json:
            target_prn = request.get_json().get("student_prn")

        if user_role == "student":
            if target_prn and target_prn != current_prn:
                return jsonify({
                    "error": "Forbidden",
                    "message": "You are not authorized to view or edit another student's data."
                }), 403

        return fn(*args, **kwargs)
    return wrapper


def faculty_subject_authorized(fn):
    """
    Ensures faculty can only submit/edit marks for their assigned subjects.
    Admin role bypasses this restriction.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=False)
        except Exception:
            return jsonify({"error": "Authentication required."}), 401

        claims = get_jwt()
        user_role = claims.get("role")
        current_prn = get_jwt_identity()

        if user_role == "admin":
            return fn(*args, **kwargs)

        if user_role != "faculty":
            return jsonify({"error": "Forbidden. Faculty access only."}), 403

        # Retrieve target subject_code
        subject_code = kwargs.get("subject_code") or request.args.get("subject_code")
        if not subject_code and request.is_json:
            subject_code = request.get_json().get("subject_code")

        if subject_code:
            db = get_db()
            faculty = db.users.find_one({"prn_roll": current_prn})
            assigned = (faculty.get("assigned_subjects") if faculty else []) or []
            if subject_code not in assigned:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Faculty {current_prn} is not authorized to grade subject {subject_code}."
                }), 403

        return fn(*args, **kwargs)
    return wrapper
