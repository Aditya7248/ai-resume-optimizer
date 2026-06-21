from pydantic import BaseModel
from typing import Optional
from enum import Enum


class FlagType(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    INFO = "info"


class FlagCategory(str, Enum):
    EXPERIENCE_GAP = "experience_gap"
    DOMAIN_MISMATCH = "domain_mismatch"
    SKILL_MISSING = "skill_missing"
    LOCATION_MISMATCH = "location_mismatch"
    EDUCATION_MISMATCH = "education_mismatch"
    SENIORITY_MISMATCH = "seniority_mismatch"
    NOTICE_PERIOD = "notice_period"
    CERTIFICATION_MISSING = "certification_missing"


class PreflightFlag(BaseModel):
    flag_type: FlagType
    category: FlagCategory
    title: str
    message: str
    detail: Optional[str] = None
    requires_acknowledgement: bool = True


class SkillStatus(str, Enum):
    MATCHED = "matched"           # candidate has it, JD wants it
    CAN_ADD = "can_add"           # candidate has it but didn't mention
    PARTIAL = "partial"           # related but not exact
    MISSING = "missing"           # JD wants it, candidate doesn't have it


class SkillItem(BaseModel):
    skill: str
    status: SkillStatus
    related_skill: Optional[str] = None   # for partial matches
    user_decision: Optional[bool] = None  # True=add, False=skip


class ATSScoreBreakdown(BaseModel):
    keyword_match: float        # max 30
    section_completeness: float # max 20
    format_parsability: float   # max 20
    keyword_placement: float    # max 15
    date_consistency: float     # max 10
    file_health: float          # max 5
    total: float                # max 100


class AnalysisResult(BaseModel):
    session_id: str
    match_score: float                      # 0-100
    ats_score_before: ATSScoreBreakdown
    flags: list[PreflightFlag] = []
    skills: list[SkillItem] = []
    experience_candidate: Optional[float] = None
    experience_required_min: Optional[float] = None
    experience_required_max: Optional[float] = None
    domain_candidate: Optional[str] = None
    domain_jd: Optional[str] = None
    missing_certifications: list[str] = []


class UserConfirmation(BaseModel):
    session_id: str
    flags_acknowledged: list[str] = []      # list of FlagCategory values
    skills_to_add: list[str] = []
    skills_to_skip: list[str] = []
    rewrite_summary: bool = True
    rewrite_bullets: bool = True
    reorder_sections: bool = True
    adjust_tone: bool = True
    template_choice: Optional[str] = None  # "modern" | "classic" | "minimal" | None (user uploaded)


class OptimizationResult(BaseModel):
    session_id: str
    ats_score_before: ATSScoreBreakdown
    ats_score_after: ATSScoreBreakdown
    match_score_before: float
    match_score_after: float
    skills_added: list[str] = []
    keywords_injected: list[str] = []
    sections_rewritten: list[str] = []
    known_gaps: list[str] = []
    suggestions: list[str] = []
    docx_filename: Optional[str] = None   # DOCX or HTML fallback; None when PDF-only
    pdf_filename: Optional[str] = None
    report_filename: str
