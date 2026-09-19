import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies, jwt_required, get_jwt_identity, get_jwt
)
from flask_bcrypt import Bcrypt
from marshmallow import ValidationError

from utils.db import get_db
from utils.validators import (
    UserLoginSchema, PasswordResetRequestSchema,
    PasswordResetSchema, ChangePasswordSchema
)
from utils.audit_logger import log_audit_event

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
bcrypt = Bcrypt()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


@auth_bp.route("/login", methods=["GET", "POST"])
def login_view():
    """Login view supporting both web form submissions and JSON API calls."""
    if request.method == "GET":
        return render_template("auth/login.html")

    # Handle POST
    is_json = request.is_json
    payload = request.get_json() if is_json else request.form.to_dict()

    # Validate input
    # Allow identifier to be email OR PRN (numeric or alphanumeric)
    raw_identifier = (payload.get("email") or "").strip()
    raw_password = (payload.get("password") or "")

    if not raw_identifier or not raw_password:
        if is_json:
            return jsonify({"error": "Identifier and password are required."}), 400
        flash("Please enter your PRN/Email and password.", "danger")
        return render_template("auth/login.html"), 400

    password = raw_password
    db = get_db()

    # Try email lookup first, then PRN lookup
    identifier_lower = raw_identifier.lower()
    user = db.users.find_one({"email": identifier_lower})
    if not user:
        user = db.users.find_one({"prn_roll": raw_identifier})

    if not user:
        if is_json:
            return jsonify({"error": "Invalid email or password."}), 401
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html"), 401

    # Check brute-force account lockout
    locked_until = user.get("locked_until")
    if locked_until:
        # Handle string or datetime
        if isinstance(locked_until, str):
            try:
                locked_until = datetime.fromisoformat(locked_until)
            except Exception:
                locked_until = None

        if locked_until and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if locked_until and locked_until > datetime.now(timezone.utc):
            remaining_mins = max(1, int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60))
            msg = f"Account temporarily locked due to multiple failed login attempts. Try again in {remaining_mins} minute(s)."
            if is_json:
                return jsonify({"error": msg}), 429
            flash(msg, "danger")
            return render_template("auth/login.html"), 429

    # Verify password
    password_hash = user.get("password_hash", "")
    is_valid = False
    try:
        is_valid = bcrypt.check_password_hash(password_hash, password)
    except Exception:
        is_valid = False

    if not is_valid:
        # Increment failed attempts
        failed = user.get("failed_login_attempts", 0) + 1
        update_fields = {"failed_login_attempts": failed}
        if failed >= MAX_FAILED_ATTEMPTS:
            update_fields["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            update_fields["failed_login_attempts"] = 0
            log_audit_event(
                actor_prn=user.get("prn_roll") or user.get("email") or raw_identifier,
                actor_role=user.get("role", "student"),
                action="ACCOUNT_LOCKED",
                details=f"Locked for {LOCKOUT_DURATION_MINUTES}m after {MAX_FAILED_ATTEMPTS} failed attempts."
            )

        db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})
        if is_json:
            return jsonify({"error": "Invalid email or password."}), 401
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html"), 401

    # Reset failed attempts upon successful login
    db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_login_attempts": 0, "locked_until": None}})

    # Check if account is active
    if not user.get("is_active", True):
        if is_json:
            return jsonify({"error": "Account has been deactivated. Please contact Administrator."}), 403
        flash("Your account has been deactivated. Contact Admin.", "danger")
        return render_template("auth/login.html"), 403

    # Generate JWT Tokens
    user_prn = user.get("prn_roll")
    user_role = user.get("role")
    additional_claims = {
        "role": user_role,
        "name": user.get("name"),
        "email": user.get("email"),
        "branch": user.get("branch"),
        "must_change_password": user.get("must_change_password", False)
    }

    access_token = create_access_token(identity=user_prn, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=user_prn, additional_claims={"role": user_role})

    # Record login audit
    log_audit_event(
        actor_prn=user_prn,
        actor_role=user_role,
        action="USER_LOGIN",
        details="Successful login."
    )

    # API JSON Response
    if is_json:
        response = make_response(jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user": {
                "prn_roll": user_prn,
                "name": user.get("name"),
                "email": user.get("email"),
                "role": user_role,
                "branch": user.get("branch"),
                "must_change_password": user.get("must_change_password", False)
            }
        }))
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        return response, 200

    # HTML Web App Response with Cookies
    if user_role == "admin":
        dest_url = url_for("admin.dashboard_view")
    elif user_role == "faculty":
        dest_url = url_for("faculty.dashboard_view")
    else:
        dest_url = url_for("student.dashboard_view")

    if user.get("must_change_password", False):
        dest_url = url_for("auth.change_password_view")

    resp = make_response(redirect(dest_url))
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    flash(f"Welcome back, {user.get('name')}!", "success")
    return resp


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """Generates new access token using httpOnly refresh token cookie."""
    identity = get_jwt_identity()
    db = get_db()
    user = db.users.find_one({"prn_roll": identity})
    if not user:
        return jsonify({"error": "User not found"}), 404

    additional_claims = {
        "role": user.get("role"),
        "name": user.get("name"),
        "email": user.get("email"),
        "branch": user.get("branch"),
        "must_change_password": user.get("must_change_password", False)
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    resp = make_response(jsonify({"message": "Token refreshed", "access_token": access_token}))
    set_access_cookies(resp, access_token)
    return resp, 200


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout_view():
    """Clears JWT cookies and redirects to login."""
    resp = make_response(redirect(url_for("auth.login_view")))
    unset_jwt_cookies(resp)
    if request.is_json:
        resp = make_response(jsonify({"message": "Logged out successfully"}))
        unset_jwt_cookies(resp)
        return resp, 200
    flash("You have been securely logged out.", "info")
    return resp


@auth_bp.route("/change-password", methods=["GET", "POST"])
@jwt_required()
def change_password_view():
    """Allows user to change password, required on first login or after admin reset."""
    identity = get_jwt_identity()
    db = get_db()
    user = db.users.find_one({"prn_roll": identity})

    if request.method == "GET":
        return render_template("auth/change_password.html", user=user)

    is_json = request.is_json
    payload = request.get_json() if is_json else request.form.to_dict()

    schema = ChangePasswordSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        if is_json:
            return jsonify({"error": "Validation failed", "details": err.messages}), 400
        flash(f"Error: {list(err.messages.values())[0][0]}", "danger")
        return render_template("auth/change_password.html", user=user), 400

    # Verify old password
    if not bcrypt.check_password_hash(user.get("password_hash", ""), data["old_password"]):
        if is_json:
            return jsonify({"error": "Current password incorrect."}), 400
        flash("Current password incorrect.", "danger")
        return render_template("auth/change_password.html", user=user), 400

    # Hash new password
    new_hash = bcrypt.generate_password_hash(data["new_password"]).decode("utf-8")
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "must_change_password": False,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    log_audit_event(
        actor_prn=identity,
        actor_role=user.get("role"),
        action="CHANGE_PASSWORD",
        details="User successfully changed password."
    )

    if is_json:
        return jsonify({"message": "Password changed successfully"}), 200

    flash("Password updated successfully! Welcome.", "success")
    if user.get("role") == "admin":
        return redirect(url_for("admin.dashboard_view"))
    elif user.get("role") == "faculty":
        return redirect(url_for("faculty.dashboard_view"))
    else:
        return redirect(url_for("student.dashboard_view"))


@auth_bp.route("/reset-password-request", methods=["POST"])
def reset_password_request():
    """Generates password reset token."""
    payload = request.get_json() or request.form.to_dict()
    schema = PasswordResetRequestSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        return jsonify({"error": err.messages}), 400

    email = data["email"].strip().lower()
    db = get_db()
    user = db.users.find_one({"email": email})

    if not user:
        # Don't reveal if user exists
        return jsonify({"message": "If this email is registered, a reset token has been generated."}), 200

    reset_token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"reset_token": reset_token, "reset_token_expiry": expiry}}
    )

    log_audit_event(
        actor_prn=user.get("prn_roll"),
        actor_role="system",
        action="PASSWORD_RESET_REQUEST",
        target_student_prn=user.get("prn_roll")
    )

    # In production, send email; in development/demo return the token in debug payload
    return jsonify({
        "message": "Password reset token generated (valid for 30 mins).",
        "demo_reset_token": reset_token
    }), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Resets password using reset token."""
    payload = request.get_json() or request.form.to_dict()
    schema = PasswordResetSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        return jsonify({"error": err.messages}), 400

    token = data["token"]
    db = get_db()
    user = db.users.find_one({"reset_token": token})

    if not user:
        return jsonify({"error": "Invalid or expired reset token."}), 400

    expiry = user.get("reset_token_expiry")
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry)
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if not expiry or expiry < datetime.now(timezone.utc):
        return jsonify({"error": "Reset token has expired. Please request a new one."}), 400

    new_hash = bcrypt.generate_password_hash(data["new_password"]).decode("utf-8")
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "reset_token": None,
            "reset_token_expiry": None,
            "must_change_password": False,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    log_audit_event(
        actor_prn=user.get("prn_roll"),
        actor_role=user.get("role"),
        action="RESET_PASSWORD_COMPLETE",
        target_student_prn=user.get("prn_roll")
    )

    return jsonify({"message": "Password successfully reset. You may now log in."}), 200


@auth_bp.route("/verify-transcript", methods=["GET"])
def verify_transcript_view():
    """
    Public portal to cryptographically verify official academic transcripts.
    Accessible without authentication for external employers, universities, and students.
    """
    from utils.transcript_verifier import verify_transcript_against_db

    prn = request.args.get("prn") or request.args.get("student_prn", "")
    sig = request.args.get("sig") or request.args.get("signature", "")
    date = request.args.get("date") or request.args.get("issue_date")
    sem = request.args.get("sem")
    sem_val = int(sem) if sem and sem.isdigit() else None

    result = None
    if prn and sig:
        result = verify_transcript_against_db(
            prn_roll=prn.strip().upper(),
            signature=sig.strip(),
            issue_date=date,
            sem=sem_val
        )

    if request.is_json or request.headers.get("Accept") == "application/json":
        if result is None:
            return jsonify({"error": "Missing parameters 'prn' and 'sig'"}), 400
        return jsonify(result), 200 if result.get("is_valid") else 400

    return render_template("auth/verify_transcript.html", result=result)
