import asyncio
import logging
import time
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.upload import session_store
from services.parser.resume_parser import parse_resume
from services.parser.jd_parser import parse_jd
from services.ats.ats_scorer import compute_ats_score
from services.validator.preflight import run_preflight
from services.ai.ai_service import (
    analyze_jd, enrich_resume,
    compute_match_score, extract_skill_breakdown,
)
from models.optimization import AnalysisResult

router = APIRouter()
log = logging.getLogger("routers.analyze")


class AnalyzeRequest(BaseModel):
    session_id: str


@router.post("/", response_model=AnalysisResult, summary="Run preflight analysis on uploaded files")
async def analyze(request: AnalyzeRequest):
    session = session_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload files first.")

    if session.get("status") == "analyzed":
        log.info("[analyze] Cache hit — returning existing result for %s", request.session_id[:8])
        return session["analysis_result"]

    t0 = time.perf_counter()
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("[analyze] START  session=%s", request.session_id[:8])
    log.info(
        "[analyze] Files: resume=%s (%s), jd=%s (%s)",
        session.get("resume_filename"), session.get("resume_content_type"),
        session.get("jd_filename"), session.get("jd_content_type"),
    )

    try:
        # ── Step 1: Parse resume + JD (CPU-bound, parallel) ──────────────────
        t1 = time.perf_counter()
        log.info("[analyze] Step 1 — parsing resume + JD in parallel...")
        loop = asyncio.get_running_loop()
        parsed_resume, parsed_jd = await asyncio.gather(
            loop.run_in_executor(None, parse_resume,
                session["resume_bytes"],
                session["resume_content_type"],
                session["resume_filename"],
            ),
            loop.run_in_executor(None, parse_jd,
                session["jd_bytes"],
                session["jd_content_type"],
                session["jd_filename"],
            ),
        )
        log.info(
            "[analyze] Step 1 done (%.1fs) — resume raw_text=%d chars, jd raw_text=%d chars",
            time.perf_counter() - t1,
            len(parsed_resume.raw_text or ""),
            len(parsed_jd.raw_text or ""),
        )

        # ── Step 2: AI enrichment — resume + JD in parallel ──────────────────
        t2 = time.perf_counter()
        log.info("[analyze] Step 2 — AI enriching resume + analyzing JD in parallel...")
        enriched_resume, analyzed_jd = await asyncio.gather(
            enrich_resume(parsed_resume),
            analyze_jd(parsed_jd),
        )
        log.info(
            "[analyze] Step 2 done (%.1fs) — skills=%s, tech_stack=%s, domain=%s | jd_title=%s, required_skills=%d",
            time.perf_counter() - t2,
            enriched_resume.skills[:5],
            enriched_resume.tech_stack[:5],
            enriched_resume.primary_domain,
            analyzed_jd.job_title,
            len(analyzed_jd.required_skills),
        )

        # ── Step 3: Scoring (all parallel, depends on step 2) ─────────────────
        t3 = time.perf_counter()
        log.info("[analyze] Step 3 — computing ATS score, match score, skill breakdown...")
        loop = asyncio.get_running_loop()
        ats_before, match_score, skills = await asyncio.gather(
            loop.run_in_executor(None, compute_ats_score,
                session["resume_bytes"],
                session["resume_content_type"],
                enriched_resume,
                analyzed_jd,
            ),
            compute_match_score(enriched_resume, analyzed_jd),
            extract_skill_breakdown(enriched_resume, analyzed_jd),
        )
        log.info(
            "[analyze] Step 3 done (%.1fs) — ATS=%s/100, match=%.0f%%, skills=%d items",
            time.perf_counter() - t3,
            ats_before.total,
            match_score,
            len(skills),
        )
        log.info(
            "[analyze] ATS breakdown: keyword_match=%.1f, section=%.1f, format=%.1f, placement=%.1f, dates=%.1f, health=%.1f",
            ats_before.keyword_match, ats_before.section_completeness,
            ats_before.format_parsability, ats_before.keyword_placement,
            ats_before.date_consistency, ats_before.file_health,
        )

        # ── Step 4: Preflight flags ────────────────────────────────────────────
        flags = run_preflight(enriched_resume, analyzed_jd)
        log.info("[analyze] Preflight flags: %s", [f.category.value for f in flags])

        result = AnalysisResult(
            session_id=request.session_id,
            match_score=match_score,
            ats_score_before=ats_before,
            flags=flags,
            skills=skills,
            experience_candidate=enriched_resume.total_years_experience,
            experience_required_min=analyzed_jd.required_experience_min,
            experience_required_max=analyzed_jd.required_experience_max,
            domain_candidate=enriched_resume.primary_domain,
            domain_jd=analyzed_jd.primary_domain,
            missing_certifications=analyzed_jd.certifications_required,
        )

        session["parsed_resume"] = enriched_resume
        session["parsed_jd"] = analyzed_jd
        session["analysis_result"] = result
        session["status"] = "analyzed"

        log.info(
            "[analyze] DONE (total %.1fs) — match=%.0f%%, ATS=%s/100",
            time.perf_counter() - t0, match_score, ats_before.total,
        )
        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return result

    except Exception as e:
        traceback.print_exc()
        log.error("[analyze] FAILED: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
