import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from routers.upload import session_store

router = APIRouter()

OUTPUT_DIR = "/tmp/resume-optimizer"


def _download_name(original_filename: str, suffix: str, ext: str) -> str:
    """Build a clean download filename from the original resume filename.

    e.g. "Aditya_Tiwari_Resume.pdf" + "_optimized" + "pdf"
         → "Aditya_Tiwari_Resume_optimized.pdf"
    """
    base = re.sub(r'\.[^/.]+$', '', original_filename or '')     # strip extension
    safe = re.sub(r'[^\w\-. ]', '', base)                        # remove special chars
    safe = re.sub(r'\s+', '_', safe).strip('_') or 'resume'      # spaces → underscores
    return f"{safe}{suffix}.{ext}"


@router.get("/{session_id}/docx", summary="Download optimized DOCX/HTML resume")
async def download_docx(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.get("status") != "optimized":
        raise HTTPException(status_code=400, detail="Resume not yet optimized.")

    result = session["optimization_result"]
    if not result.docx_filename:
        raise HTTPException(status_code=404, detail="DOCX not available — download the PDF instead.")

    filepath = os.path.join(OUTPUT_DIR, session_id, result.docx_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Output file not found.")

    is_html = result.docx_filename.endswith(".html")
    media_type = (
        "text/html"
        if is_html
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    ext = "html" if is_html else "docx"
    download_filename = _download_name(session.get("resume_filename", ""), "_optimized", ext)

    return FileResponse(path=filepath, media_type=media_type, filename=download_filename)


@router.get("/{session_id}/pdf", summary="Download optimized PDF resume")
async def download_pdf(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.get("status") != "optimized":
        raise HTTPException(status_code=400, detail="Resume not yet optimized.")

    result = session["optimization_result"]
    if not result.pdf_filename:
        raise HTTPException(status_code=404, detail="PDF not available for this session.")

    filepath = os.path.join(OUTPUT_DIR, session_id, result.pdf_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF file not found.")

    download_filename = _download_name(session.get("resume_filename", ""), "_optimized", "pdf")

    return FileResponse(path=filepath, media_type="application/pdf", filename=download_filename)


@router.get("/{session_id}/report", summary="Download optimization report")
async def download_report(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.get("status") != "optimized":
        raise HTTPException(status_code=400, detail="Resume not yet optimized.")

    result = session["optimization_result"]
    filepath = os.path.join(OUTPUT_DIR, session_id, result.report_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report file not found.")

    download_filename = _download_name(session.get("resume_filename", ""), "_optimization_report", "pdf")

    return FileResponse(path=filepath, media_type="application/pdf", filename=download_filename)


@router.get("/{session_id}/status", summary="Check session optimization status")
async def get_status(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "session_id": session_id,
        "status": session.get("status"),
        "files": {
            "resume": session.get("resume_filename"),
            "jd": session.get("jd_filename"),
            "template": session.get("template_filename") or f"pre-built:{session.get('template_choice')}",
        },
    }
