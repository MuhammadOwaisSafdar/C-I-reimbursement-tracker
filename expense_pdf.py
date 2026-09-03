"""
Builds an Expense Claim PDF from data entered in the app — the automated
replacement for filling the standalone HTML form and printing/uploading a PDF.

This does not try to pixel-match the original branded HTML/jsPDF form (that
JavaScript can't run inside this Python app), but it produces a clean,
professional PDF with the same information: header, expense rows, total,
and a signatures block.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from xml.sax.saxutils import escape


def build_expense_pdf(path, header, rows, signatories):
    """
    path: output file path (.pdf)
    header: dict with keys — company, department, month_label, expense_type,
            reason, cost_centre, sale_order, customer, sale_type, employee
    rows: list of dicts — each with 'date', 'detail', 'amount'
    signatories: dict with keys — employee, ops_lead, vp
    """
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleC", parent=styles["Title"], alignment=TA_CENTER, fontSize=16, spaceAfter=2)
    sub_style = ParagraphStyle(
        "SubC", parent=styles["Normal"], alignment=TA_CENTER, textColor=colors.grey, fontSize=9)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading3"], fontSize=10, textColor=colors.HexColor("#1F4E78"),
        spaceBefore=10, spaceAfter=4)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    story = []

    company = escape(header.get("company", "SkyElectric"))
    department = escape(header.get("department", "C&I Operations"))
    story.append(Paragraph(company, title_style))
    story.append(Paragraph(f"{department} — Expense Claim", sub_style))
    story.append(Spacer(1, 10))

    header_table_data = [
        ["Month", header.get("month_label", ""), "Expense Type", header.get("expense_type", "")],
        ["Reason", header.get("reason", ""), "Cost Centre", header.get("cost_centre", "")],
        ["Sale Order No.", header.get("sale_order", ""), "Sale Type", header.get("sale_type", "")],
        ["Customer", header.get("customer", ""), "Employee", header.get("employee", "")],
    ]
    ht = Table(header_table_data, colWidths=[32 * mm, 60 * mm, 32 * mm, 50 * mm])
    ht.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F5F9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F5F9")),
    ]))
    story.append(ht)

    story.append(Paragraph("Expense Rows", section_style))
    row_data = [["#", "Date", "Expense Details", "Amount (PKR)"]]
    total = 0.0
    for i, r in enumerate(rows, start=1):
        amt = float(r.get("amount") or 0)
        total += amt
        row_data.append([str(i), r.get("date", ""), r.get("detail", ""), f"{amt:,.2f}"])
    row_data.append(["", "", "TOTAL", f"{total:,.2f}"])

    rt = Table(row_data, colWidths=[10 * mm, 28 * mm, 92 * mm, 34 * mm], repeatRows=1)
    style_cmds = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.3, colors.HexColor("#DDDDDD")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    rt.setStyle(TableStyle(style_cmds))
    story.append(rt)

    story.append(Paragraph("Signatures and Approvals", section_style))
    sig_data = [
        [signatories.get("employee", ""), signatories.get("ops_lead", ""), signatories.get("vp", "")],
        ["_" * 22, "_" * 22, "_" * 22],
        ["Signature: Project Engineer", "Signature: Operations Lead", "Signature: Director Operations"],
    ]
    st_ = Table(sig_data, colWidths=[54 * mm, 54 * mm, 54 * mm])
    st_.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(Spacer(1, 8))
    story.append(st_)

    doc.build(story)
    return total
