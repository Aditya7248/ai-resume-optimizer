import asyncio
import logging
import time
import traceback
from fastapi import APIRouter, HTTPException

from routers.upload import session_store
from services.ai.ai_service import rewrite_resume, verify_no_hallucination, compute_match_score
from services.template.pdf_inplace_engine import MIN_MATCH_RATE
from services.ats.ats_scorer import compute_ats_score_from_text
from services.template.docx_engine import inject_into_docx, inject_into_resume_docx
from services.template.html_engine import render_prebuilt_template
from services.template.pdf_inplace_engine import inject_into_pdf_inplace
from services.template.pdf_resume_gen import generate_pdf_resume
from services.report.report_gen import generate_report
from models.optimization import UserConfirmation, OptimizationResult
from models.resume import ParsedResume

router = APIRouter()
log = logging.getLogger("routers.optimize")

# Per-session locks prevent concurrent optimize calls overwriting each other
_session_locks: dict[str, asyncio.Lock] = {}


def _enrich_for_reportlab(verified_resume: dict, original_parsed: "ParsedResume") -> dict:
    """
    When falling back to the ReportLab generator, enrich the rewritten resume dict
    with sections that were NOT included in the slim rewrite prompt:
      - certifications  (stripped from prompt to save tokens)
      - languages       (stripped from prompt to save tokens)
      - headline/title  (personal_info field not in AI schema)
    This ensures the ReportLab PDF contains ALL original sections.
    """
    orig = original_parsed.model_dump()
    enriched = dict(verified_resume)

    # Restore certifications and languages from original if rewrite omitted them
    if not enriched.get("certifications") and orig.get("certifications"):
        enriched["certifications"] = orig["certifications"]
    if not enriched.get("languages") and orig.get("languages"):
        enriched["languages"] = orig["languages"]

    # Carry through any personal_info fields that rewrite may have blanked
    orig_pi = orig.get("personal_info") or {}
    enriched_pi = (enriched.get("personal_info") or {}).copy()
    for field in ("full_name", "email", "phone", "location", "linkedin", "github"):
        if not enriched_pi.get(field) and orig_pi.get(field):
            enriched_pi[field] = orig_pi[field]
    enriched["personal_info"] = enriched_pi

    return enriched


@router.post("/", response_model=OptimizationResult, summary="Run AI optimization with user-confirmed choices")
async def optimize(confirmation: UserConfirmation):
    session = session_store.get(confirmation.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.get("status") not in ("analyzed", "optimized"):
        raise HTTPException(status_code=400, detail="Run /analyze first before optimizing.")

    # Acquire per-session lock — reject a second concurrent optimize for the same session
    lock = _session_locks.setdefault(confirmation.session_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Optimization already in progress for this session. Please wait.",
        )
    await lock.acquire()

    parsed_resume = session.get("parsed_resume")
    parsed_jd = session.get("parsed_jd")
    analysis_result = session.get("analysis_result")

    if not parsed_resume or not parsed_jd:
        lock.release()
        raise HTTPException(status_code=400, detail="Parsed data missing. Re-run /analyze.")

    t0 = time.perf_counter()
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("[optimize] START  session=%s", confirmation.session_id[:8])
    log.info(
        "[optimize] Choices: summary=%s, bullets=%s, reorder=%s, skills_add=%s, template=%s",
        confirmation.rewrite_summary,
        confirmation.rewrite_bullets,
        confirmation.reorder_sections,
        confirmation.skills_to_add,
        confirmation.template_choice or "keep-my-format",
    )

    try:
        # 1. AI rewrites resume
        t1 = time.perf_counter()
        log.info("[optimize] Step 1 — AI rewriting resume...")
        rewritten_resume = await rewrite_resume(
            parsed_resume=parsed_resume,
            parsed_jd=parsed_jd,
            confirmation=confirmation,
        )
        log.info("[optimize] Step 1 done (%.1fs) — rewritten sections present", time.perf_counter() - t1)
    except Exception as e:
        lock.release()
        traceback.print_exc()
        log.error("[optimize] FAILED at step 1: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

    try:

        # 2. Hallucination guard, then ATS post-score on verified content
        t2 = time.perf_counter()
        log.info("[optimize] Step 2 — hallucination guard + ATS post-score...")
        verified_resume = await verify_no_hallucination(
            original=parsed_resume,
            rewritten=rewritten_resume,
            skills_to_add=confirmation.skills_to_add or [],
        )
        loop = asyncio.get_running_loop()
        ats_after = await loop.run_in_executor(
            None, compute_ats_score_from_text, verified_resume, parsed_jd, parsed_resume,
        )
        log.info(
            "[optimize] Step 2 done (%.1fs) — ATS after=%s/100 (+%s vs before=%s)",
            time.perf_counter() - t2,
            ats_after.total,
            round(ats_after.total - analysis_result.ats_score_before.total, 1),
            analysis_result.ats_score_before.total,
        )

        # 3. Generate output document
        t3 = time.perf_counter()
        resume_ct = session.get("resume_content_type", "")
        is_docx = (
            "wordprocessingml" in resume_ct
            or session.get("resume_filename", "").endswith(".docx")
        )

        if confirmation.template_choice:
            log.info("[optimize] Step 3 — pre-built template: %s", confirmation.template_choice)
            # The rewrite prompt only carries full_name in personal_info to save tokens.
            # Merge all original contact fields back before rendering the template so
            # that email, phone, location, linkedin, github appear in the PDF.
            orig_pi = parsed_resume.model_dump().get("personal_info") or {}
            rewritten_pi = (verified_resume.get("personal_info") or {}).copy()
            for field in ("email", "phone", "location", "linkedin", "github", "portfolio", "headline"):
                if not rewritten_pi.get(field) and orig_pi.get(field):
                    rewritten_pi[field] = orig_pi[field]
            verified_resume_for_template = {**verified_resume, "personal_info": rewritten_pi}
            output_files = await render_prebuilt_template(
                template_name=confirmation.template_choice,
                resume_data=verified_resume_for_template,
                session_id=confirmation.session_id,
            )
        elif session.get("template_bytes"):
            log.info("[optimize] Step 3 — user-uploaded DOCX template")
            output_files = inject_into_docx(
                template_bytes=session["template_bytes"],
                resume_data=verified_resume,
                session_id=confirmation.session_id,
            )
        elif is_docx:
            log.info("[optimize] Step 3 — keep-my-format DOCX in-place edit")
            resume_bytes_docx = session.get("resume_bytes")
            if not resume_bytes_docx:
                log.warning("[optimize] resume_bytes freed (re-optimize) — falling back to reportlab")
                loop2 = asyncio.get_running_loop()
                output_files = await loop2.run_in_executor(
                    None, generate_pdf_resume,
                    _enrich_for_reportlab(verified_resume, parsed_resume),
                    confirmation.session_id,
                )
            else:
                output_files = inject_into_resume_docx(
                    resume_bytes=resume_bytes_docx,
                    original_resume=parsed_resume.model_dump(),
                    rewritten_resume=verified_resume,
                    session_id=confirmation.session_id,
                )
        else:
            log.info("[optimize] Step 3 — keep-my-format PDF in-place edit (PyMuPDF)")
            loop2 = asyncio.get_running_loop()
            resume_bytes_pdf = session.get("resume_bytes")
            if not resume_bytes_pdf:
                # Bytes were freed after a previous successful optimize — go straight to ReportLab
                log.warning("[optimize] resume_bytes freed (re-optimize) — skipping inplace edit, using reportlab")
                output_files = await loop2.run_in_executor(
                    None, generate_pdf_resume,
                    _enrich_for_reportlab(verified_resume, parsed_resume),
                    confirmation.session_id,
                )
            else:
                try:
                    output_files = await loop2.run_in_executor(
                        None,
                        lambda: inject_into_pdf_inplace(
                            resume_bytes_pdf,
                            parsed_resume.model_dump(),
                            verified_resume,
                            confirmation.session_id,
                            confirmation.skills_to_add or [],
                        ),
                    )
                    match_rate = output_files.get("match_rate", 1.0)
                    if match_rate < MIN_MATCH_RATE:
                        log.warning(
                            "[optimize] PDF in-place match rate %.0f%% < %.0f%% — falling back to reportlab",
                            match_rate * 100, MIN_MATCH_RATE * 100,
                        )
                        output_files = await loop2.run_in_executor(
                            None, generate_pdf_resume,
                            _enrich_for_reportlab(verified_resume, parsed_resume),
                            confirmation.session_id,
                        )
                except Exception as pdf_err:
                    traceback.print_exc()
                    log.warning("[optimize] PDF in-place failed (%s) — falling back to reportlab", pdf_err)
                    output_files = await loop2.run_in_executor(
                        None, generate_pdf_resume,
                        _enrich_for_reportlab(verified_resume, parsed_resume),
                        confirmation.session_id,
                    )

        log.info("[optimize] Step 3 done (%.1fs) — output: %s", time.perf_counter() - t3, output_files)

        # ── Compute match score BEFORE generating the report (report needs it) ──
        skills_added = confirmation.skills_to_add

        # Reflect only sections that actually changed after the hallucination guard
        orig_dump = parsed_resume.model_dump()
        sections_rewritten = []
        if confirmation.rewrite_summary and (
            verified_resume.get("summary") != orig_dump.get("summary")
        ):
            sections_rewritten.append("Summary")
        if confirmation.rewrite_bullets:
            orig_bullets = [b for e in (orig_dump.get("experience") or []) for b in (e.get("bullets") or [])]
            new_bullets = [b for e in (verified_resume.get("experience") or []) for b in (e.get("bullets") or [])]
            if orig_bullets != new_bullets:
                sections_rewritten.append("Experience")
        if confirmation.reorder_sections:
            sections_rewritten.append("Section Order")

        known_gaps = [f.title for f in analysis_result.flags if f.category.value in confirmation.flags_acknowledged]

        # Compute real match score on verified (post-guard) resume.
        # Augment the scoring profile with:
        #  a) user-approved skills_to_add (injected into the PDF)
        #  b) JD hard keywords that genuinely appear in the verified resume text
        score_base = {
            **parsed_resume.model_dump(),
            **{k: v for k, v in verified_resume.items() if k in ParsedResume.model_fields},
        }
        all_additions = list(confirmation.skills_to_add or [])
        verified_text = " ".join([
            verified_resume.get("summary") or "",
            " ".join(verified_resume.get("skills") or []),
            " ".join(verified_resume.get("tech_stack") or []),
            " ".join(
                b for exp in (verified_resume.get("experience") or [])
                for b in ((exp.get("bullets") or []) if isinstance(exp, dict) else [])
            ),
        ]).lower()
        for kw in (parsed_jd.hard_keywords or []):
            if kw.lower() in verified_text:
                all_additions.append(kw)
        current_skills = list(score_base.get("skills") or [])
        current_tech = list(score_base.get("tech_stack") or [])
        skills_lower = {s.lower() for s in current_skills}
        tech_lower = {s.lower() for s in current_tech}
        for s in all_additions:
            if s.lower() not in skills_lower:
                current_skills.append(s)
                skills_lower.add(s.lower())
            if s.lower() not in tech_lower:
                current_tech.append(s)
                tech_lower.add(s.lower())
        score_base["skills"] = current_skills
        score_base["tech_stack"] = current_tech
        verified_for_score = ParsedResume(**score_base)
        match_score_after_raw = await compute_match_score(verified_for_score, parsed_jd)
        match_score_after = max(match_score_after_raw, analysis_result.match_score)

        # 4. Generate optimization report (needs match_score_after computed above)
        t4 = time.perf_counter()
        log.info("[optimize] Step 4 — generating optimization report PDF...")
        report_path = generate_report(
            session_id=confirmation.session_id,
            original_resume=parsed_resume,
            rewritten_resume=verified_resume,
            jd=parsed_jd,
            ats_before=analysis_result.ats_score_before,
            ats_after=ats_after,
            match_before=analysis_result.match_score,
            confirmation=confirmation,
            match_after=match_score_after,
            keywords_injected=parsed_jd.hard_keywords[:15],
        )
        log.info("[optimize] Step 4 done (%.1fs) — report: %s", time.perf_counter() - t4, report_path)

        result = OptimizationResult(
            session_id=confirmation.session_id,
            ats_score_before=analysis_result.ats_score_before,
            ats_score_after=ats_after,
            match_score_before=analysis_result.match_score,
            match_score_after=match_score_after,
            skills_added=skills_added,
            keywords_injected=parsed_jd.hard_keywords[:10],
            sections_rewritten=sections_rewritten,
            known_gaps=known_gaps,
            suggestions=verified_resume.get("suggestions", []),
            docx_filename=output_files.get("docx", ""),
            pdf_filename=output_files.get("pdf"),
            report_filename=report_path,
        )

        session["optimization_result"] = result
        session["status"] = "optimized"
        # Free raw file bytes — no longer needed after PDF/DOCX output is written to disk
        session.pop("resume_bytes", None)
        session.pop("jd_bytes", None)
        session.pop("template_bytes", None)

        log.info(
            "[optimize] DONE (total %.1fs) — ATS %s→%s, match %.0f%%→%.0f%%",
            time.perf_counter() - t0,
            result.ats_score_before.total, result.ats_score_after.total,
            result.match_score_before, result.match_score_after,
        )
        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return result

    except Exception as e:
        traceback.print_exc()
        log.error("[optimize] FAILED: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
    finally:
        lock.release()
