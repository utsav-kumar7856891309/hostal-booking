import io
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_transfer_letter_pdf(transfer_record):
    """
    Generates an official downloadable university room transfer letter PDF using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor('#1e3a8a')
    secondary_color = colors.HexColor('#0284c7')
    dark_neutral = colors.HexColor('#1e293b')

    header_style = ParagraphStyle(
        'UnivHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=1  # Centered
    )

    sub_header_style = ParagraphStyle(
        'UnivSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_neutral,
        alignment=1
    )

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=secondary_color,
        alignment=1
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=dark_neutral
    )

    label_style = ParagraphStyle(
        'DocLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=primary_color
    )

    elements = []

    # University Header
    univ_name = transfer_record.previous_hostel.university.name
    univ_address = transfer_record.previous_hostel.university.address
    elements.append(Paragraph(univ_name.upper(), header_style))
    elements.append(Paragraph("OFFICE OF THE CHIEF WARDEN & HOSTEL ADMINISTRATION", sub_header_style))
    elements.append(Paragraph(univ_address, sub_header_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=15))

    # Document Title & Reference
    elements.append(Paragraph("OFFICIAL HOSTEL BED ALLOCATION TRANSFER CERTIFICATE", title_style))
    elements.append(Spacer(1, 10))

    meta_data = [
        [Paragraph(f"<b>Transfer Reference ID:</b> {transfer_record.transfer_id}", body_style),
         Paragraph(f"<b>Issue Date:</b> {transfer_record.transfer_date.strftime('%B %d, %Y')}", body_style)],
        [Paragraph(f"<b>Exchange Proposal Code:</b> {transfer_record.proposal.proposal_code if transfer_record.proposal else 'N/A'}", body_style),
         Paragraph(f"<b>Academic Session:</b> 2026-2027", body_style)],
    ]
    t_meta = Table(meta_data, colWidths=[3.5 * inch, 3.5 * inch])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 15))

    # Student Details
    student = transfer_record.student
    elements.append(Paragraph("<b>1. STUDENT PARTICULARS</b>", label_style))
    elements.append(Spacer(1, 5))

    student_data = [
        [Paragraph("<b>Student Name:</b>", body_style), Paragraph(student.full_name, body_style),
         Paragraph("<b>Student ID:</b>", body_style), Paragraph(student.student_id, body_style)],
        [Paragraph("<b>Registration No.:</b>", body_style), Paragraph(student.registration_number, body_style),
         Paragraph("<b>Gender:</b>", body_style), Paragraph(student.gender, body_style)],
        [Paragraph("<b>Degree Program:</b>", body_style), Paragraph(student.course, body_style),
         Paragraph("<b>Academic Year:</b>", body_style), Paragraph(student.academic_year, body_style)],
    ]
    t_stu = Table(student_data, colWidths=[1.6 * inch, 2.0 * inch, 1.4 * inch, 2.0 * inch])
    t_stu.setStyle(TableStyle([
        ('PADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    elements.append(t_stu)
    elements.append(Spacer(1, 15))

    # Transfer Details Table
    elements.append(Paragraph("<b>2. ALLOCATION TRANSFER DETAILS</b>", label_style))
    elements.append(Spacer(1, 5))

    transfer_table_data = [
        [Paragraph("<b>Attribute</b>", label_style), Paragraph("<b>Previous Allocation (Vacated)</b>", label_style), Paragraph("<b>New Allocation (Assigned)</b>", label_style)],
        [Paragraph("Hostel Name", body_style), Paragraph(transfer_record.previous_hostel.name, body_style), Paragraph(transfer_record.new_hostel.name, body_style)],
        [Paragraph("Hostel Code", body_style), Paragraph(transfer_record.previous_hostel.code, body_style), Paragraph(transfer_record.new_hostel.code, body_style)],
        [Paragraph("Room Number", body_style), Paragraph(transfer_record.previous_room.room_number, body_style), Paragraph(transfer_record.new_room.room_number, body_style)],
        [Paragraph("Bed Identifier", body_style), Paragraph(transfer_record.previous_bed.full_code, body_style), Paragraph(transfer_record.new_bed.full_code, body_style)],
        [Paragraph("Room Category", body_style), Paragraph(transfer_record.previous_category.name, body_style), Paragraph(transfer_record.new_category.name, body_style)],
        [Paragraph("Annual Room Fee", body_style), Paragraph(f"₹{transfer_record.previous_annual_fee:,.2f}", body_style), Paragraph(f"₹{transfer_record.new_annual_fee:,.2f}", body_style)],
    ]

    t_transfer = Table(transfer_table_data, colWidths=[2.2 * inch, 2.4 * inch, 2.4 * inch])
    t_transfer.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0f2fe')),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(t_transfer)
    elements.append(Spacer(1, 15))

    # Financial Summary
    elements.append(Paragraph("<b>3. FINANCIAL ADJUSTMENT SUMMARY</b>", label_style))
    elements.append(Spacer(1, 5))

    fin_data = [
        [Paragraph("Annual Fee Difference:", body_style), Paragraph(f"₹{transfer_record.fee_difference:,.2f}", body_style)],
        [Paragraph("Exchange Administrative Processing Fee:", body_style), Paragraph(f"₹{transfer_record.processing_fee:,.2f}", body_style)],
        [Paragraph("Advance Credit Generated (for next year):", body_style), Paragraph(f"₹{transfer_record.advance_balance_generated:,.2f}", body_style)],
        [Paragraph("<b>Financial Settlement Status:</b>", body_style), Paragraph("<b>COMPLETED (Verified)</b>", body_style)],
    ]
    t_fin = Table(fin_data, colWidths=[4.5 * inch, 2.5 * inch])
    t_fin.setStyle(TableStyle([
        ('PADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    elements.append(t_fin)
    elements.append(Spacer(1, 20))

    # Approvals & Signatures
    elements.append(Paragraph("<b>4. STATUTORY AUTHORIZATIONS</b>", label_style))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"Approvals verified: {transfer_record.approved_by_summary or 'Authorized by Hostel Administration'}", body_style))
    elements.append(Spacer(1, 30))

    sig_data = [
        [Paragraph("____________________________<br/><b>Student Signature</b>", body_style),
         Paragraph("____________________________<br/><b>Hostel Warden Signature</b>", body_style),
         Paragraph("____________________________<br/><b>Chief Warden Signature & Seal</b>", body_style)]
    ]
    t_sig = Table(sig_data, colWidths=[2.3 * inch, 2.3 * inch, 2.4 * inch])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_sig)
    elements.append(Spacer(1, 25))

    # Verification Note
    note_text = "<i>Note: This is an authentic digitally generated hostel allocation order issued by HostelX. Any unauthorized alternation invalidates this document. The student must take physical possession of the allotted bed within 48 hours of issue.</i>"
    elements.append(Paragraph(note_text, ParagraphStyle('Note', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#64748b'), alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
