import time
import uuid
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional

router = APIRouter()

ALLOWED_RESUME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
ALLOWED_TEMPLATE_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# In-memory session store (production would use Redis)
session_store: dict = {}


def validate_file(file: UploadFile, allowed_types: set, label: str):
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must be PDF or DOCX. Got: {file.content_type}",
        )


@router.post("/", summary="Upload resume, JD, and template files")
async def upload_files(
    resume: UploadFile = File(..., description="Candidate's resume (PDF or DOCX)"),
    jd: UploadFile = File(..., description="Job description (PDF, DOCX, or TXT)"),
    template: Optional[UploadFile] = File(None, description="Resume template DOCX (optional if using pre-built)"),
    template_choice: Optional[str] = Form(None, description="Pre-built template name: modern | classic | minimal"),
):
    # Validate resume
    validate_file(resume, ALLOWED_RESUME_TYPES, "Resume")

    # Validate JD (also allow plain text)
    jd_allowed = ALLOWED_RESUME_TYPES | {"text/plain"}
    validate_file(jd, jd_allowed, "Job Description")

    # template and template_choice are both optional —
    # if neither is provided the optimizer uses "Keep My Format" mode.
    if template:
        validate_file(template, ALLOWED_TEMPLATE_TYPES, "Template")

    # Read file bytes
    resume_bytes = await resume.read()
    jd_bytes = await jd.read()
    template_bytes = await template.read() if template else None

    # Size checks
    for label, data in [("Resume", resume_bytes), ("JD", jd_bytes)]:
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"{label} exceeds 10MB limit.")

    # Create session
    session_id = str(uuid.uuid4())
    session_store[session_id] = {
        "resume_bytes": resume_bytes,
        "resume_filename": resume.filename,
        "resume_content_type": resume.content_type,
        "jd_bytes": jd_bytes,
        "jd_filename": jd.filename,
        "jd_content_type": jd.content_type,
        "template_bytes": template_bytes,
        "template_filename": template.filename if template else None,
        "template_choice": template_choice,
        "status": "uploaded",
        "_created_at": time.time(),
    }

    return {
        "session_id": session_id,
        "message": "Files uploaded successfully. Call /analyze to run preflight analysis.",
        "files": {
            "resume": resume.filename,
            "jd": jd.filename,
            "template": template.filename if template else f"pre-built:{template_choice}",
        },
    }
