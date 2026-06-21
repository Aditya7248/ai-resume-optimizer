"""
HTML Template Engine — for pre-built templates.
Uses Jinja2 for content injection → saves HTML → converts to PDF via xhtml2pdf.
Falls back to the ReportLab generator if xhtml2pdf fails.
xhtml2pdf is pure Python (no system binary required).
"""

import logging
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

OUTPUT_DIR = "/tmp/resume-optimizer"
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "../../templates/prebuilt")

log = logging.getLogger("html_engine")


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )


def _html_to_pdf(html_content: str, pdf_path: str) -> bool:
    """Convert HTML string to PDF using xhtml2pdf. Returns True on success.

    xhtml2pdf reports minor CSS warnings as non-zero result.err even when a
    valid PDF was produced, so we judge success solely by whether the output
    file exists and has real content (>500 bytes).
    """
    try:
        from xhtml2pdf import pisa  # type: ignore

        with open(pdf_path, "wb") as f:
            pisa.CreatePDF(html_content, dest=f)

        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500:
            return True

        log.warning("[html_engine] xhtml2pdf produced an empty/missing file")
        return False

    except Exception as e:
        log.warning("[html_engine] xhtml2pdf failed: %s", e)
        return False


async def render_prebuilt_template(
    template_name: str,
    resume_data: dict,
    session_id: str,
) -> dict[str, str]:
    """
    Render a pre-built HTML template with resume data → PDF.
    template_name: "modern" | "classic" | "minimal"
    Returns {"docx": html_filename, "pdf": pdf_filename or None}
    """
    valid_templates = ("modern", "classic", "minimal")
    if template_name not in valid_templates:
        raise ValueError(f"Unknown template: {template_name}. Choose from {valid_templates}")

    out_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)

    env = _get_jinja_env()
    template = env.get_template(f"{template_name}.html")

    # Build template context — normalise dicts/objects
    def _to_dict(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return obj if isinstance(obj, dict) else {}

    pi_raw = resume_data.get("personal_info", {})
    pi = _to_dict(pi_raw)

    def _list_of_dicts(key):
        items = resume_data.get(key, []) or []
        return [_to_dict(i) if not isinstance(i, dict) else i for i in items]

    context = {
        "full_name":      pi.get("full_name", ""),
        "email":          pi.get("email", ""),
        "phone":          pi.get("phone", ""),
        "location":       pi.get("location", ""),
        "linkedin":       pi.get("linkedin", ""),
        "github":         pi.get("github", ""),
        "summary":        resume_data.get("summary", ""),
        "skills":         resume_data.get("skills", []) or [],
        "tech_stack":     resume_data.get("tech_stack", []) or [],
        "experience":     _list_of_dicts("experience"),
        "education":      _list_of_dicts("education"),
        "projects":       _list_of_dicts("projects"),
        "certifications": _list_of_dicts("certifications"),
        "languages":      resume_data.get("languages", []) or [],
    }

    # Render HTML
    html_content = template.render(**context)
    html_path = os.path.join(out_dir, "resume.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Convert HTML → PDF via xhtml2pdf (pure Python, no system binary needed)
    pdf_filename = "optimized_resume.pdf"
    pdf_path = os.path.join(out_dir, pdf_filename)

    if _html_to_pdf(html_content, pdf_path):
        log.info("[html_engine] xhtml2pdf succeeded → %s", pdf_filename)
        return {"docx": "resume.html", "pdf": pdf_filename}

    # xhtml2pdf failed — fall back to the ReportLab generator which is always reliable
    log.warning("[html_engine] xhtml2pdf failed — falling back to ReportLab PDF generator")
    try:
        from services.template.pdf_resume_gen import generate_pdf_resume  # type: ignore
        out = generate_pdf_resume(resume_data, session_id)
        rl_pdf = out.get("pdf")
        if rl_pdf:
            log.info("[html_engine] ReportLab fallback succeeded → %s", rl_pdf)
            return {"docx": "resume.html", "pdf": rl_pdf}
    except Exception as rl_err:
        log.warning("[html_engine] ReportLab fallback also failed: %s", rl_err)

    # Last resort: serve the HTML so the user can at least open it
    log.warning("[html_engine] Both PDF paths failed — serving HTML only")
    return {"docx": "resume.html", "pdf": None}
