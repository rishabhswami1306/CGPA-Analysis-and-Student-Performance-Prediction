import pytest
from utils.transcript_verifier import (
    generate_transcript_signature,
    verify_transcript_signature,
    verify_transcript_against_db
)


def test_transcript_signature_generation_and_verification():
    prn = "2022CSE001"
    cgpa = 8.75
    credits = 80
    backlogs = 0
    date_str = "2026-09-04"

    sig = generate_transcript_signature(prn, cgpa, credits, backlogs, date_str, secret_key="test-key-123")
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex length

    # Verify matching signature returns True
    assert verify_transcript_signature(prn, cgpa, credits, backlogs, date_str, sig, secret_key="test-key-123") is True

    # Tamper detection: Changed CGPA
    assert verify_transcript_signature(prn, 9.99, credits, backlogs, date_str, sig, secret_key="test-key-123") is False

    # Tamper detection: Changed PRN
    assert verify_transcript_signature("FAKE_PRN", cgpa, credits, backlogs, date_str, sig, secret_key="test-key-123") is False

    # Tamper detection: Changed backlogs
    assert verify_transcript_signature(prn, cgpa, credits, 2, date_str, sig, secret_key="test-key-123") is False


def test_public_verify_transcript_route(client):
    # Retrieve student1 from seeded test db
    db_resp = client.get("/auth/verify-transcript?prn=NON_EXISTENT&sig=invalid123", headers={"Accept": "application/json"})
    assert db_resp.status_code == 400
    data = db_resp.get_json()
    assert data["is_valid"] is False
    assert data["status"] == "NOT_FOUND"
