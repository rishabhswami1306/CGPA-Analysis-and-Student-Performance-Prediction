import os
import hmac
import hashlib
from datetime import datetime, timezone
from flask import current_app

from utils.db import get_db
from utils.grade_calculator import compute_cumulative_cgpa


def get_signing_key(secret_key: str = None) -> bytes:
    """Returns the cryptographic signing key from app config or environment."""
    if secret_key:
        return secret_key.encode("utf-8")
    try:
        if current_app and current_app.config.get("SECRET_KEY"):
            return current_app.config["SECRET_KEY"].encode("utf-8")
    except RuntimeError:
        pass
    fallback = os.getenv("SECRET_KEY", "default-dev-secret-key-123")
    return fallback.encode("utf-8")


def generate_transcript_signature(
    prn_roll: str,
    cgpa: float,
    total_credits: int,
    total_backlogs: int,
    issue_date: str = None,
    secret_key: str = None
) -> str:
    """
    Generates a secure HMAC-SHA256 signature for academic transcript verification.
    """
    if issue_date is None:
        issue_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    canonical_payload = (
        f"PRN:{prn_roll.strip().upper()}|"
        f"CGPA:{float(cgpa):.2f}|"
        f"CR:{int(total_credits)}|"
        f"BL:{int(total_backlogs)}|"
        f"DATE:{issue_date}"
    )
    key = get_signing_key(secret_key)
    sig = hmac.new(key, canonical_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


def verify_transcript_signature(
    prn_roll: str,
    cgpa: float,
    total_credits: int,
    total_backlogs: int,
    issue_date: str,
    signature: str,
    secret_key: str = None
) -> bool:
    """
    Verifies that the provided HMAC-SHA256 signature matches the transcript data.
    """
    if not signature or not prn_roll:
        return False
    expected_sig = generate_transcript_signature(
        prn_roll=prn_roll,
        cgpa=cgpa,
        total_credits=total_credits,
        total_backlogs=total_backlogs,
        issue_date=issue_date,
        secret_key=secret_key
    )
    return hmac.compare_digest(expected_sig.lower(), signature.strip().lower())


def verify_transcript_against_db(
    prn_roll: str,
    signature: str,
    issue_date: str = None,
    sem: int = None
) -> dict:
    """
    Comprehensive verification against live MongoDB database records.
    Returns validation status, student details, and verification metadata.
    """
    db = get_db()
    user = db.users.find_one({"prn_roll": prn_roll})
    if not user:
        return {
            "is_valid": False,
            "status": "NOT_FOUND",
            "message": f"Student with PRN '{prn_roll}' does not exist in institute registry.",
            "student": None
        }

    records = list(db.academic_records.find({"student_prn": prn_roll}).sort("semester", 1))
    if sem:
        records_to_check = [r for r in records if r.get("semester") == int(sem)]
    else:
        records_to_check = records

    cgpa, total_backlogs, total_credits = compute_cumulative_cgpa(records_to_check)

    # Check validity against signature
    is_valid = False
    dates_to_try = [issue_date] if issue_date else []
    # Also fallback to today and recent dates if issue_date wasn't passed in query
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today_str not in dates_to_try:
        dates_to_try.append(today_str)

    for d in dates_to_try:
        if d and verify_transcript_signature(prn_roll, cgpa, total_credits, total_backlogs, d, signature):
            is_valid = True
            issue_date = d
            break

    # If signature still doesn't match, test without date lock if needed or mark INVALID
    if not is_valid:
        return {
            "is_valid": False,
            "status": "TAMPERED_OR_INVALID",
            "message": "Cryptographic signature mismatch. Document content may have been altered.",
            "student": {
                "name": user.get("name"),
                "prn_roll": user.get("prn_roll"),
                "branch": user.get("branch")
            },
            "verified_cgpa": cgpa,
            "total_credits": total_credits,
            "total_backlogs": total_backlogs
        }

    return {
        "is_valid": True,
        "status": "VERIFIED_AUTHENTIC",
        "message": "Official academic record successfully verified against institute ledger.",
        "student": {
            "name": user.get("name"),
            "prn_roll": user.get("prn_roll"),
            "branch": user.get("branch"),
            "admission_year": user.get("admission_year")
        },
        "verified_cgpa": round(cgpa, 2),
        "total_credits": total_credits,
        "total_backlogs": total_backlogs,
        "completed_semesters": len(records),
        "issue_date": issue_date,
        "signature": signature
    }
