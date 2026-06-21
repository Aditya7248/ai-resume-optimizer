import asyncio
import copy
import json
import logging
import time
import os
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from models.resume import ParsedResume
from models.jd import ParsedJD
from models.optimization import SkillItem, SkillStatus, ATSScoreBreakdown, UserConfirmation
from services.ai.prompts import (
    RESUME_EXTRACTION_SYSTEM, RESUME_EXTRACTION_USER,
    RESUME_EXTRACTION_A_USER, RESUME_EXTRACTION_B_USER,
    RESUME_EXTRACTION_B1_USER, RESUME_EXTRACTION_B2_USER,
    JD_ANALYSIS_SYSTEM, JD_ANALYSIS_USER,
    MATCH_SCORE_SYSTEM, MATCH_SCORE_USER,
    SKILL_BREAKDOWN_SYSTEM, SKILL_BREAKDOWN_USER,
    REWRITE_SYSTEM, REWRITE_USER,
    HALLUCINATION_CHECK_SYSTEM, HALLUCINATION_CHECK_USER,
)

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Two-tier model strategy:
#   MODEL      — gpt-4o for creative/quality tasks (rewriting)
#   MODEL_FAST — gpt-4o-mini for structured extraction tasks (parse, score, guard)
#   This cuts analyze time from ~35s → ~8s and optimize from ~33s → ~22s
MODEL      = "gpt-4o"
MODEL_FAST = "gpt-4o-mini"

log = logging.getLogger("ai_service")


async def _chat(
    system: str,
    user: str,
    temperature: float = 0.3,
    label: str = "call",
    model: str | None = None,
) -> dict:
    """
    Core OpenAI call with JSON mode, exponential-backoff retry, and rate-limit handling.
    Pass `model` explicitly to override the default; defaults to MODEL (gpt-4o).
    """
    m = model or MODEL
    t0 = time.perf_counter()

    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=m,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)
            log.info(
                "[ai] %-28s  %.1fs  tokens=%s/%s  model=%s",
                label,
                time.perf_counter() - t0,
                response.usage.prompt_tokens if response.usage else "?",
                response.usage.completion_tokens if response.usage else "?",
                m,
            )
            return result

        except json.JSONDecodeError:
            if attempt == 2:
                raise ValueError(f"AI ({m}) returned invalid JSON after 3 attempts.")
            wait = 2 ** attempt
            log.warning("[ai] JSON decode error on attempt %d — retrying in %ds", attempt + 1, wait)
            await asyncio.sleep(wait)

        except RateLimitError:
            wait = 5 * (2 ** attempt)   # 5s, 10s, 20s
            if attempt == 2:
                raise RuntimeError(f"OpenAI rate limit exceeded for {m} after 3 retries.")
            log.warning("[ai] Rate limit hit on attempt %d — waiting %ds", attempt + 1, wait)
            await asyncio.sleep(wait)

        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"OpenAI API error ({m}): {str(e)}")
            wait = 2 ** attempt
            log.warning("[ai] API error on attempt %d (%s) — retrying in %ds", attempt + 1, str(e)[:60], wait)
            await asyncio.sleep(wait)


async def enrich_resume(parsed_resume: ParsedResume) -> ParsedResume:
    """
    Use AI (gpt-4o-mini) to deeply extract structured resume data from raw text.
    Runs TWO parallel calls to halve latency (~13s instead of ~27s):
      - Call A: personal_info, summary, skills, tech_stack, domain, years
      - Call B: experience[], education[], projects[], certifications[]
    Both calls receive the full raw_text so output quality is identical to a
    single-call extraction.
    """
    raw_text = parsed_resume.raw_text or ""
    if not raw_text:
        return parsed_resume

    truncated = raw_text[:12000]
    prompt_a  = RESUME_EXTRACTION_A_USER.format(raw_text=truncated)   # skills/info
    prompt_b1 = RESUME_EXTRACTION_B1_USER.format(raw_text=truncated)  # experience only
    prompt_b2 = RESUME_EXTRACTION_B2_USER.format(raw_text=truncated)  # edu/projects/certs

    data_a, data_b1, data_b2 = await asyncio.gather(
        _chat(RESUME_EXTRACTION_SYSTEM, prompt_a,
              temperature=0.1, label="enrich_resume_a", model=MODEL_FAST),
        _chat(RESUME_EXTRACTION_SYSTEM, prompt_b1,
              temperature=0.1, label="enrich_resume_b1", model=MODEL_FAST),
        _chat(RESUME_EXTRACTION_SYSTEM, prompt_b2,
              temperature=0.1, label="enrich_resume_b2", model=MODEL_FAST),
    )

    # Merge all three responses — treat as if they came from one call
    data = {**data_a, **data_b1, **data_b2}

    from models.resume import (
        PersonalInfo, ExperienceEntry, EducationEntry,
        ProjectEntry, CertificationEntry,
    )

    pi = data.get("personal_info", {})
    personal_info = PersonalInfo(
        full_name=pi.get("full_name") or parsed_resume.personal_info.full_name,
        headline=pi.get("headline") or parsed_resume.personal_info.headline,
        email=pi.get("email") or parsed_resume.personal_info.email,
        phone=pi.get("phone") or parsed_resume.personal_info.phone,
        location=pi.get("location"),
        linkedin=pi.get("linkedin") or parsed_resume.personal_info.linkedin,
        github=pi.get("github") or parsed_resume.personal_info.github,
        portfolio=pi.get("portfolio"),
    )

    # Safe Pydantic construction — skip entries with missing required fields
    # rather than crashing the whole analysis on one malformed AI response entry.
    experience = []
    for exp in (data.get("experience") or []):
        try:
            experience.append(ExperienceEntry(**exp))
        except Exception as exc:
            log.warning("[enrich] Skipping malformed experience entry: %s — %s", str(exp)[:80], exc)

    education = []
    for edu in (data.get("education") or []):
        try:
            education.append(EducationEntry(**edu))
        except Exception as exc:
            log.warning("[enrich] Skipping malformed education entry: %s — %s", str(edu)[:80], exc)

    projects = []
    for proj in (data.get("projects") or []):
        try:
            projects.append(ProjectEntry(**proj))
        except Exception as exc:
            log.warning("[enrich] Skipping malformed project entry: %s — %s", str(proj)[:80], exc)

    certifications = []
    for cert in (data.get("certifications") or []):
        try:
            certifications.append(CertificationEntry(**cert))
        except Exception as exc:
            log.warning("[enrich] Skipping malformed certification entry: %s — %s", str(cert)[:80], exc)

    return ParsedResume(
        personal_info=personal_info,
        summary=data.get("summary"),
        skills=data.get("skills") or [],
        experience=experience,
        education=education,
        projects=projects,
        certifications=certifications,
        languages=data.get("languages") or [],
        total_years_experience=_parse_float(data.get("total_years_experience")) or parsed_resume.total_years_experience,
        primary_domain=data.get("primary_domain"),
        tech_stack=data.get("tech_stack") or [],
        raw_text=parsed_resume.raw_text,
    )


import re as _re_ai

_VALID_SENIORITY = {"intern", "junior", "mid", "senior", "lead", "manager", "director"}

# Fuzzy mappings for common AI variants that don't match the enum exactly
_SENIORITY_ALIASES: dict[str, str] = {
    "entry": "junior",
    "entry-level": "junior",
    "entry level": "junior",
    "graduate": "junior",
    "associate": "junior",
    "intermediate": "mid",
    "experienced": "mid",
    "mid-level": "mid",
    "mid level": "mid",
    "principal": "lead",
    "staff": "lead",
    "tech lead": "lead",
    "team lead": "lead",
    "engineering manager": "manager",
    "engineering lead": "lead",
    "vp": "director",
    "vice president": "director",
    "head": "director",
    "c-level": "director",
}


def _parse_seniority(raw: str | None) -> str | None:
    """
    Robustly parse a seniority string from any AI output format.
    Handles: "mid|senior", "senior/lead", "mid-senior", "Senior Level",
             "mid to senior", compound values, aliases, and unknown strings.
    Always returns a valid SeniorityLevel value or None — never raises.
    """
    if not raw:
        return None
    s = raw.strip().lower()
    if s in _VALID_SENIORITY:
        return s
    if s in _SENIORITY_ALIASES:
        return _SENIORITY_ALIASES[s]
    tokens = [t.strip() for t in _re_ai.split(r"[|/\-,&\s]+", s) if t.strip()]
    for token in tokens:
        if token in _VALID_SENIORITY:
            return token
        if token in _SENIORITY_ALIASES:
            return _SENIORITY_ALIASES[token]
    for level in ("director", "manager", "lead", "senior", "mid", "junior", "intern"):
        if level in s:
            return level
    log.warning("[analyze_jd] Unrecognised seniority_level %r — defaulting to None", raw)
    return None


def _parse_float(raw, fallback: float | None = None) -> float | None:
    """
    Safely parse a float from any AI output format.
    Handles: 5.0, "5", "5+", "5-7", "5 years", "five", None, ""
    Returns the first numeric value found, or fallback.
    """
    if raw is None:
        return fallback
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return fallback
    # Find first numeric sequence (including decimals)
    m = _re_ai.search(r"\d+(?:\.\d+)?", s)
    if m:
        return float(m.group())
    return fallback


_VALID_SKILL_STATUSES = {"matched", "can_add", "partial", "missing"}
_SKILL_STATUS_ALIASES: dict[str, str] = {
    "can add": "can_add",
    "can-add": "can_add",
    "canadd": "can_add",
    "highlight": "can_add",
    "add": "can_add",
    "partially matched": "partial",
    "partially_matched": "partial",
    "partial match": "partial",
    "related": "partial",
    "similar": "partial",
    "match": "matched",
    "found": "matched",
    "not found": "missing",
    "not_found": "missing",
    "not detected": "missing",
    "absent": "missing",
    "unknown": "missing",
}


def _parse_skill_status(raw: str | None) -> str:
    """
    Robustly parse a SkillStatus from any AI output format.
    Always returns a valid status string — defaults to "missing" if unrecognised.
    """
    if not raw:
        return "missing"
    s = str(raw).strip().lower()
    if s in _VALID_SKILL_STATUSES:
        return s
    if s in _SKILL_STATUS_ALIASES:
        return _SKILL_STATUS_ALIASES[s]
    # Substring match
    for status in ("matched", "can_add", "partial", "missing"):
        if status.replace("_", "") in s.replace("_", "").replace(" ", ""):
            return status
    log.warning("[skill_breakdown] Unrecognised status %r — defaulting to 'missing'", raw)
    return "missing"


def _parse_bool(raw, default: bool = True) -> bool:
    """
    Robustly parse a boolean from any AI output format.
    Handles: True, False, "true", "false", "yes", "no", 0, 1, "True", etc.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return bool(raw)
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "yes", "1", "clean", "ok", "pass"):
            return True
        if s in ("false", "no", "0", "dirty", "fail"):
            return False
    return default


async def analyze_jd(parsed_jd: ParsedJD) -> ParsedJD:
    """Deep AI analysis of JD to extract skills, keywords, seniority. Uses gpt-4o-mini."""
    user_prompt = JD_ANALYSIS_USER.format(raw_text=parsed_jd.raw_text[:8000])
    data = await _chat(JD_ANALYSIS_SYSTEM, user_prompt, temperature=0.1, label="analyze_jd", model=MODEL_FAST)

    return ParsedJD(
        job_title=data.get("job_title", parsed_jd.job_title),
        company=data.get("company"),
        location=data.get("location"),
        work_mode=data.get("work_mode"),
        notice_period=data.get("notice_period"),
        required_experience_min=_parse_float(data.get("required_experience_min")) or parsed_jd.required_experience_min,
        required_experience_max=_parse_float(data.get("required_experience_max")) or parsed_jd.required_experience_max,
        seniority_level=_parse_seniority(data.get("seniority_level")),
        primary_domain=data.get("primary_domain"),
        industry=data.get("industry"),
        required_skills=data.get("required_skills", []),
        preferred_skills=data.get("preferred_skills", []),
        technologies=data.get("technologies", []),
        certifications_required=data.get("certifications_required", []),
        education_required=data.get("education_required"),
        hard_keywords=data.get("hard_keywords", []),
        soft_keywords=data.get("soft_keywords", []),
        responsibilities=data.get("responsibilities", []),
        raw_text=parsed_jd.raw_text,
    )


async def compute_match_score(resume: ParsedResume, jd: ParsedJD) -> float:
    """Compute semantic match % between resume and JD."""
    # Build a compact evidence snippet: summary + first 2 bullets from each experience entry
    evidence_parts: list[str] = []
    if resume.summary:
        evidence_parts.append(f"Summary: {resume.summary}")
    for exp in (resume.experience or [])[:5]:
        header = f"{exp.title} @ {exp.company}"
        bullets = (exp.bullets or [])[:2]
        if bullets:
            evidence_parts.append(f"{header}: " + "; ".join(bullets))
        else:
            evidence_parts.append(header)
    resume_text = "\n".join(evidence_parts) if evidence_parts else "No resume text available."

    user_prompt = MATCH_SCORE_USER.format(
        domain_candidate=resume.primary_domain or "Unknown",
        experience=resume.total_years_experience or 0,
        tech_stack=", ".join(resume.tech_stack[:20]),
        skills=", ".join(resume.skills[:30]),
        resume_text=resume_text,
        job_title=jd.job_title,
        domain_jd=jd.primary_domain or "Unknown",
        exp_min=jd.required_experience_min or 0,
        exp_max=jd.required_experience_max or 0,
        required_skills=", ".join(jd.required_skills[:20]),
        technologies=", ".join(jd.technologies[:20]),
    )
    # Use the full model for match scoring — gpt-4o-mini is too conservative
    # and significantly undersells candidate fit (35% vs realistic 65-75%).
    data = await _chat(MATCH_SCORE_SYSTEM, user_prompt, temperature=0.2, label="match_score", model=MODEL)
    return float(data.get("match_score", 50))


async def extract_skill_breakdown(resume: ParsedResume, jd: ParsedJD) -> list[SkillItem]:
    """Per-skill categorization: matched / can_add / partial / missing."""
    all_jd_skills = list(set(jd.required_skills + jd.technologies))[:40]

    user_prompt = SKILL_BREAKDOWN_USER.format(
        tech_stack=", ".join(resume.tech_stack[:30]),
        skills=", ".join(resume.skills[:30]),
        domain=resume.primary_domain or "Unknown",
        required_skills=", ".join(jd.required_skills[:25]),
        technologies=", ".join(jd.technologies[:25]),
    )
    data = await _chat(SKILL_BREAKDOWN_SYSTEM, user_prompt, temperature=0.1, label="skill_breakdown", model=MODEL_FAST)

    # Prompt asks for {"skills": [...]}, but handle bare list too
    raw = data.get("skills", data) if isinstance(data, dict) else data
    items = []
    for entry in (raw if isinstance(raw, list) else []):
        try:
            skill_name = (entry.get("skill") or "").strip()
            if not skill_name:
                continue
            items.append(SkillItem(
                skill=skill_name,
                status=SkillStatus(_parse_skill_status(entry.get("status"))),
                related_skill=entry.get("related_skill"),
            ))
        except Exception as exc:
            log.warning("[skill_breakdown] Skipping malformed skill entry: %s — %s", str(entry)[:80], exc)
    return items


async def rewrite_resume(
    parsed_resume: ParsedResume,
    parsed_jd: ParsedJD,
    confirmation: UserConfirmation,
) -> dict[str, Any]:
    """AI rewrites resume content per user's confirmed choices."""

    # Enrich only if the resume wasn't already enriched in the analyze step
    # (skills/tech_stack populated = already enriched)
    if parsed_resume.skills or parsed_resume.tech_stack:
        enriched = parsed_resume
    else:
        enriched = await enrich_resume(parsed_resume)

    # Build a slim resume JSON — only fields the rewrite actually uses.
    # Excludes raw_text, certifications, languages, location to cut ~300-400 tokens.
    full = enriched.model_dump(exclude={"raw_text"})
    original_json = {
        "personal_info": {"full_name": full.get("personal_info", {}).get("full_name", "")},
        "summary": full.get("summary"),
        "skills": full.get("skills", []),
        "tech_stack": full.get("tech_stack", []),
        "experience": [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "start_date": e.get("start_date", ""),
                "end_date": e.get("end_date", ""),
                "bullets": e.get("bullets", []),
            }
            for e in (full.get("experience") or [])
        ],
        "projects": [
            {
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "bullets": p.get("bullets", []),
            }
            for p in (full.get("projects") or [])
        ],
        "education": full.get("education", []),
        "total_years_experience": full.get("total_years_experience"),
        "primary_domain": full.get("primary_domain"),
    }

    # Compute original summary word count reliably.
    #
    # Strategy (in priority order):
    #   1. Count words in the full summary as extracted from raw_text by
    #      pdfplumber (which preserves the complete multi-sentence paragraph).
    #      This is the most accurate source.
    #   2. If the raw_text summary is shorter than the AI-extracted summary
    #      (shouldn't happen but guards against edge cases), prefer the longer.
    #   3. Fallback: estimate from raw_text length proportional to summary share.
    #
    # We intentionally do NOT use section-header regex patterns — those are
    # resume-format specific and break for non-English or differently named
    # sections. Instead, we trust pdfplumber's raw_text which always contains
    # the full paragraph, then count words in the portion that matches the
    # AI-extracted summary start.
    raw_text = enriched.raw_text or ""
    ai_summary = (full.get("summary") or "").strip()
    ai_summary_words = len(ai_summary.split()) if ai_summary else 0

    orig_summary_words = 0
    if raw_text and ai_summary:
        # Find where the AI-extracted summary (first sentence) starts in raw text
        # then count all text until the next double-newline / section boundary.
        import re as _re_s
        first_phrase = " ".join(ai_summary.split()[:6])  # first 6 words as anchor
        idx = raw_text.find(first_phrase)
        if idx >= 0:
            # Scan forward from the anchor to the next blank line or a line that
            # is ALL CAPS (section header) — works for any resume format.
            segment = raw_text[idx:]
            # Stop at first blank line after at least 20 chars
            end_match = _re_s.search(r'\n\s*\n|\n[A-Z][A-Z ]{4,}\n', segment)
            if end_match:
                segment = segment[:end_match.start()]
            orig_summary_words = max(len(segment.split()), ai_summary_words)

    # Final fallback
    if not orig_summary_words:
        orig_summary_words = ai_summary_words if ai_summary_words > 20 else 80

    min_summary_words = max(30, round(orig_summary_words * 0.88))
    max_summary_words = round(orig_summary_words * 1.12)

    user_prompt = REWRITE_USER.format(
        original_resume_json=json.dumps(original_json, indent=2)[:9000],
        job_title=parsed_jd.job_title,
        required_skills=", ".join(parsed_jd.required_skills[:20]),
        hard_keywords=", ".join(parsed_jd.hard_keywords[:20]),
        soft_keywords=", ".join(parsed_jd.soft_keywords[:15]),
        seniority=parsed_jd.seniority_level or "mid",
        rewrite_summary=confirmation.rewrite_summary,
        rewrite_bullets=confirmation.rewrite_bullets,
        reorder_sections=confirmation.reorder_sections,
        adjust_tone=confirmation.adjust_tone,
        skills_to_add=", ".join(confirmation.skills_to_add),
        skills_to_skip=", ".join(confirmation.skills_to_skip),
        original_summary_words=orig_summary_words,
        min_summary_words=min_summary_words,
        max_summary_words=max_summary_words,
    )

    data = await _chat(REWRITE_SYSTEM, user_prompt, temperature=0.4, label="rewrite_resume")
    data["_original"] = original_json  # keep original for hallucination check
    return data


async def verify_no_hallucination(
    original: ParsedResume,
    rewritten: dict,
    skills_to_add: list[str] | None = None,
) -> dict:
    """
    Hallucination guard: revert only genuinely fabricated facts, not rewording.
    Uses bullet-level granularity for experience/projects so a single bad bullet
    does not wipe the entire section.
    """
    original_json = original.model_dump(exclude={"raw_text"})
    rewritten_clean = {k: v for k, v in rewritten.items() if k != "_original"}

    approved_lower = {s.lower() for s in (skills_to_add or [])}

    approved_note = ""
    if skills_to_add:
        approved_note = (
            "\n\nUSER-APPROVED ADDITIONS (these were explicitly selected by the user — "
            "NEVER flag them as hallucinations):\n"
            + "\n".join(f"- {s}" for s in skills_to_add)
        )

    user_prompt = HALLUCINATION_CHECK_USER.format(
        original_json=json.dumps(original_json, indent=2)[:8000],
        rewritten_json=json.dumps(rewritten_clean, indent=2)[:8000],
    ) + approved_note

    # Use full model for hallucination guard — gpt-4o-mini is too aggressive,
    # flags legitimate action-verb rewrites as hallucinations, and ironically
    # takes longer (14s+) than gpt-4o (1-3s) for this structured task.
    data = await _chat(HALLUCINATION_CHECK_SYSTEM, user_prompt, temperature=0.1, label="hallucination_check", model=MODEL)

    is_clean = _parse_bool(data.get("is_clean"), default=True)
    flags = data.get("flags", []) or []

    if is_clean or not flags:
        return rewritten_clean

    log.warning("[hallucination] guard caught %d issue(s) — reverting to originals", len(flags))
    result = copy.deepcopy(rewritten_clean)

    for flag in flags:
        section = flag.get("section", "")
        rewritten_text = str(flag.get("rewritten_text", "") or "")
        revert_to = flag.get("revert_to") or flag.get("original_text", "")
        exp_idx = flag.get("experience_index", -1)
        bullet_idx = flag.get("bullet_index", -1)

        # Skills: protect user-approved additions before deciding to revert.
        # The guard sometimes flags the entire skills list when a skill it doesn't
        # recognise appears — but if that skill was explicitly requested by the user
        # we must keep it.  We also guard against null/ambiguous flag payloads.
        if section == "skills":
            all_flag_text = " ".join(filter(None, [
                rewritten_text,
                str(flag.get("original_text") or ""),
                str(flag.get("revert_to") or ""),
            ])).lower()

            # If the flag mentions ANY user-approved skill, it's a false positive — skip.
            if approved_lower and any(a in all_flag_text for a in approved_lower):
                log.info("[hallucination]   KEPT skills flag (user-approved skill detected in flag): %s...", rewritten_text[:60])
                continue

            # Null / ambiguous payload with approved skills present — play it safe, skip.
            if approved_lower and (not rewritten_text or rewritten_text == "None"):
                log.info("[hallucination]   KEPT skills flag (ambiguous null payload, approved skills exist)")
                continue

            # Genuine hallucination in skills — revert
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            result["skills"] = original_json.get("skills", result.get("skills"))
            result["tech_stack"] = original_json.get("tech_stack", result.get("tech_stack"))
            continue

        # Education: check the flag isn't just restating what's already in original
        if section == "education":
            orig_edu_str = json.dumps(original_json.get("education", []))
            if revert_to and revert_to.lower() in orig_edu_str.lower():
                continue
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            result["education"] = original_json.get("education", result.get("education"))
            continue

        # Summary: full revert
        if section == "summary":
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            result["summary"] = original_json.get("summary", result.get("summary"))
            continue

        # Experience: bullet-level granular revert when indices are provided
        if section == "experience":
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            orig_exp = original_json.get("experience", [])
            res_exp = result.get("experience", [])
            if (
                isinstance(exp_idx, int) and exp_idx >= 0
                and exp_idx < len(orig_exp)
                and exp_idx < len(res_exp)
                and isinstance(bullet_idx, int) and bullet_idx >= 0
            ):
                orig_bullets = orig_exp[exp_idx].get("bullets", [])
                if bullet_idx < len(orig_bullets):
                    res_bullets = list(res_exp[exp_idx].get("bullets", []))
                    if bullet_idx < len(res_bullets):
                        res_bullets[bullet_idx] = orig_bullets[bullet_idx]
                        result["experience"][exp_idx]["bullets"] = res_bullets
                    continue
            # Fall back to whole-entry revert only when no index given
            if isinstance(exp_idx, int) and exp_idx >= 0 and exp_idx < len(orig_exp):
                result["experience"][exp_idx] = orig_exp[exp_idx]
            else:
                result["experience"] = original_json.get("experience", result.get("experience"))
            continue

        # Projects: same granular approach
        if section == "projects":
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            orig_proj = original_json.get("projects", [])
            res_proj = result.get("projects", [])
            if (
                isinstance(exp_idx, int) and exp_idx >= 0
                and exp_idx < len(orig_proj)
                and exp_idx < len(res_proj)
                and isinstance(bullet_idx, int) and bullet_idx >= 0
            ):
                orig_bullets = orig_proj[exp_idx].get("bullets", [])
                if bullet_idx < len(orig_bullets):
                    res_bullets = list(res_proj[exp_idx].get("bullets", []))
                    if bullet_idx < len(res_bullets):
                        res_bullets[bullet_idx] = orig_bullets[bullet_idx]
                        result["projects"][exp_idx]["bullets"] = res_bullets
                    continue
            if isinstance(exp_idx, int) and exp_idx >= 0 and exp_idx < len(orig_proj):
                result["projects"][exp_idx] = orig_proj[exp_idx]
            else:
                result["projects"] = original_json.get("projects", result.get("projects"))
            continue

        # Certifications
        if section == "certifications":
            log.warning("[hallucination]   reverting in %s: %s...", section, rewritten_text[:60])
            result["certifications"] = original_json.get("certifications", result.get("certifications"))

    return result
