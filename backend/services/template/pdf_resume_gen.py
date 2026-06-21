"""
PDF Resume Generator — direct reportlab rendering.
Used for "Keep My Format" when the user uploaded a PDF resume.
Reconstructs the resume into a clean, professional PDF preserving the
original content structure (sections, bullets, skills, etc.).
No external binaries required.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

OUTPUT_DIR = "/tmp/resume-optimizer"

# ── Colours ──────────────────────────────────────────────────────────────────
DARK_BLUE  = HexColor("#1a56db")
LIGHT_BLUE = HexColor("#eef2ff")
DARK       = HexColor("#1e293b")
MID        = HexColor("#374151")
GRAY       = HexColor("#6b7280")
LIGHT_GRAY = HexColor("#f3f4f6")
RULE_BLUE  = HexColor("#c7d7f9")


# ── Style helpers ─────────────────────────────────────────────────────────────
def _styles():
    name_style   = ParagraphStyle("name",    fontSize=18, fontName="Helvetica-Bold",
                                  textColor=DARK_BLUE, spaceAfter=2)
    contact_style = ParagraphStyle("contact", fontSize=8,  fontName="Helvetica",
                                   textColor=HexColor("#555555"), spaceAfter=8)
    section_style = ParagraphStyle("section", fontSize=9.5, fontName="Helvetica-Bold",
                                   textColor=DARK_BLUE, spaceBefore=10, spaceAfter=3,
                                   textTransform="uppercase")
    body_style    = ParagraphStyle("body",    fontSize=9,   fontName="Helvetica",
                                   textColor=MID, leading=13, spaceAfter=4)
    bullet_style  = ParagraphStyle("bullet",  fontSize=8.5, fontName="Helvetica",
                                   textColor=MID, leading=12, spaceAfter=2,
                                   leftIndent=10, bulletIndent=3)
    bold_style    = ParagraphStyle("bold",    fontSize=9.5, fontName="Helvetica-Bold",
                                   textColor=DARK, spaceAfter=1)
    sub_style     = ParagraphStyle("sub",     fontSize=8.5, fontName="Helvetica",
                                   textColor=HexColor("#1a56db"), spaceAfter=1)
    small_style   = ParagraphStyle("small",   fontSize=8,   fontName="Helvetica",
                                   textColor=GRAY, spaceAfter=2)
    return {
        "name": name_style, "contact": contact_style, "section": section_style,
        "body": body_style, "bullet": bullet_style, "bold": bold_style,
        "sub": sub_style, "small": small_style,
    }


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _section_header(title: str, s: dict, story: list):
    story.append(Spacer(1, 4))
    story.append(Paragraph(title.upper(), s["section"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE_BLUE, spaceAfter=4))


def generate_pdf_resume(
    resume_data,          # dict or Pydantic model (rewritten resume)
    session_id: str,
) -> dict[str, str]:
    """
    Generate a clean professional PDF resume from parsed/rewritten resume data.
    Returns {"docx": None, "pdf": "optimized_resume.pdf"}.
    """
    out_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)

    pdf_filename = "optimized_resume.pdf"
    pdf_path = os.path.join(out_dir, pdf_filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    s = _styles()
    story = []

    # Normalise input
    if not isinstance(resume_data, dict):
        resume_data = _to_dict(resume_data)

    pi_raw = resume_data.get("personal_info", {}) or {}
    pi = _to_dict(pi_raw)

    def _items(key):
        return [_to_dict(i) if not isinstance(i, dict) else i
                for i in (resume_data.get(key) or [])]

    experience     = _items("experience")
    education      = _items("education")
    projects       = _items("projects")
    certifications = _items("certifications")
    skills         = resume_data.get("skills") or []
    tech_stack     = resume_data.get("tech_stack") or []
    all_skills     = list(dict.fromkeys(skills + tech_stack))  # deduplicated
    summary        = resume_data.get("summary", "") or ""

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph(pi.get("full_name", ""), s["name"]))

    # Headline / title line (e.g. "Senior Data Engineer | Microsoft Fabric Architect")
    headline = pi.get("headline") or ""
    if headline:
        headline_style = ParagraphStyle(
            "headline", fontSize=9, fontName="Helvetica",
            textColor=HexColor("#374151"), spaceAfter=3, alignment=1,  # centred
        )
        story.append(Paragraph(headline, headline_style))

    contact_parts = [p for p in [
        pi.get("email"),
        pi.get("phone"),
        pi.get("location"),
        pi.get("linkedin"),
        pi.get("github"),
    ] if p]
    if contact_parts:
        story.append(Paragraph("  |  ".join(contact_parts), s["contact"]))

    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK_BLUE, spaceAfter=6))

    # ── Summary ─────────────────────────────────────────────────────────────
    if summary:
        _section_header("Professional Summary", s, story)
        story.append(Paragraph(summary, s["body"]))

    # ── Skills ──────────────────────────────────────────────────────────────
    if all_skills:
        _section_header("Core Skills", s, story)
        # Render skills as a wrapped paragraph with separators — no flexbox needed
        skills_text = "  ·  ".join(all_skills[:30])
        skill_style = ParagraphStyle("skillrow", fontSize=8.5, fontName="Helvetica",
                                     textColor=MID, leading=13, spaceAfter=4)
        story.append(Paragraph(skills_text, skill_style))

    # ── Experience ──────────────────────────────────────────────────────────
    if experience:
        _section_header("Professional Experience", s, story)
        for exp in experience:
            title   = exp.get("title", "")
            company = exp.get("company", "")
            loc     = exp.get("location", "")
            start   = exp.get("start_date", "")
            end     = exp.get("end_date", "")
            dates   = f"{start} – {end}" if end else start
            bullets = exp.get("bullets") or []

            # Title + dates on same row via table
            title_para = Paragraph(f"<b>{title}</b>  <font color='#1a56db'>{company}</font>", s["body"])
            dates_para = Paragraph(dates, ParagraphStyle("dr", fontSize=8, fontName="Helvetica",
                                                          textColor=GRAY, alignment=TA_RIGHT))
            row_table = Table([[title_para, dates_para]],
                              colWidths=[130 * mm, 35 * mm])
            row_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
            ]))
            story.append(row_table)

            if loc:
                story.append(Paragraph(loc, s["small"]))

            for bullet in bullets:
                story.append(Paragraph(f"• {bullet}", s["bullet"]))

            story.append(Spacer(1, 4))

    # ── Projects ────────────────────────────────────────────────────────────
    if projects:
        _section_header("Projects", s, story)
        for proj in projects:
            name  = proj.get("name", "")
            desc  = proj.get("description", "")
            techs = proj.get("technologies") or []
            tech_str = ", ".join(techs) if techs else ""

            proj_line = f"<b>{name}</b>"
            if tech_str:
                proj_line += f"  <font color='#1a56db' size='8'>{tech_str}</font>"
            story.append(Paragraph(proj_line, s["body"]))
            if desc:
                story.append(Paragraph(desc, s["bullet"]))
            for bullet in (proj.get("bullets") or []):
                story.append(Paragraph(f"• {bullet}", s["bullet"]))
            story.append(Spacer(1, 3))

    # ── Education ───────────────────────────────────────────────────────────
    if education:
        _section_header("Education", s, story)
        for edu in education:
            degree = edu.get("degree", "")
            inst   = edu.get("institution", "")
            loc    = edu.get("location", "")
            year   = edu.get("year", "") or ""
            gpa    = edu.get("gpa", "") or ""

            inst_loc = inst
            if loc:
                inst_loc += f", {loc}"

            deg_para  = Paragraph(f"<b>{degree}</b>  <font color='#1a56db'>{inst_loc}</font>", s["body"])
            year_para = Paragraph(year, ParagraphStyle("yr", fontSize=8, fontName="Helvetica",
                                                        textColor=GRAY, alignment=TA_RIGHT))
            edu_table = Table([[deg_para, year_para]],
                              colWidths=[130 * mm, 35 * mm])
            edu_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
            ]))
            story.append(edu_table)
            if gpa:
                story.append(Paragraph(f"GPA: {gpa}", s["small"]))
            story.append(Spacer(1, 3))

    # ── Certifications ───────────────────────────────────────────────────────
    if certifications:
        _section_header("Certifications", s, story)
        for cert in certifications:
            name   = cert.get("name", "")
            issuer = cert.get("issuer", "") or ""
            year   = cert.get("year", "") or ""
            line   = name
            if issuer:
                line += f" — {issuer}"
            if year:
                line += f" ({year})"
            story.append(Paragraph(f"• {line}", s["bullet"]))

    # ── Languages ────────────────────────────────────────────────────────────
    languages = resume_data.get("languages") or []
    if languages:
        _section_header("Languages", s, story)
        story.append(Paragraph("  ·  ".join(languages), s["body"]))

    doc.build(story)
    return {"docx": None, "pdf": pdf_filename}
