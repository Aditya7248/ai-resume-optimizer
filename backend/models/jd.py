from pydantic import BaseModel
from typing import Optional
from enum import Enum


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"


class ParsedJD(BaseModel):
    job_title: str
    company: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None          # WFO / Hybrid / Remote
    notice_period: Optional[str] = None
    required_experience_min: Optional[float] = None
    required_experience_max: Optional[float] = None
    seniority_level: Optional[SeniorityLevel] = None
    primary_domain: Optional[str] = None
    industry: Optional[str] = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    technologies: list[str] = []
    certifications_required: list[str] = []
    education_required: Optional[str] = None
    hard_keywords: list[str] = []           # exact tech terms
    soft_keywords: list[str] = []           # action verbs, domain words
    responsibilities: list[str] = []
    raw_text: Optional[str] = None
