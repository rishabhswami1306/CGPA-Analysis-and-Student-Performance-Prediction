import io
import re
import os
import zipfile
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

from PIL import Image
import fitz

# Try importing winocr
try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    winocr = None
    HAS_WINOCR = False

from utils.db import get_db
from utils.grade_calculator import (
    calculate_grade_point,
    compute_semester_sgpa,
    compute_cumulative_cgpa,
)


GRADE_POINTS_MAP = {
    "O": 10.0,
    "A+": 9.0,
    "A": 8.0,
    "B+": 7.0,
    "B": 6.0,
    "C": 5.0,
    "P": 4.0,
    "F": 0.0,
}


def _run_async(coro):
    """Executes an async coroutine thread-safely inside synchronous contexts."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _clean_str(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _clean_numeric_tokens(text: str) -> str:
    """Normalizes OCR numbers, decimal separators, and fixes common OCR glitches."""
    if not text:
        return ""
    t = text
    # Fix split decimals: '99. 00' -> '99.00', '46. 00' -> '46.00'
    t = re.sub(r"(\d+)\.\s+(\d{1,2})", r"\1.\2", t)
    # Fix numbers ending with dot: '38.' -> '38.00', '21.' -> '21.00'
    t = re.sub(r"\b(\d+)\.(?!\d)", r"\1.00", t)
    # Fix European / misread comma: '8,14' -> '8.14'
    t = re.sub(r"\b(\d+),(\d{1,2})\b", r"\1.\2", t)
    # Fix misread letters in digits: '2S.00' -> '25.00', '2S.oo' -> '25.00'
    t = re.sub(r"\b([0-9])S\.([0-9oO]{2})\b", r"\g<1>5.\2", t)
    t = t.replace("2S.oo", "25.00").replace("2S.00", "25.00").replace("2s.00", "25.00")
    t = t.replace(".oo", ".00").replace(".o0", ".00").replace(".Oo", ".00")
    # Fix letter O or o as zero in decimals: '0.O0' -> '0.00'
    t = re.sub(r"\b[oO]\.00\b", "0.00", t)
    return t


def _parse_semester(text: str) -> int:
    """Parses semester string to integer (e.g. SEM-III -> 3, Third YearSEM-111 -> 3, 1st Sem -> 1, Sem 4 -> 4)."""
    if not text:
        return 1
    
    # 1. Direct regex for SEM-III / SEM-111 / SEM 3 / SEMESTER IV / SEMESTER 4
    m = re.search(r"SEM(?:ESTER)?[\s\-_]*([IVX]+|111|11|1|2|3|4|5|6|7|8)\b", text, re.IGNORECASE)
    if m:
        token = m.group(1).upper()
        roman_map = {
            "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
            "111": 3, "11": 2, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8
        }
        if token in roman_map:
            return roman_map[token]
        if token.isdigit():
            return int(token)

    # 2. Check ordinal formats like 1st Sem, 2nd Sem, 3rd Sem, 4th Sem, 5th Sem, etc.
    ord_m = re.search(r"\b([1-8])(?:st|nd|rd|th)?\s*SEM(?:ESTER)?\b", text, re.IGNORECASE)
    if ord_m:
        return int(ord_m.group(1))

    # 3. Check standalone roman or word phrases
    upper = text.upper()
    if "FIRST" in upper or "SEM-I" in upper or "SEM 1" in upper or "1ST SEM" in upper:
        return 1
    if "SECOND" in upper or "SEM-II" in upper or "SEM 2" in upper or "2ND SEM" in upper:
        return 2
    if "THIRD" in upper or "SEM-III" in upper or "SEM 3" in upper or "3RD SEM" in upper or "SEM-111" in upper:
        return 3
    if "FOURTH" in upper or "SEM-IV" in upper or "SEM 4" in upper or "4TH SEM" in upper:
        return 4
    if "FIFTH" in upper or "SEM-V" in upper or "SEM 5" in upper or "5TH SEM" in upper:
        return 5
    if "SIXTH" in upper or "SEM-VI" in upper or "SEM 6" in upper or "6TH SEM" in upper:
        return 6
    if "SEVENTH" in upper or "SEM-VII" in upper or "SEM 7" in upper or "7TH SEM" in upper:
        return 7
    if "EIGHTH" in upper or "SEM-VIII" in upper or "SEM 8" in upper or "8TH SEM" in upper:
        return 8

    # 4. Fallback: check Year
    if "THIRD YEAR" in upper or "TY" in upper:
        return 3
    if "SECOND YEAR" in upper or "SE" in upper:
        return 3 if "ODD" in upper else 4
    if "FIRST YEAR" in upper or "FE" in upper:
        return 1

    return 1


def get_student_year_context(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes completed semester list based on registered student's current year and semester.
    1 academic year = 2 semesters.
    - If in 1st year: completed = [1]
    - If in 2nd year: completed = [1, 2]
    - If in 3rd year: completed = [1, 2, 3, 4] (4 completed semesters: 1st, 2nd, 3rd, 4th)
    - If in 4th year: completed = [1, 2, 3, 4, 5, 6] (6 completed semesters)
    """
    curr_yr_raw = str(user.get("current_year", "")).lower()
    curr_sem = int(user.get("current_semester", 0) or 0)

    # Determine numeric year (1, 2, 3, 4)
    if "first" in curr_yr_raw or "1" in curr_yr_raw or "fe" in curr_yr_raw:
        year_num = 1
    elif "second" in curr_yr_raw or "2" in curr_yr_raw or "se" in curr_yr_raw:
        year_num = 2
    elif "third" in curr_yr_raw or "3" in curr_yr_raw or "te" in curr_yr_raw or "ty" in curr_yr_raw:
        year_num = 3
    elif "fourth" in curr_yr_raw or "final" in curr_yr_raw or "4" in curr_yr_raw or "be" in curr_yr_raw or "ly" in curr_yr_raw:
        year_num = 4
    elif curr_sem > 0:
        year_num = min(4, max(1, (curr_sem + 1) // 2))
    else:
        year_num = 3

    # Default completed semesters:
    if curr_sem > 1:
        default_sems = list(range(1, curr_sem))
    else:
        if year_num == 1:
            default_sems = [1]
        elif year_num == 2:
            default_sems = [1, 2]
        elif year_num == 3:
            default_sems = [1, 2, 3, 4]
        else:
            default_sems = [1, 2, 3, 4, 5, 6]

    year_labels = {
        1: "First Year (FE)",
        2: "Second Year (SE)",
        3: "Third Year (TE / TY)",
        4: "Final Year (BE / Final)",
    }

    return {
        "year_num": year_num,
        "year_label": year_labels.get(year_num, f"Year {year_num}"),
        "current_semester": curr_sem or (year_num * 2 - 1),
        "default_semesters": default_sems,
    }


def _extract_branch_code(programme: str) -> str:
    """Extracts short branch code from programme string."""
    if not programme:
        return "CSE-DS"
    prog_upper = programme.upper()
    if "ARTIFICIAL" in prog_upper or "AIML" in prog_upper or "AI &" in prog_upper:
        return "CSE-AIML"
    if "DATA SCIENCE" in prog_upper:
        return "CSE-DS"
    if "COMPUTER" in prog_upper:
        return "CSE"
    if "INFORMATION TECHNOLOGY" in prog_upper or "IT" in prog_upper:
        return "IT"
    if "CIVIL" in prog_upper:
        return "CIVIL"
    if "MECHANICAL" in prog_upper:
        return "MECH"
    if "ELECTRICAL" in prog_upper:
        return "EE"
    if "ELECTRONICS" in prog_upper or "ENTC" in prog_upper:
        return "ENTC"
    return "CSE-DS"


def _parse_course_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single course row from OCR or digital text.
    Expected format: [Subject Name] [Course Code] [Credits] [CA Max] [CA Marks] [ESE Max] [ESE Marks] [Total] [Grade]
    Accurately handles all marking and numbering formats, scaling lab/mini-project marks based on their actual maximum marks.
    """
    line_clean = line.strip()
    # Find course code token like RCP23DPC201, RCP23DPC201L, CS301, DS401, etc.
    code_pattern = re.compile(r"\b([A-Z]{2,6}[0-9]{1,4}[A-Za-z0-9_\-\.]{0,8})\b")
    matches = list(code_pattern.finditer(line_clean))
    valid_matches = [
        m for m in matches
        if len(m.group(1)) >= 5
        and any(c.isdigit() for c in m.group(1))
        and any(c.isalpha() for c in m.group(1))
    ]

    if not valid_matches:
        return None

    # Take the code match
    code_match = valid_matches[0]
    subject_name = line_clean[:code_match.start()].strip()
    raw_code = code_match.group(1).strip()
    # Clean OCR artefacts from code
    subject_code = re.sub(r"[^A-Za-z0-9]", "", raw_code).upper()

    rest = line_clean[code_match.end():].strip()
    rest_normalized = _clean_numeric_tokens(rest)

    tokens = rest_normalized.split()
    numbers: List[float] = []
    grade_letter: Optional[str] = None

    for tok in tokens:
        clean_tok = tok.strip(".,;:|").upper()
        if clean_tok in ["O", "A+", "A", "B+", "B", "C", "P", "F"]:
            grade_letter = clean_tok
            continue
        if clean_tok == "O":
            grade_letter = "O"
            continue

        num_match = re.search(r"^\d+(?:\.\d+)?$", tok.strip(".,;:|"))
        if num_match:
            try:
                numbers.append(float(num_match.group(0)))
            except ValueError:
                pass

    if not numbers or len(numbers) < 1:
        return None

    # First number is Credits
    credits_val = int(round(numbers[0]))
    if credits_val < 1 or credits_val > 6:
        credits_val = 3

    ca_max: Optional[float] = None
    ese_max: Optional[float] = None
    ca_marks: Optional[float] = None
    ese_marks: Optional[float] = None
    total_marks: Optional[float] = None

    if len(numbers) >= 6:
        # Format: [Credits, CA_Max, CA_Marks, ESE_Max, ESE_Marks, Total]
        ca_max = numbers[1]
        ca_marks = numbers[2]
        ese_max = numbers[3]
        ese_marks = numbers[4]
        total_marks = numbers[5]
    elif len(numbers) == 5:
        # Check if numbers[1] or numbers[2] is CA_Max
        if numbers[1] in [25.0, 40.0, 50.0] and numbers[3] in [25.0, 50.0, 60.0]:
            ca_max = numbers[1]
            ca_marks = numbers[2]
            ese_marks = numbers[3]
            total_marks = numbers[4]
        else:
            ca_marks = numbers[1]
            ese_max = numbers[2]
            ese_marks = numbers[3]
            total_marks = numbers[4]
    elif len(numbers) == 4:
        # Format: [Credits, CA_Marks, ESE_Marks, Total]
        ca_marks = numbers[1]
        ese_marks = numbers[2]
        total_marks = numbers[3]
    elif len(numbers) == 3:
        if numbers[0] <= 5.0 and numbers[1] > 5.0:
            credits_val = int(round(numbers[0]))
            total_marks = numbers[1]
        else:
            total_marks = numbers[-1]
    elif len(numbers) >= 1:
        total_marks = numbers[-1]

    if total_marks is None:
        if ca_marks is not None and ese_marks is not None:
            total_marks = round(ca_marks + ese_marks, 2)
        elif numbers:
            total_marks = numbers[-1]
        else:
            total_marks = 0.0

    # Determine Maximum Marks and Percentage for accurate grade mapping
    max_marks = 0.0
    if ca_max is not None and ese_max is not None and (ca_max + ese_max) > 0:
        max_marks = ca_max + ese_max
    elif total_marks is not None:
        if total_marks <= 25.0 and (ca_marks is None or ca_marks <= 25.0):
            max_marks = 25.0
        elif total_marks <= 50.0:
            max_marks = 50.0
        else:
            max_marks = 100.0

    # Ensure max_marks is never less than total_marks
    if total_marks is not None and total_marks > max_marks:
        if total_marks > 50.0:
            max_marks = 100.0
        elif total_marks > 25.0:
            max_marks = 50.0
        else:
            max_marks = 25.0

    # Ensure ca_max is consistent if ca_marks was parsed
    if ca_marks is not None and ca_marks > (ca_max or 0.0):
        if max_marks > (ese_max or 0.0):
            ca_max = max_marks - (ese_max or 0.0)
        elif ca_marks > 25.0:
            ca_max = 50.0
        else:
            ca_max = 25.0

    # Ensure ese_max is consistent if ese_marks was parsed
    if ese_marks is not None and ese_marks > (ese_max or 0.0):
        if max_marks > (ca_max or 0.0):
            ese_max = max_marks - (ca_max or 0.0)
        elif ese_marks > 25.0:
            ese_max = 50.0
        else:
            ese_max = 25.0

    # Re-verify max_marks = ca_max + ese_max if both are present
    if (ca_max or 0.0) + (ese_max or 0.0) > max_marks:
        max_marks = (ca_max or 0.0) + (ese_max or 0.0)

    if max_marks > 0:
        percentage = min(100.0, max(0.0, (total_marks / max_marks) * 100.0))
    else:
        percentage = min(100.0, max(0.0, total_marks))

    # Determine grade point and grade letter
    if grade_letter and grade_letter in GRADE_POINTS_MAP:
        grade_point = GRADE_POINTS_MAP[grade_letter]
    else:
        grade_point, calculated_letter = calculate_grade_point(percentage)
        grade_letter = calculated_letter

    # Filter out spurious header words in subject name
    subject_name = re.sub(r"^(?:THIRD\s+SEMESTER|SEMESTER|COURSE\s+NAME|SUBJECTS?)\s*", "", subject_name, flags=re.IGNORECASE).strip()
    # Normalize subject suffix if dropped by OCR onto next line
    if subject_code.endswith("L") and not any(k in subject_name.lower() for k in ["lab", "laboratory", "practical"]):
        subject_name = f"{subject_name} Laboratory".strip()
    elif subject_code.endswith("P") and not any(k in subject_name.lower() for k in ["project", "practice"]):
        subject_name = f"{subject_name} Project".strip()

    if not subject_name:
        subject_name = f"Course {subject_code}"

    return {
        "subject_code": subject_code,
        "subject_name": subject_name,
        "credits": credits_val,
        "ca_max": round(ca_max, 2) if ca_max is not None else 0.0,
        "ca_marks": round(ca_marks, 2) if ca_marks is not None else 0.0,
        "ese_max": round(ese_max, 2) if ese_max is not None else 0.0,
        "ese_marks": round(ese_marks, 2) if ese_marks is not None else 0.0,
        "max_marks": round(max_marks, 2),
        "total_marks": round(total_marks, 2),
        "percentage": round(percentage, 1),
        "grade_letter": grade_letter,
        "grade_point": float(grade_point),
    }


async def _ocr_image_best_orientation(image: Image.Image) -> Tuple[str, List[Any]]:
    """Runs winocr on image testing 4 orientations to extract maximum text content."""
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
            # Scale 2.5x for crisp OCR line detection
            w, h = cur.size
            scaled = cur.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
            res = await winocr.recognize_pil(scaled, "en-US")
            if len(res.text) > len(best_text):
                best_text = res.text
                best_lines = res.lines
                # If we got strong marksheet text (> 500 chars), we found the right orientation
                if len(best_text) > 800 and any(k in best_text.lower() for k in ["marks", "grade", "prn", "semester", "sgpa"]):
                    break
        except Exception:
            continue

    return best_text, best_lines


def _lines_from_ocr_words(lines: List[Any]) -> List[str]:
    """
    Sorts words by (Y, X) coordinates and reconstructs horizontal rows.
    Uses dynamic vertical center clustering to accurately keep table columns
    in the same row even on slightly skewed scans.
    """
    words_list = []
    for line in lines:
        for word in line.words:
            r = word.bounding_rect
            words_list.append((r.y, r.x, r.width, r.height, word.text))
    words_list.sort(key=lambda w: (w[0], w[1]))

    rows = []
    for y, x, w, h, wt in words_list:
        cy = y + h / 2.0
        matched_row = None
        for row in rows:
            row_cy = row["cy"]
            row_h = row["avg_h"]
            if abs(cy - row_cy) < max(18.0, row_h * 0.55):
                matched_row = row
                break
        if matched_row is not None:
            matched_row["words"].append((x, wt))
            matched_row["cy"] = (matched_row["cy"] * (len(matched_row["words"]) - 1) + cy) / len(matched_row["words"])
            matched_row["avg_h"] = max(matched_row["avg_h"], h)
        else:
            rows.append({"cy": cy, "avg_h": h, "words": [(x, wt)]})

    rows.sort(key=lambda r: r["cy"])
    reconstructed_lines = []
    for r in rows:
        r["words"].sort(key=lambda t: t[0])
        reconstructed_lines.append(" ".join(t[1] for t in r["words"]))

    return reconstructed_lines


def parse_result_pdf(
    file_input: Union[str, bytes, io.BytesIO],
    filename: str = "result.pdf",
    override_prn: Optional[str] = None,
    override_semester: Optional[int] = None,
    student_name_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parses a student marksheet / result PDF.
    Supports both digital text-layer PDFs and scanned marksheet images (via native Windows OCR).
    Returns structured academic record dictionary.
    """
    result: Dict[str, Any] = {
        "filename": filename,
        "status": "error",
        "error_message": "",
        "confidence": "low",
        "student_prn": override_prn.strip() if override_prn else None,
        "student_name": student_name_hint.strip() if student_name_hint else None,
        "mother_name": None,
        "programme": None,
        "branch": "CSE-DS",
        "semester": int(override_semester) if override_semester else 1,
        "academic_year": "2025-2026",
        "examination": None,
        "sgpa": None,
        "cgpa": None,
        "credits_earned": None,
        "computed_sgpa": None,
        "subjects": [],
        "extraction_method": "text",
    }

    try:
        # Determine document type & load pages (supports PDF and direct raster images)
        doc = None
        raw_bytes = None
        if isinstance(file_input, str):
            doc = fitz.open(file_input)
        elif isinstance(file_input, bytes):
            raw_bytes = file_input
        else:
            if hasattr(file_input, "seek"):
                try:
                    file_input.seek(0)
                except Exception:
                    pass
            raw_bytes = file_input.read()

        if doc is None and raw_bytes:
            lower_name = filename.lower()
            if any(lower_name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".jfif"]):
                try:
                    ext = lower_name.rsplit(".", 1)[-1]
                    doc = fitz.open(stream=raw_bytes, filetype=ext)
                except Exception:
                    pass
            if doc is None:
                try:
                    doc = fitz.open(stream=raw_bytes, filetype="pdf")
                except Exception:
                    try:
                        doc = fitz.open(stream=raw_bytes)
                    except Exception as err:
                        result["error_message"] = f"Could not read document or image: {err}"
                        return result

        if not doc or len(doc) == 0:
            result["error_message"] = "Uploaded marksheet file is empty (0 pages)."
            return result

        lines: List[str] = []
        methods_used: List[str] = []

        # Iterate all pages to support single and multi-page marksheets
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            digital_text = page.get_text()

            # Determine extraction strategy per page
            if len(digital_text.strip()) > 50 and any(k in digital_text.lower() for k in ["marks", "grade", "prn", "sgpa", "statement", "credit"]):
                methods_used.append("digital_text")
                # 1. Reconstruct horizontal lines by word bounding boxes (essential for tabular marksheets)
                words = page.get_text("words")
                if words:
                    rows = []
                    for w in sorted(words, key=lambda x: (x[1], x[0])):
                        x0, y0, text = w[0], w[1], w[4]
                        matched = None
                        for r in rows:
                            if abs(r["y"] - y0) < 4:
                                matched = r
                                break
                        if matched:
                            matched["words"].append((x0, text))
                        else:
                            rows.append({"y": y0, "words": [(x0, text)]})
                    for r in rows:
                        r["words"].sort(key=lambda x: x[0])
                        lines.append(" ".join(t[1] for t in r["words"]))
                # 2. Also append raw split lines
                lines.extend([l.strip() for l in digital_text.splitlines() if l.strip()])
            else:
                methods_used.append("windows_ocr")
                pix = page.get_pixmap(dpi=250)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text, ocr_lines = _run_async(_ocr_image_best_orientation(img))
                if ocr_lines:
                    lines.extend(_lines_from_ocr_words(ocr_lines))

        result["extraction_method"] = " / ".join(dict.fromkeys(methods_used)) if methods_used else "windows_ocr"

        if not lines:
            result["error_message"] = "Failed to extract text using OCR. Please check image clarity."
            return result

        full_text = "\n".join(lines)

        # 1. Extract Student Name
        name_m = re.search(r"Nam[ec]\s*(?:Of\s*)?(?:th[ce]\s*)?Student\s*[:\-]?\s*([A-Za-z\s]+?)(?=\s*(?:Mother|PRN|Roll|Programme|\n|$))", full_text, re.IGNORECASE)
        if name_m:
            result["student_name"] = _clean_str(name_m.group(1)).title()

        # 2. Extract Mother Name
        mom_m = re.search(r"Mother\s*Nam[ec]\s*[:\-]?\s*([A-Za-z\s]+?)(?=\s*(?:Programme|PRN|Roll|Year|\n|$))", full_text, re.IGNORECASE)
        if mom_m:
            result["mother_name"] = _clean_str(mom_m.group(1)).title()

        # 3. Extract PRN
        if override_prn:
            result["student_prn"] = str(override_prn).strip()
        else:
            prn_m = re.search(r"(?:PRN|Roll\s*No|Seat\s*No)[\s:\-]*([0-9]{8,12})", full_text, re.IGNORECASE)
            if not prn_m:
                prn_m = re.search(r"\b(2[0-9]{8,10})\b", full_text)
            if prn_m:
                result["student_prn"] = prn_m.group(1).strip()

        # 4. Extract Programme & Branch
        prog_m = re.search(r"Programme\s*[:\-]?\s*([A-Za-z0-9\(\)\s\-]+?)(?=\s*(?:PRN|Year|Academic|Examination|\n|$))", full_text, re.IGNORECASE)
        if prog_m:
            raw_prog = _clean_str(prog_m.group(1))
            result["programme"] = raw_prog
            result["branch"] = _extract_branch_code(raw_prog)

        # 5. Extract Semester
        if override_semester is not None:
            try:
                result["semester"] = int(override_semester)
            except (ValueError, TypeError):
                result["semester"] = 1
        else:
            sem_m = re.search(r"(?:Year\s*&\s*)?Semester\s*[:\-]?\s*([A-Za-z0-9\-\s]+?)(?=\s*(?:Academic|Examination|\n|$))", full_text, re.IGNORECASE)
            if sem_m:
                result["semester"] = _parse_semester(sem_m.group(1))
            else:
                # Fallback scan for SEM-III / SEM-IV etc.
                result["semester"] = _parse_semester(full_text)

        # 6. Extract Academic Year
        acad_m = re.search(r"Academic\s*Year\s*[:\-]?\s*(\d{4}[-\/]\d{2,4})", full_text, re.IGNORECASE)
        if acad_m:
            result["academic_year"] = acad_m.group(1).strip()

        # 7. Extract Examination
        exam_m = re.search(r"Examination\s*[:\-]?\s*([A-Za-z0-9\-\s]+?)(?=\s*(?:Subjects|Course|\n|$))", full_text, re.IGNORECASE)
        if exam_m:
            result["examination"] = _clean_str(exam_m.group(1))

        # 8. Extract SGPA
        sgpa_m = re.search(r"SGPA(?:\s*\([^)]*\))?\s*[:\s=]+\s*([0-9]+\.[0-9]+)", full_text, re.IGNORECASE)
        if not sgpa_m:
            sgpa_m = re.search(r"SGPA\s*(?:\([^)]*\)\s*)?[:\s=]*\n*[:\s=]*\s*([0-9]+\.[0-9]+)", full_text, re.IGNORECASE)
        if not sgpa_m:
            sgpa_m = re.search(r"SGPA[\s\S]{0,50}?[:\s=]+\s*([0-9]+\.[0-9]{2})", full_text, re.IGNORECASE)
        if sgpa_m:
            result["sgpa"] = float(sgpa_m.group(1))

        # 9. Extract CGPA
        cgpa_m = re.search(r"CGPA(?:\s*\([^)]*\))?\s*[:\s=]+\s*([0-9]+\.[0-9]+)", full_text, re.IGNORECASE)
        if not cgpa_m:
            cgpa_m = re.search(r"CGPA\s*(?:\([^)]*\)\s*)?[:\s=]*\n*[:\s=]*\s*([0-9]+\.[0-9]+)", full_text, re.IGNORECASE)
        if not cgpa_m:
            cgpa_m = re.search(r"CGPA[\s\S]{0,50}?[:\s=]+\s*([0-9]+\.[0-9]{2})", full_text, re.IGNORECASE)
        if cgpa_m:
            result["cgpa"] = float(cgpa_m.group(1))

        # 10. Extract Credits Earned
        cr_m = re.search(r"CR(?:Earned)?(?:\s*\([^)]*\))?\s*[:\s=]+\s*([0-9]{1,3})", full_text, re.IGNORECASE)
        if not cr_m:
            cr_m = re.search(r"CR(?:Earned)?[\s\S]{0,50}?[:\s=]+\s*([0-9]{1,3})", full_text, re.IGNORECASE)
        if cr_m:
            result["credits_earned"] = int(cr_m.group(1))

        # 11. Extract Course Rows
        subjects = []
        seen_codes = set()
        for line in lines:
            c = _parse_course_line(line)
            if c and c["subject_code"] not in seen_codes:
                seen_codes.add(c["subject_code"])
                subjects.append(c)

        result["subjects"] = subjects

        # Compute SGPA from parsed subjects
        if subjects:
            total_points = sum(s["credits"] * s["grade_point"] for s in subjects)
            total_credits = sum(s["credits"] for s in subjects)
            computed = round(total_points / total_credits, 2) if total_credits > 0 else 0.0
            result["computed_sgpa"] = computed
            if result["sgpa"] is None:
                result["sgpa"] = computed
            if result["credits_earned"] is None or result["credits_earned"] < total_credits:
                result["credits_earned"] = total_credits

        # Assess confidence & completion status
        if result["student_prn"] and len(subjects) >= 3:
            result["status"] = "success"
            if result["sgpa"] is not None:
                result["confidence"] = "high"
            else:
                result["confidence"] = "medium"
        elif result["student_prn"] or len(subjects) >= 1:
            result["status"] = "warning"
            result["confidence"] = "medium"
            result["error_message"] = "Partial data parsed. Please review fields before saving."
        else:
            result["status"] = "error"
            result["error_message"] = "Could not identify student PRN or course table from marksheet."

    except Exception as e:
        result["status"] = "error"
        result["error_message"] = f"Extraction failed: {str(e)}"

    return result


def parse_batch_pdfs(files: List[Any], purge_legacy: bool = False) -> Dict[str, Any]:
    """
    Parses a batch of uploaded files (PDFs or ZIP archive containing PDFs).
    Returns a unified batch report.
    """
    parsed_records = []
    errors = []

    for item in files:
        filename = getattr(item, "filename", "uploaded_file")
        if not filename:
            continue

        filename_lower = filename.lower()
        if filename_lower.endswith(".zip"):
            try:
                zip_bytes = item.read() if hasattr(item, "read") else item
                with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                    for zip_name in z.namelist():
                        if any(zip_name.lower().endswith(ext) for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]) and not zip_name.startswith("__MACOSX"):
                            item_bytes = z.read(zip_name)
                            base_name = os.path.basename(zip_name)
                            rec = parse_result_pdf(item_bytes, filename=base_name)
                            parsed_records.append(rec)
            except Exception as e:
                errors.append(f"Failed to extract ZIP file {filename}: {str(e)}")

        elif any(filename_lower.endswith(ext) for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]):
            try:
                rec = parse_result_pdf(item, filename=filename)
                parsed_records.append(rec)
            except Exception as e:
                errors.append(f"Failed to parse marksheet {filename}: {str(e)}")

    success_count = sum(1 for r in parsed_records if r["status"] == "success")
    warning_count = sum(1 for r in parsed_records if r["status"] == "warning")
    error_count = sum(1 for r in parsed_records if r["status"] == "error") + len(errors)

    return {
        "total_files": len(parsed_records),
        "success_count": success_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "records": parsed_records,
        "errors": errors,
        "purge_legacy": purge_legacy,
    }


def commit_result_records(
    records: List[Dict[str, Any]],
    purge_legacy_seed: bool = True,
    actor_prn: str = "ADMIN"
) -> Dict[str, Any]:
    """
    Commits verified real student result records to MongoDB.
    - Upserts students in `db.users`.
    - Purges previous testing/temporary mock data for the affected students if requested.
    - Upserts semester documents in `db.academic_records`.
    - Invalidates `db.predictions_cache` for affected PRNs so AI models re-predict on REAL ground truth.
    """
    db = get_db()
    committed_students = set()
    committed_semesters = 0
    errors = []

    for rec in records:
        prn = str(rec.get("student_prn") or "").strip()
        sem = int(rec.get("semester") or 1)
        subjects = rec.get("subjects") or []

        if not prn or not subjects:
            errors.append(f"Skipped record ({rec.get('filename')}): missing PRN or subjects.")
            continue

        student_name = rec.get("student_name") or f"Student {prn}"
        branch = rec.get("branch") or "CSE-DS"
        acad_year = rec.get("academic_year") or "2025-2026"
        sgpa = float(rec.get("sgpa") or rec.get("computed_sgpa") or 0.0)
        cgpa = float(rec.get("cgpa") or sgpa)
        credits_earned = int(rec.get("credits_earned") or sum(s["credits"] for s in subjects))

        # Check for active backlogs (F grades or gp == 0)
        active_backlogs = sum(1 for s in subjects if s.get("grade_letter") == "F" or s.get("grade_point", 0.0) == 0.0)

        # 1. Purge legacy mock data for this specific semester if requested
        if purge_legacy_seed:
            db.academic_records.delete_many({
                "student_prn": prn,
                "semester": sem,
                "is_real_marksheet": {"$ne": True}
            })
            # Also clear cached predictions
            db.predictions_cache.delete_many({"student_prn": prn})

        # 2. Upsert user in db.users
        existing_user = db.users.find_one({"prn_roll": prn})
        curr_sem = existing_user.get("current_semester", 5) if existing_user else max(sem + 1, 5)
        user_update = {
            "name": student_name,
            "branch": branch,
            "role": "student",
            "is_active": True,
            "is_real_student": True,
            "current_semester": max(curr_sem, sem + 1 if sem < 8 else 8),
            "updated_at": datetime.now(timezone.utc),
        }
        if rec.get("mother_name"):
            user_update["mother_name"] = rec["mother_name"]

        db.users.update_one(
            {"prn_roll": prn},
            {
                "$set": user_update,
                "$setOnInsert": {
                    "prn_roll": prn,
                    "email": f"{prn}@rcpit.ac.in",
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        # 3. Format subject documents for academic_records with complete key aliases
        formatted_subjects = []
        for s in subjects:
            ca = float(s.get("ca_marks", 0.0))
            ese = float(s.get("ese_marks", 0.0))
            tot = float(s.get("total_marks", ca + ese))
            tt_conv = round(ca * 0.5, 2)
            tt_val = round(ca * 0.75, 1)
            formatted_subjects.append({
                "subject_code": s["subject_code"],
                "course_code": s["subject_code"],
                "subject_name": s["subject_name"],
                "course_name": s["subject_name"],
                "credits": s["credits"],
                "ca_marks": ca,
                "internal_score": ca,
                "total_internal_40": ca,
                "ese_marks": ese,
                "ese_score": ese,
                "total_marks": tot,
                "total_100": tot,
                "grade_letter": s.get("grade_letter", "P"),
                "grade_point": s.get("grade_point", 4.0),
                "tt1_score": tt_val,
                "tt2_score": tt_val,
                "tt_converted": tt_conv,
                "tt_converted_15": tt_conv,
            })

        # 4. Determine semester attendance percentage
        att_rec = db.attendance_records.find_one({"student_prn": prn, "semester": sem})
        if not att_rec:
            att_rec = db.attendance_records.find_one({"student_prn": prn})
        att_pct = float(att_rec.get("attendance_percentage") or att_rec.get("percentage") or 82.5) if att_rec else 82.5

        # 5. Upsert semester record in db.academic_records
        academic_doc = {
            "student_prn": prn,
            "semester": sem,
            "academic_year": acad_year,
            "subjects": formatted_subjects,
            "courses": formatted_subjects,
            "sgpa": sgpa,
            "cgpa": cgpa,
            "active_backlogs": active_backlogs,
            "credits_earned": credits_earned,
            "attendance_percentage": att_pct,
            "is_completed": True,
            "status": "completed",
            "is_real_marksheet": True,
            "source_file": rec.get("filename"),
            "updated_at": datetime.now(timezone.utc),
        }

        db.academic_records.update_one(
            {"student_prn": prn, "semester": sem},
            {
                "$set": academic_doc,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )

        # 6. Ensure attendance collection is synchronized
        db.attendance_records.update_one(
            {"student_prn": prn, "semester": sem},
            {
                "$set": {
                    "attendance_percentage": att_pct,
                    "percentage": att_pct,
                    "student_name": student_name,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "student_prn": prn,
                    "semester": sem,
                    "total_conducted": 120,
                    "total_attended": int(120 * att_pct / 100),
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        committed_students.add(prn)
        committed_semesters += 1

    # Recalculate cumulative CGPA across all completed semesters for affected students
    for prn in committed_students:
        all_recs = list(db.academic_records.find({"student_prn": prn, "is_completed": True, "sgpa": {"$ne": None}}).sort("semester", 1))
        if all_recs:
            cum_cgpa, tot_backlogs, tot_credits = compute_cumulative_cgpa(all_recs)
            # Update user profile with cumulative summary
            db.users.update_one(
                {"prn_roll": prn},
                {"$set": {
                    "cgpa": cum_cgpa,
                    "active_backlogs": tot_backlogs,
                    "credits_earned": tot_credits,
                }}
            )
    # Automatically retrain ML pipelines on fresh ground truth marks
    try:
        from ml_engine.train_models import retrain_all_models
        retrain_all_models()
    except Exception:
        pass

    # Immediately recompute predictions and refresh cache for all affected students
    predictions_by_prn = {}
    try:
        from ml_engine.inference import predict_student_analytics
        for prn in committed_students:
            pred = predict_student_analytics(prn, force_recalculate=True)
            if pred:
                predictions_by_prn[prn] = pred
    except Exception as e:
        logger.warning(f"Prediction calculation notice: {e}")

    return {
        "status": "success",
        "committed_students_count": len(committed_students),
        "committed_semesters_count": committed_semesters,
        "affected_prns": list(committed_students),
        "predictions": predictions_by_prn,
        "errors": errors,
    }
