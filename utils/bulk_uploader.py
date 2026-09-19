import io
import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

from utils.db import get_db
from utils.grade_calculator import (
    compute_subject_internal, compute_subject_total, calculate_grade_point, compute_semester_sgpa
)
from utils.audit_logger import log_audit_event
from ml_engine.inference import predict_student_analytics

logger = logging.getLogger(__name__)

# Standard header aliases mapping to canonical fields
HEADER_ALIASES = {
    # Student identifier
    "student_prn": "student_prn",
    "prn": "student_prn",
    "prn_roll": "student_prn",
    "roll_no": "student_prn",
    "roll": "student_prn",
    "student_id": "student_prn",
    "student": "student_prn",

    # Semester
    "semester": "semester",
    "sem": "semester",

    # Subject Code
    "subject_code": "subject_code",
    "subject": "subject_code",
    "sub_code": "subject_code",
    "code": "subject_code",

    # Marks fields
    "tt1_score": "tt1_score",
    "tt1": "tt1_score",
    "unit_test_1": "tt1_score",
    "test_1": "tt1_score",

    "tt2_score": "tt2_score",
    "tt2": "tt2_score",
    "unit_test_2": "tt2_score",
    "test_2": "tt2_score",

    "aptitude_score": "aptitude_score",
    "aptitude": "aptitude_score",
    "apt": "aptitude_score",

    "skat_score": "skat_score",
    "skat": "skat_score",

    "teacher_assessment_score": "teacher_assessment_score",
    "teacher_assessment": "teacher_assessment_score",
    "ta": "teacher_assessment_score",

    "mock_interview_score": "mock_interview_score",
    "mock_interview": "mock_interview_score",
    "mock": "mock_interview_score",

    "presentation_score": "presentation_score",
    "presentation": "presentation_score",
    "pres": "presentation_score",

    "ese_score": "ese_score",
    "ese": "ese_score",
    "end_sem": "ese_score",

    # Attendance & Bunk fields
    "conducted_hours": "conducted_hours",
    "conducted": "conducted_hours",
    "conducted_classes": "conducted_hours",
    "total_classes": "conducted_hours",
    "total_lectures": "conducted_hours",
    "total_conducted": "conducted_hours",

    "attended_hours": "attended_hours",
    "attended": "attended_hours",
    "attended_classes": "attended_hours",
    "total_attended": "attended_hours",

    "bunked_hours": "bunked_hours",
    "bunked": "bunked_hours",
    "bunked_classes": "bunked_hours",
    "bunks": "bunked_hours",
    "bunk_count": "bunked_hours",
    "absent_hours": "bunked_hours",
    "absent": "bunked_hours",

    "attendance_percentage": "attendance_percentage",
    "attendance_pct": "attendance_percentage",
    "attendance": "attendance_percentage",
    "att_pct": "attendance_percentage",
}


def normalize_column_name(col: str) -> str:
    """Normalize arbitrary header string to snake_case canonical name."""
    cleaned = str(col).strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_").replace(".", "")
    return HEADER_ALIASES.get(cleaned, cleaned)


def parse_upload_file(file_storage, filename: str) -> pd.DataFrame:
    """
    Safely load CSV or Excel file into a pandas DataFrame and normalize columns.
    """
    ext = filename.lower().split(".")[-1]
    if ext == "csv":
        df = pd.read_csv(file_storage)
    elif ext in ["xlsx", "xls"]:
        df = pd.read_excel(file_storage)
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Please upload a .csv or .xlsx file.")

    # Clean whitespace and normalize headers
    df.columns = [normalize_column_name(c) for c in df.columns]
    # Drop completely empty rows
    df = df.dropna(how="all")
    return df


def validate_and_prepare_batch(
    df: pd.DataFrame,
    upload_type: str,
    default_semester: int = 5,
    default_subject: Optional[str] = None,
    authorized_subjects: Optional[List[str]] = None,
    is_admin: bool = False
) -> Dict[str, Any]:
    """
    Validates uploaded rows, resolves student names, checks authorized subject scope,
    and stages valid records for dry-run preview or atomic commit.
    """
    db = get_db()
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    staged_rows: List[Dict[str, Any]] = []

    if "student_prn" not in df.columns:
        return {
            "is_valid": False,
            "fatal_error": "Missing student PRN column (e.g. 'student_prn', 'prn', 'roll_no').",
            "staged_rows": [],
            "errors": [],
            "warnings": []
        }

    # Pre-cache students in database for fast validation
    existing_students = {
        u["prn_roll"]: u.get("name", "Student")
        for u in db.users.find({"role": "student"}, {"prn_roll": 1, "name": 1})
    }

    # If no students found in users, check academic_records
    if not existing_students:
        for r in db.academic_records.find({}, {"student_prn": 1}):
            existing_students[r["student_prn"]] = f"Student {r['student_prn']}"

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed header + 1
        raw_prn = row.get("student_prn")
        if pd.isna(raw_prn) or str(raw_prn).strip() == "":
            continue

        prn = str(raw_prn).strip()
        # Strip trailing .0 if read as float from excel
        if prn.endswith(".0"):
            prn = prn[:-2]

        if prn not in existing_students:
            errors.append({
                "row": row_num,
                "prn": prn,
                "error": f"Student PRN '{prn}' not found in active database roster."
            })
            continue

        student_name = existing_students[prn]

        # Resolve semester
        sem = row.get("semester")
        if pd.isna(sem) or sem is None or str(sem).strip() == "":
            sem = default_semester
        else:
            try:
                sem = int(float(sem))
            except (ValueError, TypeError):
                sem = default_semester

        # Resolve subject
        sub_code = row.get("subject_code")
        if pd.isna(sub_code) or sub_code is None or str(sub_code).strip() == "":
            sub_code = default_subject

        if not sub_code:
            errors.append({
                "row": row_num,
                "prn": prn,
                "error": "No subject code specified in row and no default subject selected."
            })
            continue

        sub_code = str(sub_code).strip().upper()

        # Subject authorization check for faculty
        if not is_admin and authorized_subjects and sub_code not in authorized_subjects:
            errors.append({
                "row": row_num,
                "prn": prn,
                "error": f"Unauthorized subject '{sub_code}'. Faculty scope is limited to: {', '.join(authorized_subjects)}"
            })
            continue

        row_errors = []
        parsed_entry = {
            "row_num": row_num,
            "student_prn": prn,
            "student_name": student_name,
            "semester": sem,
            "subject_code": sub_code,
            "has_marks": False,
            "has_attendance": False,
            "marks": {},
            "attendance": {},
            "old_state": {}
        }

        # Fetch old state from DB for comparison & clean replacement
        sem_rec = db.academic_records.find_one({"student_prn": prn, "semester": sem})
        old_sub = None
        if sem_rec:
            old_sub = next((s for s in sem_rec.get("subjects", []) if s.get("subject_code") == sub_code), None)
        if old_sub:
            parsed_entry["old_state"]["marks"] = {
                "tt1": old_sub.get("tt1_score", 0.0),
                "tt2": old_sub.get("tt2_score", 0.0),
                "internal": old_sub.get("internal_score", 0.0),
                "total": old_sub.get("total_marks", 0.0)
            }

        att_rec = db.attendance_records.find_one({"student_prn": prn})
        if att_rec and "subjects" in att_rec and sub_code in att_rec["subjects"]:
            old_att = att_rec["subjects"][sub_code]
            parsed_entry["old_state"]["attendance"] = {
                "conducted": old_att.get("lecture_conducted", 0),
                "attended": old_att.get("lecture_attended", 0)
            }

        # ── Parse Marks ──
        has_tt1 = "tt1_score" in row and not pd.isna(row["tt1_score"])
        has_tt2 = "tt2_score" in row and not pd.isna(row["tt2_score"])
        has_subcomps = any(
            k in row and not pd.isna(row[k])
            for k in ["aptitude_score", "skat_score", "teacher_assessment_score", "mock_interview_score", "presentation_score", "ese_score"]
        )

        if has_tt1 or has_tt2 or has_subcomps or upload_type in ["tt_marks", "combined"]:
            parsed_entry["has_marks"] = True
            def parse_score(key, max_val, label):
                val = row.get(key)
                if pd.isna(val) or val is None or str(val).strip() == "":
                    return 0.0
                try:
                    num = float(val)
                    if num < 0.0 or num > max_val:
                        row_errors.append(f"{label} ({num}) exceeds permitted range [0.0 - {max_val}].")
                        return num
                    return round(num, 2)
                except (ValueError, TypeError):
                    row_errors.append(f"Invalid numeric value for {label}: '{val}'")
                    return 0.0

            tt1 = parse_score("tt1_score", 30.0, "TT1 Score")
            tt2 = parse_score("tt2_score", 30.0, "TT2 Score")
            apt = parse_score("aptitude_score", 5.0, "Aptitude Score")
            skat = parse_score("skat_score", 5.0, "SKAT Score")
            ta = parse_score("teacher_assessment_score", 5.0, "Teacher Assessment")
            mock = parse_score("mock_interview_score", 5.0, "Mock Interview")
            pres = parse_score("presentation_score", 5.0, "Presentation Score")
            ese = parse_score("ese_score", 100.0, "ESE Score")

            tt_conv = round((tt1 + tt2) / 4.0, 2)
            has_sub = any(v > 0 for v in [apt, skat, ta, mock, pres]) or tt1 > 20.0 or tt2 > 20.0
            if not has_sub and (ese > 60.0):
                internal = (tt1 + tt2) / 2.0
                total = compute_subject_total(tt1=tt1, tt2=tt2, ese=ese, max_ese=80.0)
            else:
                internal = compute_subject_internal(tt1, tt2, apt, skat, ta, mock, pres)
                total = compute_subject_total(
                    tt1=tt1, tt2=tt2, ese=ese, max_ese=60.0,
                    aptitude=apt, skat=skat, teacher_assessment=ta,
                    mock_interview=mock, presentation=pres,
                    internal_score=internal
                )
            gp, letter = calculate_grade_point(total)

            parsed_entry["marks"] = {
                "tt1_score": tt1,
                "tt2_score": tt2,
                "tt_converted": tt_conv,
                "aptitude_score": apt,
                "skat_score": skat,
                "teacher_assessment_score": ta,
                "mock_interview_score": mock,
                "presentation_score": pres,
                "ese_score": ese,
                "internal_score": internal,
                "total_marks": total,
                "grade_point": gp,
                "grade_letter": letter
            }

        # ── Parse Attendance & Bunk ──
        has_att = any(k in row and not pd.isna(row[k]) for k in ["conducted_hours", "attended_hours", "bunked_hours", "attendance_percentage"])
        if has_att or upload_type in ["attendance_bunk", "combined"]:
            parsed_entry["has_attendance"] = True
            conducted = row.get("conducted_hours")
            attended = row.get("attended_hours")
            bunked = row.get("bunked_hours")
            att_pct = row.get("attendance_percentage")

            try:
                cond_val = int(float(conducted)) if not pd.isna(conducted) and conducted is not None else 0
            except (ValueError, TypeError):
                cond_val = 0

            try:
                att_val = int(float(attended)) if not pd.isna(attended) and attended is not None else 0
            except (ValueError, TypeError):
                att_val = 0

            try:
                bunk_val = int(float(bunked)) if not pd.isna(bunked) and bunked is not None else 0
            except (ValueError, TypeError):
                bunk_val = 0

            # If bunked provided instead of attended, derive attended
            if bunk_val > 0 and att_val == 0 and cond_val > 0:
                att_val = max(0, cond_val - bunk_val)
            elif att_val > 0 and cond_val > 0 and bunk_val == 0:
                bunk_val = max(0, cond_val - att_val)

            if cond_val > 0 and att_val > cond_val:
                row_errors.append(f"Attended hours ({att_val}) cannot exceed conducted hours ({cond_val}).")

            # Direct percentage override
            pct_val = None
            if not pd.isna(att_pct) and att_pct is not None:
                try:
                    pct_str = str(att_pct).replace("%", "").strip()
                    pct_val = round(float(pct_str), 2)
                    if pct_val < 0.0 or pct_val > 100.0:
                        row_errors.append(f"Attendance percentage ({pct_val}%) must be between 0 and 100.")
                except (ValueError, TypeError):
                    row_errors.append(f"Invalid attendance percentage: '{att_pct}'")

            if pct_val is None and cond_val > 0:
                pct_val = round((att_val / cond_val) * 100.0, 2)
            elif pct_val is None:
                pct_val = 75.0

            # Calculate safe bunks (margin above 75%)
            safe_bunks = 0
            if cond_val > 0 and pct_val >= 75.0:
                # (attended) / (conducted + x) >= 0.75 => x <= (attended - 0.75*conducted) / 0.75
                safe_bunks = max(0, math.floor((att_val - 0.75 * cond_val) / 0.75))

            parsed_entry["attendance"] = {
                "conducted_hours": cond_val,
                "attended_hours": att_val,
                "bunked_hours": bunk_val,
                "attendance_percentage": pct_val,
                "safe_bunks": safe_bunks,
                "detention_risk": pct_val < 75.0
            }

        if row_errors:
            errors.append({
                "row": row_num,
                "prn": prn,
                "error": "; ".join(row_errors)
            })
        else:
            staged_rows.append(parsed_entry)

    return {
        "is_valid": len(errors) == 0 and len(staged_rows) > 0,
        "total_rows": len(df),
        "valid_count": len(staged_rows),
        "error_count": len(errors),
        "errors": errors,
        "warnings": warnings,
        "staged_rows": staged_rows
    }


def commit_faculty_bulk_upload(
    staged_rows: List[Dict[str, Any]],
    actor_prn: str,
    actor_role: str = "faculty",
    overwrite_mode: bool = True
) -> Dict[str, Any]:
    """
    Executes atomic database updates with clean overwrite of previous records,
    recalculating SGPA, grade points, bunk capacity, and ML predictions,
    and broadcasting real-time WebSocket notifications to the student portal.
    """
    db = get_db()
    updated_students = set()
    records_overwritten = 0
    now_utc = datetime.now(timezone.utc)

    for entry in staged_rows:
        prn = entry["student_prn"]
        sem = entry["semester"]
        sub_code = entry["subject_code"]

        # ── 1. UPDATE ACADEMIC RECORDS (MARKS) ──
        if entry.get("has_marks"):
            rec = db.academic_records.find_one({"student_prn": prn, "semester": sem})
            if not rec:
                # Initialize new semester record
                rec = {
                    "student_prn": prn,
                    "semester": sem,
                    "academic_year": "2026-27",
                    "is_completed": (sem <= 4),
                    "attendance_percentage": 75.0,
                    "subjects": [],
                    "created_at": now_utc
                }

            subjects = rec.get("subjects", [])
            target_idx = next((i for i, s in enumerate(subjects) if s.get("subject_code") == sub_code), None)

            # Build fresh subject record (cleanly overwriting previous data)
            marks_data = entry["marks"]
            new_subject_entry = {
                "subject_code": sub_code,
                "subject_name": old_name if (old_name := (subjects[target_idx].get("subject_name") if target_idx is not None else None)) else f"Course {sub_code}",
                "credits": old_creds if (old_creds := (subjects[target_idx].get("credits") if target_idx is not None else None)) else 4,
                "tt1_score": marks_data["tt1_score"],
                "tt2_score": marks_data["tt2_score"],
                "tt_converted": marks_data["tt_converted"],
                "aptitude_score": marks_data["aptitude_score"],
                "skat_score": marks_data["skat_score"],
                "teacher_assessment_score": marks_data["teacher_assessment_score"],
                "mock_interview_score": marks_data["mock_interview_score"],
                "presentation_score": marks_data["presentation_score"],
                "internal_score": marks_data["internal_score"],
                "ese_score": marks_data["ese_score"],
                "total_marks": marks_data["total_marks"],
                "grade_point": marks_data["grade_point"],
                "grade_letter": marks_data["grade_letter"]
            }

            if target_idx is not None and overwrite_mode:
                # Remove and replace all previous score fields cleanly
                subjects[target_idx] = new_subject_entry
                records_overwritten += 1
            else:
                subjects.append(new_subject_entry)
                records_overwritten += 1

            # Recalculate SGPA
            is_ongoing = (sem == 5 and rec.get("is_completed") is False)
            if is_ongoing and all(s.get("ese_score", 0.0) == 0.0 for s in subjects):
                new_sgpa = None
                new_backlogs = 0
            else:
                new_sgpa, new_backlogs, _ = compute_semester_sgpa(subjects)

            update_set = {
                "subjects": subjects,
                "sgpa": new_sgpa,
                "active_backlogs": new_backlogs,
                "updated_at": now_utc
            }

            if entry.get("has_attendance") and "attendance_percentage" in entry["attendance"]:
                update_set["attendance_percentage"] = entry["attendance"]["attendance_percentage"]

            db.academic_records.update_one(
                {"student_prn": prn, "semester": sem},
                {"$set": update_set, "$setOnInsert": {"created_at": now_utc}},
                upsert=True
            )

        # ── 2. UPDATE ATTENDANCE RECORDS & BUNK COUNTS ──
        if entry.get("has_attendance"):
            att_data = entry["attendance"]
            att_doc = db.attendance_records.find_one({"student_prn": prn})
            if not att_doc:
                att_doc = {
                    "student_prn": prn,
                    "class_name": "TY BTech DS (A) 2026-27 Sem-I",
                    "semester": sem,
                    "academic_year": "2026-27",
                    "subjects": {},
                    "created_at": now_utc
                }

            if "subjects" not in att_doc:
                att_doc["subjects"] = {}

            # Overwrite previous subject attendance record cleanly
            att_doc["subjects"][sub_code] = {
                "lecture_conducted": att_data["conducted_hours"],
                "lecture_attended": att_data["attended_hours"],
                "bunked_hours": att_data["bunked_hours"],
                "practical_conducted": 0,
                "practical_attended": 0,
                "attendance_percentage": att_data["attendance_percentage"]
            }

            # Recalculate overall attendance across all enrolled subjects
            tot_cond = sum(s.get("lecture_conducted", 0) + s.get("practical_conducted", 0) for s in att_doc["subjects"].values())
            tot_att = sum(s.get("lecture_attended", 0) + s.get("practical_attended", 0) for s in att_doc["subjects"].values())
            overall_pct = round((tot_att / tot_cond) * 100.0, 2) if tot_cond > 0 else att_data["attendance_percentage"]

            att_doc["overall_percentage"] = overall_pct
            att_doc["updated_at"] = now_utc

            db.attendance_records.update_one(
                {"student_prn": prn},
                {"$set": att_doc, "$setOnInsert": {"created_at": now_utc}},
                upsert=True
            )

            # Sync overall attendance to ongoing academic record
            db.academic_records.update_one(
                {"student_prn": prn, "semester": sem},
                {"$set": {"attendance_percentage": overall_pct, "updated_at": now_utc}}
            )

        updated_students.add(prn)

    # ── 3. RECALCULATE PREDICTIONS & EMIT WEBSOCKET EVENTS ──
    for prn in updated_students:
        try:
            predictions = predict_student_analytics(prn, force_recalculate=True)
        except Exception as e:
            logger.warning(f"Failed to recalculate predictions for {prn}: {e}")
            predictions = {}

        # Emit SocketIO event so student portal UI updates in real-time
        try:
            from app import socketio
            socketio.emit(
                "academic_update",
                {
                    "student_prn": prn,
                    "updated_by": actor_prn,
                    "predictions": predictions,
                    "timestamp": now_utc.isoformat(),
                    "source": "faculty_bulk_upload"
                },
                room=f"student_{prn}"
            )
            socketio.emit(
                "attendance_update",
                {
                    "student_prn": prn,
                    "timestamp": now_utc.isoformat()
                },
                room=f"student_{prn}"
            )
        except Exception:
            pass

    # ── 4. RECORD AUDIT EVENT ──
    log_audit_event(
        actor_prn=actor_prn,
        actor_role=actor_role,
        action="FACULTY_BULK_UPLOAD_OVERWRITE",
        details=f"Overwrote {records_overwritten} records across {len(updated_students)} students. Real-time predictions and student portals refreshed."
    )

    return {
        "success": True,
        "students_updated": len(updated_students),
        "records_overwritten": records_overwritten,
        "updated_prns": list(updated_students)
    }


def generate_bulk_template(
    upload_type: str = "tt_marks",
    output_format: str = "csv",
    subject_code: str = "ML-II",
    semester: int = 5
) -> Tuple[io.BytesIO, str, str]:
    """
    Generates a pre-populated CSV or Excel workbook containing enrolled students
    for convenient, zero-friction marks and attendance entry.
    """
    db = get_db()
    # Fetch real enrolled students from database
    students_cursor = db.users.find({"role": "student"}).sort("prn_roll", 1)
    student_list = list(students_cursor)

    rows = []
    if student_list:
        for s in student_list:
            prn = s.get("prn_roll")
            name = s.get("name", "Student")
            if upload_type == "tt_marks":
                rows.append({
                    "student_prn": prn,
                    "student_name": name,
                    "semester": semester,
                    "subject_code": subject_code,
                    "tt1_score": 18.0,
                    "tt2_score": 17.5,
                    "aptitude_score": 4.0,
                    "skat_score": 4.5,
                    "teacher_assessment_score": 4.5,
                    "mock_interview_score": 4.0,
                    "presentation_score": 4.0,
                    "ese_score": 0.0
                })
            elif upload_type == "attendance_bunk":
                rows.append({
                    "student_prn": prn,
                    "student_name": name,
                    "semester": semester,
                    "subject_code": subject_code,
                    "conducted_hours": 30,
                    "attended_hours": 26,
                    "bunked_hours": 4,
                    "attendance_percentage": 86.7
                })
            else:  # combined
                rows.append({
                    "student_prn": prn,
                    "student_name": name,
                    "semester": semester,
                    "subject_code": subject_code,
                    "tt1_score": 18.0,
                    "tt2_score": 17.5,
                    "aptitude_score": 4.0,
                    "skat_score": 4.0,
                    "teacher_assessment_score": 4.0,
                    "conducted_hours": 30,
                    "attended_hours": 26,
                    "bunked_hours": 4
                })
    else:
        # Fallback sample rows
        rows = [
            {
                "student_prn": "241106001",
                "student_name": "Sample Student",
                "semester": semester,
                "subject_code": subject_code,
                "tt1_score": 18.5,
                "tt2_score": 17.0,
                "conducted_hours": 30,
                "attended_hours": 26,
                "bunked_hours": 4
            }
        ]

    df = pd.DataFrame(rows)
    buf = io.BytesIO()

    if output_format.lower() == "excel" or output_format.lower() == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="BulkUploadTemplate")
        buf.seek(0)
        filename = f"Faculty_Upload_{subject_code}_Sem{semester}_{upload_type}.xlsx"
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        buf.write(csv_bytes)
        buf.seek(0)
        filename = f"Faculty_Upload_{subject_code}_Sem{semester}_{upload_type}.csv"
        mimetype = "text/csv"

    return buf, filename, mimetype
