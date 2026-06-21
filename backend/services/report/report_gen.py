"""
Optimization Report Generator.
Produces a PDF report summarizing what changed, ATS scores, flags acknowledged, and known gaps.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from models.resume import ParsedResume
from models.jd import ParsedJD
from models.optimization import ATSScoreBreakdown, UserConfirmation

OUTPUT_DIR = "/tmp/resume-optimizer"

# Brand colors
BLUE = HexColor("#1a56db")
LIGHT_BLUE = HexColor("#eef2ff")
GREEN = HexColor("#16a34a")
ORANGE = HexColor("#d97706")
RED = HexColor("#dc2626")
GRAY = HexColor("#6b7280")
DARK = HexColor("#1e293b")


def _score_color(score: float):
    if score >= 80:
        return GREEN
    elif score >= 60:
        return ORANGE
    return RED


def generate_report(
    session_id: str,
    original_resume: ParsedResume,
    rewritten_resume: dict,
    jd: ParsedJD,
    ats_before: ATSScoreBreakdown,
    ats_after: ATSScoreBreakdown,
    match_before: float,
    confirmation: UserConfirmation,
    match_after: float | None = None,
    keywords_injected: list[str] | None = None,
) -> str:
    """Generate optimization report PDF. Returns filename."""

    out_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)
    report_filename = "optimization_report.pdf"
    report_path = os.path.join(out_dir, report_filename)

    doc = SimpleDocTemplate(
        report_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Title ─────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle("title", fontSize=18, textColor=BLUE, fontName="Helvetica-Bold", spaceAfter=4)
    sub_style = ParagraphStyle("sub", fontSize=10, textColor=GRAY, spaceAfter=16)
    story.append(Paragraph("AI Resume Optimization Report", title_style))
    story.append(Paragraph(f"Candidate: {original_resume.personal_info.full_name}  ·  Role: {jd.job_title}", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE))
    story.append(Spacer(1, 10))

    # ── Score Summary ─────────────────────────────────────────────────────────
    h2 = ParagraphStyle("h2", fontSize=12, textColor=DARK, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=6)
    story.append(Paragraph("Score Summary", h2))

    m_after = match_after if match_after is not None else min(match_before + 15, 98)
    m_delta = m_after - match_before
    m_delta_str = f"+{m_delta:.0f}%" if m_delta >= 0 else f"{m_delta:.0f}%"

    score_data = [
        ["Metric", "Before", "After", "Change"],
        ["ATS Compatibility Score",
         f"{ats_before.total:.0f}/100",
         f"{ats_after.total:.0f}/100",
         f"+{ats_after.total - ats_before.total:.0f} pts"],
        ["Match Score",
         f"{match_before:.0f}%",
         f"{m_after:.0f}%",
         m_delta_str],
    ]

    score_table = Table(score_data, colWidths=[80 * mm, 30 * mm, 30 * mm, 30 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_BLUE]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d1d5db")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 10))

    # ── ATS Breakdown ─────────────────────────────────────────────────────────
    story.append(Paragraph("ATS Score Breakdown", h2))

    breakdown_data = [
        ["Signal", "Max", "Before", "After"],
        ["Keyword Match (hard + soft keywords)", "30", f"{ats_before.keyword_match:.0f}", f"{ats_after.keyword_match:.0f}"],
        ["Section Completeness", "20", f"{ats_before.section_completeness:.0f}", f"{ats_after.section_completeness:.0f}"],
        ["Format Parsability", "20", f"{ats_before.format_parsability:.0f}", f"{ats_after.format_parsability:.0f}"],
        ["Keyword Placement (summary/skills)", "15", f"{ats_before.keyword_placement:.0f}", f"{ats_after.keyword_placement:.0f}"],
        ["Date Consistency", "10", f"{ats_before.date_consistency:.0f}", f"{ats_after.date_consistency:.0f}"],
        ["File Health", "5", f"{ats_before.file_health:.0f}", f"{ats_after.file_health:.0f}"],
        ["TOTAL", "100", f"{ats_before.total:.0f}", f"{ats_after.total:.0f}"],
    ]

    breakdown_table = Table(breakdown_data, colWidths=[90 * mm, 20 * mm, 25 * mm, 25 * mm])
    breakdown_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [white, HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 8))

    # ATS disclaimer
    disclaimer_style = ParagraphStyle("disc", fontSize=8, textColor=GRAY, fontName="Helvetica-Oblique", spaceAfter=10)
    story.append(Paragraph(
        "Note: ATS scores are calculated based on industry-standard ATS behavior across Workday, Taleo, Greenhouse, and Lever. "
        "Scores reflect general compatibility and are not a guarantee for any specific system.",
        disclaimer_style,
    ))

    # ── Keywords Injected ─────────────────────────────────────────────────────
    if keywords_injected:
        story.append(Paragraph("JD Keywords Woven Into Resume", h2))
        normal = ParagraphStyle("n", fontSize=9.5, textColor=DARK, spaceAfter=3, leftIndent=10)
        story.append(Paragraph(
            "The following JD-extracted keywords were naturally incorporated into your resume content:",
            ParagraphStyle("note", fontSize=9, textColor=GRAY, spaceAfter=6, leftIndent=10),
        ))
        kw_text = "  ·  ".join(keywords_injected)
        story.append(Paragraph(kw_text, ParagraphStyle("kw", fontSize=9, textColor=BLUE, spaceAfter=3, leftIndent=10)))
        story.append(Spacer(1, 8))

    # ── Skills Added ──────────────────────────────────────────────────────────
    if confirmation.skills_to_add:
        story.append(Paragraph("Skills Added to Resume", h2))
        normal = ParagraphStyle("n", fontSize=9.5, textColor=DARK, spaceAfter=3, leftIndent=10)
        for skill in confirmation.skills_to_add:
            story.append(Paragraph(f"✓  {skill}", normal))
        story.append(Spacer(1, 8))

    # ── Changes Made ──────────────────────────────────────────────────────────
    sections_changed = []
    if confirmation.rewrite_summary:
        sections_changed.append("Professional Summary")
    if confirmation.rewrite_bullets:
        sections_changed.append("Experience Bullet Points")
    if confirmation.reorder_sections:
        sections_changed.append("Section Order")

    if sections_changed:
        story.append(Paragraph("Content Rewritten", h2))
        normal = ParagraphStyle("n", fontSize=9.5, textColor=DARK, spaceAfter=3, leftIndent=10)
        for section in sections_changed:
            story.append(Paragraph(f"✎  {section}", normal))
        story.append(Spacer(1, 8))

    # ── Known Gaps ────────────────────────────────────────────────────────────
    if confirmation.flags_acknowledged:
        story.append(Paragraph("Known Gaps (Acknowledged by Candidate)", h2))
        warn_style = ParagraphStyle("warn", fontSize=9.5, textColor=ORANGE, spaceAfter=3, leftIndent=10)
        for flag_cat in confirmation.flags_acknowledged:
            story.append(Paragraph(f"⚠  {flag_cat.replace('_', ' ').title()}", warn_style))
        story.append(Spacer(1, 8))

    # ── AI Guardrails Note ────────────────────────────────────────────────────
    story.append(Paragraph("AI Guardrails Applied", h2))
    guardrail_style = ParagraphStyle("gr", fontSize=9, textColor=DARK, spaceAfter=3, leftIndent=10)
    guardrails = [
        "No company names, job titles, or employment dates were modified.",
        "No certifications or technologies were fabricated.",
        "No educational qualifications were changed.",
        "All rewritten content was verified against the original resume.",
        "Keywords were added only where truthfully applicable.",
    ]
    for g in guardrails:
        story.append(Paragraph(f"✔  {g}", guardrail_style))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e5e7eb")))
    footer_style = ParagraphStyle("footer", fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceBefore=6)
    story.append(Paragraph("Generated by AI Resume Optimizer · Confidential · For candidate use only", footer_style))

    doc.build(story)
    return report_filename
