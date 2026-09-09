import io
import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_student_transcript_pdf(student_data: dict, academic_records: list, current_sem: int = None, base_url: str = None) -> bytes:
    """
    Generates a formal, institute-style grade transcript PDF with embedded cryptographic verification QR code.
    
    :param student_data: Dict with student info (name, prn_roll, branch, admission_year)
    :param academic_records: List of academic record dicts for all completed semesters
    :param current_sem: Specific semester to generate (or all semesters if None)
    :param base_url: Base host URL for QR code verification portal
    :return: PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        alignment=1,  # Center
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#475569'),
        fontName='Helvetica'
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )
    normal_text = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica'
    )
    bold_text = ParagraphStyle(
        'BoldText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Header / Letterhead
    story.append(Paragraph("INSTITUTE OF HIGHER TECHNOLOGY & ADVANCED STUDIES", title_style))
    story.append(Paragraph("Accredited by NBA & NAAC 'A+' Grade | Affiliated University System", subtitle_style))
    story.append(Paragraph("OFFICIAL GRADE TRANSCRIPT & PERFORMANCE REPORT", ParagraphStyle('SubSub', parent=subtitle_style, fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#1D4ED8'))))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E293B'), spaceBefore=2, spaceAfter=10))

    # 2. Student Info Card
    info_data = [
        [
            Paragraph("<b>Student Name:</b>", bold_text),
            Paragraph(student_data.get("name", "N/A"), normal_text),
            Paragraph("<b>PRN / Roll No:</b>", bold_text),
            Paragraph(student_data.get("prn_roll", "N/A"), normal_text),
        ],
        [
            Paragraph("<b>Department / Branch:</b>", bold_text),
            Paragraph(student_data.get("branch", "N/A"), normal_text),
            Paragraph("<b>Admission Year:</b>", bold_text),
            Paragraph(str(student_data.get("admission_year", "N/A")), normal_text),
        ],
        [
            Paragraph("<b>Issue Date:</b>", bold_text),
            Paragraph(datetime.now().strftime("%d-%B-%Y"), normal_text),
            Paragraph("<b>Transcript Status:</b>", bold_text),
            Paragraph("<font color='green'><b>OFFICIAL & AUDITED</b></font>", normal_text),
        ]
    ]
    info_table = Table(info_data, colWidths=[120, 150, 110, 160])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # Filter records if current_sem is specified
    records_to_show = academic_records
    if current_sem:
        records_to_show = [r for r in academic_records if r.get("semester") == int(current_sem)]

    # 3. Semester Breakdown Tables
    for record in records_to_show:
        sem_num = record.get("semester", 1)
        sem_sgpa = record.get("sgpa", 0.0)
        attendance = record.get("attendance_percentage", 0.0)
        backlogs = record.get("active_backlogs", 0)

        story.append(Paragraph(f"Semester {sem_num} Academic Record", section_heading))
        story.append(Spacer(1, 4))

        # Subjects table header
        table_data = [[
            Paragraph("<b>Code</b>", bold_text),
            Paragraph("<b>Subject Name</b>", bold_text),
            Paragraph("<b>Credits</b>", bold_text),
            Paragraph("<b>TT1 (20)</b>", bold_text),
            Paragraph("<b>TT2 (20)</b>", bold_text),
            Paragraph("<b>ESE (80)</b>", bold_text),
            Paragraph("<b>Total (100)</b>", bold_text),
            Paragraph("<b>Grade</b>", bold_text),
            Paragraph("<b>Grade Pt</b>", bold_text),
        ]]

        total_sem_credits = 0
        total_credit_points = 0.0

        for sub in record.get("subjects", []):
            cr = int(sub.get("credits", 4))
            gp = float(sub.get("grade_point", 0.0))
            total_sem_credits += cr
            total_credit_points += (cr * gp)
            
            table_data.append([
                Paragraph(sub.get("subject_code", ""), normal_text),
                Paragraph(sub.get("subject_name", ""), normal_text),
                Paragraph(str(cr), normal_text),
                Paragraph(str(sub.get("tt1_score", 0.0)), normal_text),
                Paragraph(str(sub.get("tt2_score", 0.0)), normal_text),
                Paragraph(str(sub.get("ese_score", 0.0)), normal_text),
                Paragraph(str(sub.get("total_marks", 0.0)), normal_text),
                Paragraph(sub.get("grade_letter", "P"), bold_text),
                Paragraph(str(gp), normal_text),
            ])

        # Summary row for semester
        table_data.append([
            Paragraph("<b>SEMESTER TOTALS</b>", bold_text),
            Paragraph("", normal_text),
            Paragraph(f"<b>{total_sem_credits}</b>", bold_text),
            Paragraph("", normal_text),
            Paragraph("", normal_text),
            Paragraph("", normal_text),
            Paragraph("", normal_text),
            Paragraph(f"<b>SGPA:</b>", bold_text),
            Paragraph(f"<b>{sem_sgpa:.2f}</b>", bold_text),
        ])

        sub_table = Table(table_data, colWidths=[65, 175, 45, 45, 45, 45, 50, 40, 45])
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(sub_table)

        # Sem summary note
        summary_note = f"<b>Attendance:</b> {attendance}% | <b>Backlogs:</b> {backlogs} | <b>Total Credits:</b> {total_sem_credits} | <b>SGPA:</b> {sem_sgpa:.2f}"
        story.append(Spacer(1, 3))
        story.append(Paragraph(summary_note, normal_text))
        story.append(Spacer(1, 10))

    # 4. Cumulative Performance & Verification Box
    all_sgpas = [r.get("sgpa", 0.0) for r in academic_records]
    cgpa = round(sum(all_sgpas) / len(all_sgpas), 2) if all_sgpas else 0.0
    total_backlogs_all = sum(r.get("active_backlogs", 0) for r in academic_records)

    cum_data = [
        [
            Paragraph("<b>Cumulative Grade Point Average (CGPA):</b>", bold_text),
            Paragraph(f"<font size=11 color='#1D4ED8'><b>{cgpa:.2f} / 10.00</b></font>", bold_text),
            Paragraph("<b>Total Active Backlogs:</b>", bold_text),
            Paragraph(str(total_backlogs_all), normal_text),
        ]
    ]
    cum_table = Table(cum_data, colWidths=[200, 100, 140, 100])
    cum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#3B82F6')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(cum_table)
    story.append(Spacer(1, 20))

    # 5. Cryptographic Verification & QR Code Generation
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from utils.transcript_verifier import generate_transcript_signature

    issue_date_str = datetime.now().strftime("%Y-%m-%d")
    total_credits_earned = sum(sum(int(s.get("credits", 4)) for s in r.get("subjects", [])) for r in records_to_show)

    sig = generate_transcript_signature(
        prn_roll=student_data.get("prn_roll", ""),
        cgpa=cgpa,
        total_credits=total_credits_earned,
        total_backlogs=total_backlogs_all,
        issue_date=issue_date_str
    )
    verification_hash = sig[:24].upper()

    clean_base_url = (base_url or "http://localhost:5000").rstrip("/")
    verification_url = f"{clean_base_url}/auth/verify-transcript?prn={student_data.get('prn_roll')}&sig={sig}&date={issue_date_str}"

    qr_widget = qr.QrCodeWidget(verification_url)
    bounds = qr_widget.getBounds()
    qr_w = bounds[2] - bounds[0]
    qr_h = bounds[3] - bounds[1]
    qr_drawing = Drawing(65, 65, transform=[65.0 / qr_w, 0, 0, 65.0 / qr_h, 0, 0])
    qr_drawing.add(qr_widget)

    # Verification Table (QR Code + Cryptographic Ledger Details)
    verify_data = [
        [
            qr_drawing,
            [
                Paragraph("<b>CRYPTOGRAPHICALLY VERIFIED DIGITAL TRANSCRIPT</b>", ParagraphStyle('VTitle', parent=bold_text, fontSize=9, textColor=colors.HexColor('#0F766E'))),
                Spacer(1, 2),
                Paragraph(f"<b>Digital Signature:</b> <font fontName='Courier' size=7 color='#0F172A'>{sig}</font>", normal_text),
                Paragraph(f"<b>Security Hash:</b> <font fontName='Courier-Bold' size=8 color='#1D4ED8'>{verification_hash}</font> | <b>Date:</b> {issue_date_str}", normal_text),
                Paragraph(f"Scan QR code or visit: <font color='#2563EB'><u>{verification_url}</u></font>", ParagraphStyle('VUrl', parent=normal_text, fontSize=7, textColor=colors.HexColor('#2563EB'))),
                Paragraph("<font size=7 color='#475569'><i>This tamper-evident digital credential is authenticated against the university's permanent academic ledger.</i></font>", normal_text),
            ]
        ]
    ]
    verify_table = Table(verify_data, colWidths=[75, 465])
    verify_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDFA')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0D9488')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(verify_table)
    story.append(Spacer(1, 14))

    # 6. Signatures
    sig_data = [
        [
            Paragraph("Prepared by:<br/><b>Academic Records Office</b>", normal_text),
            Paragraph("Verified by:<br/><b>Dean of Academic Affairs</b>", normal_text),
            Paragraph("Authorized Signature:<br/><b>Controller of Examinations</b>", normal_text),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[180, 180, 180])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 10))

    footer_text = f"Document Hash: <b>{verification_hash}</b> | Official Electronic Credential issued on {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}. Any alteration renders this record void."
    story.append(Paragraph(footer_text, ParagraphStyle('FooterStyle', parent=normal_text, fontSize=7, textColor=colors.HexColor('#64748B'), alignment=1)))

    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content
