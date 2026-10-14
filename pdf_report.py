"""
pdf_report.py — Professional PDF birthday report using ReportLab
"""
import io
from datetime import date, datetime
import calendar as cal_module

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Palette ────────────────────────────────────────────────────────────────────
FOREST   = colors.HexColor("#1a2e1e")
GOLD     = colors.HexColor("#c9a84c")
GOLD_LT  = colors.HexColor("#f5eccc")
GREEN_LT = colors.HexColor("#edf7f1")
IVORY    = colors.HexColor("#f8f2e6")
GREY     = colors.HexColor("#7a8c72")
WHITE    = colors.white


def generate_birthday_report(
    students: list,
    query_date: date = None,
    title: str = None,
) -> bytes:
    """Return raw PDF bytes for a birthday report."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="BIT Birthday Report",
        author="Bannari Amman Institute of Technology",
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", fontName="Helvetica-Bold",
                        fontSize=18, textColor=FOREST,
                        alignment=TA_CENTER, spaceAfter=4)
    H2 = ParagraphStyle("H2", fontName="Helvetica-Bold",
                        fontSize=12, textColor=FOREST,
                        alignment=TA_CENTER, spaceAfter=2)
    SUB = ParagraphStyle("SUB", fontName="Helvetica",
                         fontSize=10, textColor=GREY,
                         alignment=TA_CENTER, spaceAfter=10)
    NOTE = ParagraphStyle("NOTE", fontName="Helvetica-Oblique",
                          fontSize=8.5, textColor=GREY,
                          alignment=TA_CENTER)

    story = []

    # ── Header ──
    story.append(Paragraph("Bannari Amman Institute of Technology", H1))
    story.append(Paragraph("Office of Student Affairs", H2))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=GOLD, spaceAfter=10))

    report_title = title or (
        f"Birthday Report — {query_date.strftime('%d %B %Y')}"
        if query_date
        else f"Birthday Report — {date.today().strftime('%d %B %Y')}"
    )
    story.append(Paragraph(report_title, H2))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        SUB
    ))

    if not students:
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(
            "No birthday records found for the selected date.", NOTE))
    else:
        story.append(Paragraph(f"Total: <b>{len(students)}</b> student(s)", SUB))
        story.append(Spacer(1, 0.3*cm))

        # ── Table ──
        header = ["#", "Name", "Date of Birth", "Email"]
        rows   = [header]
        for i, s in enumerate(students, 1):
            rows.append([str(i), s["name"], s.get("dob", "—"), s["email"]])

        col_widths = [0.8*cm, 5.2*cm, 3.5*cm, 7.5*cm]
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header row
            ("BACKGROUND",    (0, 0), (-1, 0), FOREST),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 10),
            ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
            # Data rows
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 9),
            ("ALIGN",         (0, 1), (0, -1),  "CENTER"),
            ("ALIGN",         (2, 1), (2, -1),  "CENTER"),
            ("TOPPADDING",    (0, 1), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
            # Alternating row colours
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREEN_LT]),
            # Grid
            ("GRID",          (0, 0), (-1, -1), 0.4,
             colors.HexColor("#d4be93")),
            ("LINEBELOW",     (0, 0), (-1, 0),  1.5, GOLD),
        ]))
        story.append(tbl)

    # ── Footer ──
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Bannari Amman Institute of Technology · Sathyamangalam · Tamil Nadu",
        NOTE))
    story.append(Paragraph("This document is system-generated.", NOTE))

    doc.build(story)
    return buf.getvalue()
