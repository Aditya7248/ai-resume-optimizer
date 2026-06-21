"""
Preflight Validator — runs before AI processing.
Detects semantic mismatches between candidate profile and JD.
Produces structured flags for the Review & Confirm panel.
"""

import re
import difflib

from models.resume import ParsedResume
from models.jd import ParsedJD, SeniorityLevel
from models.optimization import PreflightFlag, FlagType, FlagCategory

# Common abbreviations → full form, used to normalise domain strings before comparison.
# No need to enumerate every domain — just handle ambiguous short forms.
_DOMAIN_ABBREV: dict[str, str] = {
    r"\bhr\b": "human resources",
    r"\bai\b": "artificial intelligence",
    r"\bml\b": "machine learning",
    r"\bde\b": "data engineering",
    r"\bda\b": "data analytics",
    r"\bbi\b": "business intelligence",
    r"\bpm\b": "project management",
    r"\bba\b": "business analyst",
    r"\bqa\b": "quality assurance",
    r"\bsre\b": "site reliability engineering",
    r"\bui\b": "user interface",
    r"\bux\b": "user experience",
    r"\bit\b": "information technology",
    r"\bsec\b": "security",
    r"\binfosec\b": "information security",
    r"\bfintech\b": "financial technology",
    r"\bbfsi\b": "banking financial services insurance",
    r"\bcrm\b": "customer relationship management",
    r"\berp\b": "enterprise resource planning",
    r"\bscm\b": "supply chain management",
    r"\bsap\b": "sap enterprise",
}

# Stop-words to ignore when computing word-overlap between domain strings
_STOP_WORDS = {"and", "the", "of", "in", "for", "a", "an", "with", "&", "/"}

# Synonym clusters — domains in the same set are treated as compatible (score → 1.0).
# Only needed for cases where text similarity alone would fail (no shared words/chars).
_DOMAIN_SYNONYM_CLUSTERS: list[frozenset[str]] = [
    frozenset(["business intelligence", "data analytics", "data analysis",
               "analytics", "bi", "reporting", "data visualisation", "data visualization"]),
    frozenset(["devops", "cloud", "cloud infrastructure", "platform engineering",
               "site reliability engineering", "sre", "infrastructure"]),
    frozenset(["healthcare", "medical", "medtech", "health technology",
               "clinical", "health informatics", "pharma"]),
    frozenset(["supply chain", "scm", "logistics", "operations management",
               "procurement", "warehouse"]),
    frozenset(["human resources", "people operations", "talent management",
               "hr", "talent acquisition", "recruiting"]),
    frozenset(["product management", "program management", "project management",
               "delivery management", "agile"]),
    frozenset(["marketing", "growth", "digital marketing", "brand management",
               "content marketing", "performance marketing"]),
    frozenset(["legal", "compliance", "regulatory", "governance",
               "risk and compliance", "grc"]),
    frozenset(["finance", "accounting", "financial analysis", "fintech",
               "investment", "banking", "treasury", "bfsi"]),
    frozenset(["customer success", "account management", "client management",
               "customer experience", "cx"]),
    frozenset(["sales", "business development", "revenue", "pre-sales", "presales"]),
    frozenset(["education", "edtech", "training", "learning and development",
               "instructional design"]),
]


def _in_same_synonym_cluster(a_norm: str, b_norm: str) -> bool:
    """Return True if both normalised domain strings appear in the same synonym cluster."""
    for cluster in _DOMAIN_SYNONYM_CLUSTERS:
        in_a = any(kw in a_norm for kw in cluster)
        in_b = any(kw in b_norm for kw in cluster)
        if in_a and in_b:
            return True
    return False


def _normalise_domain(domain: str) -> str:
    """Lowercase, expand abbreviations, remove stop-words."""
    d = domain.lower().strip()
    d = re.sub(r"[^a-z\s]", " ", d)  # strip punctuation
    for pattern, expansion in _DOMAIN_ABBREV.items():
        d = re.sub(pattern, expansion, d)
    return d


def _domain_similarity(domain_a: str, domain_b: str) -> float:
    """
    Return a 0–1 similarity score between two domain strings.

    Uses three signals:
      1. Exact match after normalisation
      2. Word-level Jaccard overlap (ignores stop-words)
      3. Character-level SequenceMatcher ratio

    Returns the MAX of the three so that even a single strong signal
    (e.g. one domain is a substring of the other) yields a high score.
    """
    if not domain_a or not domain_b:
        return 1.0  # can't determine mismatch — don't penalise

    a = _normalise_domain(domain_a)
    b = _normalise_domain(domain_b)

    if a == b:
        return 1.0

    # Substring containment — handles "Data Engineer" ↔ "Data Engineering"
    if a in b or b in a:
        return 0.90

    # Synonym cluster — handles "Business Intelligence" ↔ "Data Analytics" etc.
    if _in_same_synonym_cluster(a, b):
        return 0.90

    # Word Jaccard (ignores stop-words)
    words_a = set(a.split()) - _STOP_WORDS
    words_b = set(b.split()) - _STOP_WORDS
    if words_a and words_b:
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        jaccard = intersection / union if union else 0.0
    else:
        jaccard = 0.0

    # Character fuzzy ratio
    fuzzy = difflib.SequenceMatcher(None, a, b).ratio()

    return max(jaccard, fuzzy)


def _check_experience_gap(resume: ParsedResume, jd: ParsedJD) -> PreflightFlag | None:
    candidate_exp = resume.total_years_experience
    jd_min = jd.required_experience_min

    if candidate_exp is None or jd_min is None:
        return None

    gap = jd_min - candidate_exp

    if gap > 5:
        return PreflightFlag(
            flag_type=FlagType.RED,
            category=FlagCategory.EXPERIENCE_GAP,
            title="Significant Experience Gap",
            message=f"JD requires {jd_min}+ years · Your resume reflects ~{candidate_exp} years",
            detail=f"A gap of {gap:.0f}+ years may cause automatic ATS rejection at most companies.",
            requires_acknowledgement=True,
        )
    elif gap > 0:
        return PreflightFlag(
            flag_type=FlagType.YELLOW,
            category=FlagCategory.EXPERIENCE_GAP,
            title="Experience Gap",
            message=f"JD requires {jd_min} years · Your resume shows ~{candidate_exp} years",
            detail="You are slightly below the stated requirement. Optimization will still proceed.",
            requires_acknowledgement=True,
        )
    elif candidate_exp - (jd.required_experience_max or jd_min) > 5:
        return PreflightFlag(
            flag_type=FlagType.YELLOW,
            category=FlagCategory.SENIORITY_MISMATCH,
            title="Potential Overqualification",
            message=f"Your experience ({candidate_exp} yrs) significantly exceeds JD requirement ({jd_min} yrs)",
            detail="You may appear overqualified. Consider whether to de-emphasize seniority.",
            requires_acknowledgement=False,
        )
    return None


def _check_domain_mismatch(resume: ParsedResume, jd: ParsedJD) -> PreflightFlag | None:
    """
    Dynamic domain mismatch check — works for ANY domain without hardcoded lists.

    Uses fuzzy similarity between the AI-extracted primary_domain strings:
      ≥ 0.70  → compatible, no flag
      0.40–0.69 → partial overlap, INFO flag
      < 0.40  → significant mismatch, RED flag (requires acknowledgement)
    """
    candidate_domain = (resume.primary_domain or "").strip()
    jd_domain = (jd.primary_domain or "").strip()

    if not candidate_domain or not jd_domain:
        return None  # can't assess without data

    score = _domain_similarity(candidate_domain, jd_domain)

    if score >= 0.70:
        return None  # compatible

    if score >= 0.40:
        return PreflightFlag(
            flag_type=FlagType.INFO,
            category=FlagCategory.DOMAIN_MISMATCH,
            title="Partial Domain Match",
            message=f"Your primary domain is {candidate_domain} · JD targets {jd_domain}",
            detail="There is some overlap between the domains — optimization will still be effective.",
            requires_acknowledgement=False,
        )

    return PreflightFlag(
        flag_type=FlagType.RED,
        category=FlagCategory.DOMAIN_MISMATCH,
        title="Domain Mismatch",
        message=f"Your primary domain is {candidate_domain} · JD targets {jd_domain}",
        detail="Significant domain mismatch detected. Resume optimization will be limited in effectiveness.",
        requires_acknowledgement=True,
    )


def _check_seniority(resume: ParsedResume, jd: ParsedJD) -> PreflightFlag | None:
    if not jd.seniority_level or not resume.total_years_experience:
        return None

    exp = resume.total_years_experience
    seniority = jd.seniority_level

    # Junior role but senior candidate
    if seniority in (SeniorityLevel.INTERN, SeniorityLevel.JUNIOR) and exp > 5:
        return PreflightFlag(
            flag_type=FlagType.YELLOW,
            category=FlagCategory.SENIORITY_MISMATCH,
            title="Seniority Mismatch — Overqualified",
            message=f"JD targets {seniority.value} level · You have {exp} years of experience",
            detail="Recruiters may screen you out as overqualified.",
            requires_acknowledgement=False,
        )

    # Senior role but junior candidate
    if seniority in (SeniorityLevel.LEAD, SeniorityLevel.MANAGER, SeniorityLevel.DIRECTOR) and exp < 5:
        return PreflightFlag(
            flag_type=FlagType.RED,
            category=FlagCategory.SENIORITY_MISMATCH,
            title="Seniority Mismatch — Underqualified",
            message=f"JD targets {seniority.value} level · You have {exp} years of experience",
            detail="This role typically requires significant leadership/management experience.",
            requires_acknowledgement=True,
        )
    return None


def _check_missing_certifications(resume: ParsedResume, jd: ParsedJD) -> list[PreflightFlag]:
    flags = []
    if not jd.certifications_required:
        return flags

    resume_cert_text = " ".join(
        c.name.lower() for c in resume.certifications
    )

    for cert in jd.certifications_required:
        if cert.lower() not in resume_cert_text:
            flags.append(PreflightFlag(
                flag_type=FlagType.RED,
                category=FlagCategory.CERTIFICATION_MISSING,
                title=f"Required Certification Missing: {cert}",
                message=f"JD requires '{cert}' · Not found in your resume",
                detail="This certification cannot be added without fabricating credentials.",
                requires_acknowledgement=True,
            ))
    return flags


def _check_location(resume: ParsedResume, jd: ParsedJD) -> PreflightFlag | None:
    if not jd.location or not resume.personal_info.location:
        return None

    jd_city = jd.location.lower()
    candidate_city = resume.personal_info.location.lower()

    # Simple city mismatch check
    jd_city_words = set(jd_city.split())
    candidate_city_words = set(candidate_city.split())

    if not jd_city_words.intersection(candidate_city_words):
        work_mode = (jd.work_mode or "").lower()
        if "wfo" in work_mode or "office" in work_mode:
            return PreflightFlag(
                flag_type=FlagType.YELLOW,
                category=FlagCategory.LOCATION_MISMATCH,
                title="Location Mismatch",
                message=f"JD: {jd.location} ({jd.work_mode}) · Your location: {resume.personal_info.location}",
                detail="This role requires work from office. Location may be a concern.",
                requires_acknowledgement=False,
            )
    return None


def _check_notice_period(resume: ParsedResume, jd: ParsedJD) -> PreflightFlag | None:
    if not jd.notice_period:
        return None

    notice_lower = jd.notice_period.lower()
    if "immediate" in notice_lower or "0 days" in notice_lower:
        return PreflightFlag(
            flag_type=FlagType.YELLOW,
            category=FlagCategory.NOTICE_PERIOD,
            title="Immediate Joiner Preferred",
            message="JD prefers immediate joiners",
            detail="If you have a notice period, this may affect your candidacy.",
            requires_acknowledgement=False,
        )
    return None


def run_preflight(resume: ParsedResume, jd: ParsedJD) -> list[PreflightFlag]:
    """Run all validators and return consolidated flags list."""
    flags = []

    checkers = [
        _check_experience_gap(resume, jd),
        _check_domain_mismatch(resume, jd),
        _check_seniority(resume, jd),
        _check_location(resume, jd),
        _check_notice_period(resume, jd),
    ]

    for flag in checkers:
        if flag:
            flags.append(flag)

    # Certification checks (returns list)
    flags.extend(_check_missing_certifications(resume, jd))

    # Sort: RED first, then YELLOW, then INFO
    priority = {FlagType.RED: 0, FlagType.YELLOW: 1, FlagType.INFO: 2}
    flags.sort(key=lambda f: priority.get(f.flag_type, 3))

    return flags
