"""
Builds a SkyElectric Expense Claim PDF from data entered in the app — the
automated replacement for filling the standalone HTML form, printing it, and
uploading the PDF separately.

Two pages, matching the original HTML/jsPDF tool's output:
  1. Header info, itemized expense rows, total, signature block.
  2. Receipts — uploaded photos laid out in a 2-column x 3-row grid per page.

Uses the actual SkyElectric logo (assets/sky_logo.jpg, extracted from the
original form) rather than plain text, and the same brand colors.
"""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader
from xml.sax.saxutils import escape

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "sky_logo.jpg")

# Brand colors pulled from the original HTML form
BRAND_GREEN = colors.HexColor("#7CFC94")
BRAND_BLUE = colors.HexColor("#1A73E8")
BRAND_NAVY = colors.HexColor("#0F0F1A")
GREY = colors.HexColor("#7878A0")
LIGHT_GREY = colors.HexColor("#F2F5F9")
BORDER_GREY = colors.HexColor("#CCCCCC")


def _header_flowables(header):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleL", parent=styles["Title"], alignment=TA_LEFT, fontSize=18,
        textColor=BRAND_NAVY, spaceAfter=0, leading=20)
    sub_style = ParagraphStyle(
        "SubL", parent=styles["Normal"], alignment=TA_LEFT, textColor=GREY, fontSize=9.5, leading=12)

    company = escape(header.get("company", "SkyElectric"))
    department = escape(header.get("department", "C&I Operations"))

    title_block = [
        Paragraph(company, title_style),
        Paragraph(f"{department} — Expense Claim", sub_style),
    ]

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=16 * mm, height=16 * mm)
        row = Table([[logo, title_block]], colWidths=[20 * mm, 140 * mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        flows = [row]
    else:
        flows = title_block

    accent_bar = Table([[""]], colWidths=[172 * mm], rowHeights=[1.6])
    accent_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN)]))
    flows.append(Spacer(1, 8))
    flows.append(accent_bar)
    flows.append(Spacer(1, 10))
    return flows


def build_expense_pdf(path, header, rows, signatories, receipts=None):
    """
    path: output file path (.pdf)
    header: dict — company, department, month_label, expense_type, reason,
            cost_centre, sale_order, customer, sale_type, employee
    rows: list of dicts — each with 'date', 'detail', 'amount'
    signatories: dict — employee, ops_lead, vp (VP = 3rd signature block)
    receipts: optional list of image file paths to lay out on a Receipts page
    """
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading3"], fontSize=10.5, textColor=BRAND_BLUE,
        spaceBefore=12, spaceAfter=5)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    story = []
    story.extend(_header_flowables(header))

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
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_GREY),
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
    rt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.3, colors.HexColor("#DDDDDD")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
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

    # ---- Receipts page(s): 2 columns x 3 rows per page, matching drawRcptPage ----
    valid_receipts = [r for r in (receipts or []) if r and os.path.exists(r)]
    if valid_receipts:
        story.append(PageBreak())
        story.append(Paragraph("Receipts / Supporting Documents", ParagraphStyle(
            "RcptTitle", parent=styles["Heading2"], fontSize=13, textColor=BRAND_NAVY, spaceAfter=10)))

        cell_w, cell_h = 82 * mm, 78 * mm
        grid_rows = []
        row_cells = []
        for idx, rpath in enumerate(valid_receipts):
            try:
                iw, ih = ImageReader(rpath).getSize()
                avail_w, avail_h = cell_w - 6 * mm, cell_h - 14 * mm
                scale = min(avail_w / iw, avail_h / ih)
                img = Image(rpath, width=iw * scale, height=ih * scale)
            except Exception:
                img = Paragraph("Could not load image", styles["Normal"])
            label = Paragraph(
                f"<b>Receipt {idx + 1}</b>",
                ParagraphStyle("RcptLbl", parent=styles["Normal"], fontSize=8, textColor=GREY))
            cell = Table([[label], [img]], colWidths=[cell_w - 4 * mm])
            cell.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 1), (0, 1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            row_cells.append(cell)
            if len(row_cells) == 2:
                grid_rows.append(row_cells)
                row_cells = []
        if row_cells:
            row_cells.append("")
            grid_rows.append(row_cells)

        # 3 rows per page
        for chunk_start in range(0, len(grid_rows), 3):
            chunk = grid_rows[chunk_start:chunk_start + 3]
            if chunk_start > 0:
                story.append(PageBreak())
            grid = Table(chunk, colWidths=[cell_w, cell_w], rowHeights=[cell_h] * len(chunk))
            grid.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(grid)

    doc.build(story)
    return total
