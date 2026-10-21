import io
import os
import re
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from PIL import Image
import fitz

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    winocr = None
    HAS_WINOCR = False

from utils.db import get_db
from utils.audit_logger import log_audit_event


def _run_async(coro):
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _clean_str(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


async def _ocr_image(image: Image.Image) -> Tuple[str, List[Any]]:
    """Runs winocr on image testing upright and rotated orientations."""
    if not HAS_WINOCR:
        return "", []

    best_text = ""
    best_lines = []
    rotations = [
        ("0 deg", None),
        ("90 deg CW", Image.Transpose.ROTATE_270),
        ("270 deg CW", Image.Transpose.ROTATE_90),
        ("180 deg", Image.Transpose.ROTATE_180),
    ]

    for label, rot in rotations:
        try:
            cur = image.transpose(rot) if rot is not None else image
            w, h = cur.size
            scaled = cur.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
            res = await winocr.recognize_pil(scaled, "en-US")
            if len(res.text) > len(best_text):
                best_text = res.text
                best_lines = res.lines
                if len(best_text) > 400 and any(k in best_text.lower() for k in ["roll", "prn", "attendance", "%", "detention"]):
                    break
        except Exception:
            continue

    return best_text, best_lines


def _lines_from_ocr_words(lines: List[Any]) -> List[str]:
    words_list = []
    for line in lines:
        for word in line.words:
            r = word.bounding_rect
            words_list.append((r.y, r.x, r.width, r.height, word.text))
    words_list.sort(key=lambda w: (w[0], w[1]))

    reconstructed_lines = []
    cur_line = []
    cur_y = None
    for y, x, w, h, wt in words_list:
        if cur_y is None or abs(y - cur_y) < 14:
            cur_line.append((x, wt))
            if cur_y is None:
                cur_y = y
        else:
            cur_line.sort(key=lambda t: t[0])
            reconstructed_lines.append(" ".join(t[1] for t in cur_line))
            cur_line = [(x, wt)]
            cur_y = y

    if cur_line:
        cur_line.sort(key=lambda t: t[0])
        reconstructed_lines.append(" ".join(t[1] for t in cur_line))

    return reconstructed_lines


def parse_detention_row_line(line: str, db_users_by_prn: dict, db_users_by_roll: dict) -> Optional[Dict[str, Any]]:
    """
    Parses a single row from OCR/text representing student attendance in detention table.
    Looks for Roll No (1-75), PRN (9 digits), Student Name, Attended, Conducted, and Percentage.
    """
    # Clean text
    clean_line = _clean_str(line)
    if not clean_line or len(clean_line) < 4:
        return None

    # Ignore header rows
    lower = clean_line.lower()
    if any(h in lower for h in ["roll no", "student name", "local guardian", "total attended", "conducted", "percentage", "signature"]):
        return None

    # Check for 9-digit PRN like 241106001
    prn_match = re.search(r"\b(241106\d{3}|2024\d{7,8}|\d{9,11})\b", clean_line)
    prn = prn_match.group(1) if prn_match else None

    # Extract all numbers from line
    numbers = []
    for tok in clean_line.split():
        # Handle percentage token like '66.67%' or '72%'
        num_str = re.sub(r"[^\d\.]", "", tok)
        if num_str:
            try:
                numbers.append(float(num_str))
            except ValueError:
                pass

    if not numbers and not prn:
        return None

    roll_no = None
    # If first token is integer between 1 and 75, that's roll_no
    first_tok = clean_line.split()[0]
    if first_tok.isdigit() and 1 <= int(first_tok) <= 80:
        roll_no = int(first_tok)

    # If PRN was found, match with DB user
    user = None
    if prn and prn in db_users_by_prn:
        user = db_users_by_prn[prn]
    elif roll_no and roll_no in db_users_by_roll:
        user = db_users_by_roll[roll_no]
        if not prn:
            prn = user.get("prn_roll")

    student_name = user.get("name") if user else ""
    if not student_name:
        # Extract letters
        letters_match = re.search(r"([A-Za-z\s]{5,35})", clean_line)
        if letters_match:
            student_name = _clean_str(letters_match.group(1)).title()

    # Determine percentage, attended, conducted
    percentage = None
    total_attended = None
    total_conducted = None

    # Check if a number with decimal exists (e.g. 66.67 or 77.01)
    decimals = [n for n in numbers if "." in str(n) and 0.0 <= n <= 100.0]
    if decimals:
        percentage = round(decimals[-1], 2)

    # Check for attended and conducted pair (e.g. 58 and 87)
    integers = [int(n) for n in numbers if n == int(n)]
    # Look for pair where conducted > attended and 20 <= conducted <= 150
    for i in range(len(integers) - 1):
        att = integers[i]
        cond = integers[i + 1]
        if 0 <= att <= cond and 20 <= cond <= 160:
            total_attended = att
            total_conducted = cond
            if percentage is None and cond > 0:
                percentage = round((att / cond) * 100, 2)
            break

    if percentage is None:
        # Find any number between 20 and 100
        pct_candidates = [n for n in numbers if 10.0 <= n <= 100.0]
        if pct_candidates:
            percentage = round(pct_candidates[-1], 2)
        else:
            return None

    if not prn and roll_no:
        prn = f"241106{roll_no:03d}"

    if not prn:
        return None

    is_detained = percentage < 75.0

    return {
        "roll_no": roll_no or (user.get("roll_no") if user else None),
        "student_prn": prn,
        "student_name": student_name or f"Student {prn}",
        "total_attended": total_attended,
        "total_conducted": total_conducted,
        "percentage": percentage,
        "is_detained": is_detained,
        "source_line": clean_line,
    }


def parse_detention_file(file_input: Any, filename: str) -> Dict[str, Any]:
    """
    Parses an uploaded detention list image (.png, .jpg), PDF, spreadsheet (.csv, .xlsx), or JSON file.
    Returns parsed student attendance list ready for staging and DB commit.
    """
    db = get_db()
    students_cursor = db.users.find({"role": "student"})
    db_users_by_prn = {}
    db_users_by_roll = {}
    for u in students_cursor:
        prn = str(u.get("prn_roll", "")).strip()
        db_users_by_prn[prn] = u
        roll = u.get("roll_no")
        if roll is not None:
            try:
                db_users_by_roll[int(roll)] = u
            except (ValueError, TypeError):
                pass

    filename_lower = filename.lower()
    raw_lines = []
    structured_records = []
    method = "unknown"

    # 1. JSON Upload
    if filename_lower.endswith(".json"):
        method = "json"
        content = file_input.read() if hasattr(file_input, "read") else file_input
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                prn = str(item.get("prn") or item.get("student_prn") or "").strip()
                pct = float(item.get("percentage") or item.get("recorded_percentage") or 0.0)
                u = db_users_by_prn.get(prn, {})
                structured_records.append({
                    "roll_no": item.get("roll_no") or u.get("roll_no"),
                    "student_prn": prn,
                    "student_name": item.get("student_name") or u.get("name") or f"Student {prn}",
                    "total_attended": item.get("total_attended"),
                    "total_conducted": item.get("total_conducted"),
                    "percentage": round(pct, 2),
                    "is_detained": pct < 75.0,
                })

    # 2. CSV or Excel Upload
    elif filename_lower.endswith((".csv", ".xlsx", ".xls")):
        method = "spreadsheet"
        if filename_lower.endswith(".csv"):
            df = pd.read_csv(file_input)
        else:
            df = pd.read_excel(file_input)

        # Standardize column headers
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        for _, row in df.iterrows():
            prn_val = str(row.get("student_prn") or row.get("prn") or row.get("roll_no") or "").strip()
            pct_val = row.get("percentage") or row.get("attendance_percentage") or row.get("pct")
            try:
                pct = float(pct_val)
            except (TypeError, ValueError):
                continue

            u = db_users_by_prn.get(prn_val) or db_users_by_roll.get(int(row.get("roll_no", 0)), {})
            if not u and prn_val:
                u = {"prn_roll": prn_val, "name": str(row.get("student_name") or f"Student {prn_val}")}

            final_prn = u.get("prn_roll", prn_val)
            structured_records.append({
                "roll_no": row.get("roll_no") or u.get("roll_no"),
                "student_prn": final_prn,
                "student_name": str(row.get("student_name") or u.get("name") or f"Student {final_prn}"),
                "total_attended": int(row.get("total_attended", 0)) if pd.notnull(row.get("total_attended")) else None,
                "total_conducted": int(row.get("total_conducted", 0)) if pd.notnull(row.get("total_conducted")) else None,
                "percentage": round(pct, 2),
                "is_detained": pct < 75.0,
            })

    # 3. PDF Upload
    elif filename_lower.endswith(".pdf"):
        method = "pdf"
        file_bytes = file_input.read() if hasattr(file_input, "read") else file_input
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            txt = page.get_text()
            if len(txt.strip()) > 100:
                raw_lines.extend(txt.splitlines())
            else:
                # OCR page
                pix = page.get_pixmap(dpi=220)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                _, ocr_lines = _run_async(_ocr_image(img))
                raw_lines.extend(_lines_from_ocr_words(ocr_lines))

    # 4. Image Upload (.png, .jpg, .jpeg, .webp)
    elif filename_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        method = "image_ocr"
        file_bytes = file_input.read() if hasattr(file_input, "read") else file_input
        img = Image.open(io.BytesIO(file_bytes))
        _, ocr_lines = _run_async(_ocr_image(img))
        raw_lines.extend(_lines_from_ocr_words(ocr_lines))

    # Parse text lines into student rows if not already structured
    if not structured_records and raw_lines:
        seen_prns = set()
        for line in raw_lines:
            row_rec = parse_detention_row_line(line, db_users_by_prn, db_users_by_roll)
            if row_rec and row_rec["student_prn"] not in seen_prns:
                seen_prns.add(row_rec["student_prn"])
                structured_records.append(row_rec)

    # Sort by roll_no
    structured_records.sort(key=lambda r: int(r.get("roll_no") or 999))

    # Attach old database attendance for visual before/after comparison
    for r in structured_records:
        prn = r["student_prn"]
        old_att = db.attendance_records.find_one({"student_prn": prn})
        if old_att:
            r["old_percentage"] = float(old_att.get("percentage", 0.0))
            r["old_is_detained"] = bool(old_att.get("is_detained", r["old_percentage"] < 75.0))
        else:
            r["old_percentage"] = None
            r["old_is_detained"] = None

    detained_count = sum(1 for r in structured_records if r["is_detained"])
    safe_count = len(structured_records) - detained_count

    return {
        "filename": filename,
        "method": method,
        "total_records": len(structured_records),
        "detained_count": detained_count,
        "safe_count": safe_count,
        "records": structured_records,
    }


def commit_detention_records(records: List[Dict[str, Any]], actor_prn: str = "ADMIN") -> Dict[str, Any]:
    """
    Commits updated detention list attendance data to MongoDB.
    - Updates `db.attendance_records` (total_attended, total_conducted, percentage, is_detained).
    - Updates student profile in `db.users`.
    - Invalidates `db.predictions_cache` for affected students so attendance forecast and risk matrix refresh immediately!
    - Logs audit trail event.
    """
    db = get_db()
    updated_count = 0
    affected_prns = []

    for r in records:
        prn = str(r.get("student_prn", "")).strip()
        if not prn:
            continue

        pct = float(r.get("percentage", 0.0))
        is_detained = bool(r.get("is_detained", pct < 75.0))
        total_att = r.get("total_attended")
        total_cond = r.get("total_conducted")

        # 1. Update attendance_records document
        update_set: Dict[str, Any] = {
            "percentage": pct,
            "recorded_percentage": int(round(pct)),
            "is_detained": is_detained,
            "updated_at": datetime.now(timezone.utc),
        }
        if total_att is not None:
            update_set["total_attended"] = int(total_att)
        if total_cond is not None:
            update_set["total_conducted"] = int(total_cond)

        db.attendance_records.update_one(
            {"student_prn": prn},
            {
                "$set": update_set,
                "$setOnInsert": {
                    "student_prn": prn,
                    "class_name": "TY DS (A) (2026-27)(SEM-1)",
                    "roll_no": r.get("roll_no"),
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        # 2. Update user profile
        db.users.update_one(
            {"prn_roll": prn},
            {
                "$set": {
                    "attendance_percentage": pct,
                    "is_detained": is_detained,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "prn_roll": prn,
                    "role": "student",
                    "name": r.get("student_name") or f"Student {prn}",
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        # 3. Invalidate predictions cache for this student
        db.predictions_cache.delete_many({"student_prn": prn})

        updated_count += 1
        affected_prns.append(prn)

    # Log audit event
    log_audit_event(
        actor_prn=actor_prn,
        actor_role="admin",
        action="DETENTION_LIST_REUPLOAD",
        details=f"Re-uploaded detention list: updated attendance and detention flags for {updated_count} students."
    )

    return {
        "status": "success",
        "updated_count": updated_count,
        "affected_prns": affected_prns,
    }
