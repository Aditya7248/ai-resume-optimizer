import asyncio
import logging
import shutil
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("xhtml2pdf").setLevel(logging.WARNING)
logging.getLogger("xhtml2pdf.document").setLevel(logging.WARNING)
logging.getLogger("xhtml2pdf.tables").setLevel(logging.WARNING)
logging.getLogger("xhtml2pdf.tags").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("fontTools").setLevel(logging.WARNING)

log = logging.getLogger("main")

from routers import upload, analyze, optimize, download

SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 hours
TMP_DIR = "/tmp/resume-optimizer"


async def _session_cleanup_loop():
    """Background task: evict sessions older than SESSION_TTL_SECONDS every hour."""
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        expired = [
            sid for sid, data in list(upload.session_store.items())
            if now - data.get("_created_at", now) > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            upload.session_store.pop(sid, None)
            # Remove the session's /tmp directory
            session_dir = os.path.join(TMP_DIR, sid)
            if os.path.isdir(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)
        if expired:
            log.info("[cleanup] Evicted %d expired sessions", len(expired))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 AI Resume Optimizer API starting on http://127.0.0.1:8000")
    log.info("   Docs: http://127.0.0.1:8000/docs")
    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    yield
    cleanup_task.cancel()
    log.info("⏹  API shutting down")


app = FastAPI(
    title="AI Resume Optimizer & Template Generator",
    description="""
    An intelligent API that accepts a candidate's resume, a target Job Description,
    and a resume template — then rewrites and tailors the resume content to maximise
    ATS compatibility, preserving the exact visual design of the uploaded template.

    ## Flow
    1. **POST /upload** — Upload resume, JD, and template files
    2. **POST /analyze** — Run preflight analysis (flags, ATS score, skill gaps)
    3. **POST /optimize** — Run AI optimization with user's confirmed choices
    4. **GET /download/{session_id}** — Download optimized DOCX/PDF + report
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request/response logger middleware ────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info(
        "  %s %s → %d  (%.0f ms)",
        request.method, request.url.path, response.status_code, elapsed,
    )
    return response


# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
        # Railway production frontend
        "https://ai-resume-optimizer-production-9629.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload.router,   prefix="/upload",   tags=["Upload"])
app.include_router(analyze.router,  prefix="/analyze",  tags=["Analyze"])
app.include_router(optimize.router, prefix="/optimize", tags=["Optimize"])
app.include_router(download.router, prefix="/download", tags=["Download"])


@app.get("/", tags=["Health"])
async def root():
    return {"service": "AI Resume Optimizer", "version": "1.0.0", "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
