import io
import re
from typing import Optional

import pdfplumber
from docx import Document

from models.jd import ParsedJD


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_experience_requirement(text: str):
    """Extract min/max years from JD text."""
    # Patterns: "5+ years", "3-5 years", "minimum 7 years", "5 to 8 years"
    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*years?", text, re.IGNORECASE)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    min_match = re.search(r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)", text, re.IGNORECASE)
    if min_match:
        val = float(min_match.group(1))
        return val, val + 3  # assume range

    minimum_match = re.search(r"(?:minimum|min\.?|at least)\s*(\d+)\s*years?", text, re.IGNORECASE)
    if minimum_match:
        val = float(minimum_match.group(1))
        return val, val + 3

    return None, None


def parse_jd(file_bytes: bytes, content_type: str, filename: str) -> ParsedJD:
    """
    Extracts raw text from JD file.
    AI-based deep keyword/skill extraction is done in ai_service.py.
    This layer handles file reading and basic pattern matching.
    """
    if content_type == "text/plain":
        raw_text = file_bytes.decode("utf-8", errors="ignore")
    elif "pdf" in content_type.lower():
        raw_text = extract_text_from_pdf(file_bytes)
    else:
        raw_text = extract_text_from_docx(file_bytes)

    if not raw_text or len(raw_text.strip()) < 30:
        raise ValueError("Could not extract text from Job Description.")

    # Basic experience extraction
    exp_min, exp_max = extract_experience_requirement(raw_text)

    # Extract first meaningful line as title heuristic
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    title_candidates = [l for l in lines[:5] if len(l) < 80]
    job_title = title_candidates[0] if title_candidates else "Unknown Position"

    return ParsedJD(
        job_title=job_title,
        required_experience_min=exp_min,
        required_experience_max=exp_max,
        raw_text=raw_text,
    )
