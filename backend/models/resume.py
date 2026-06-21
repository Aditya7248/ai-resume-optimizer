from pydantic import BaseModel, EmailStr
from typing import Optional


class PersonalInfo(BaseModel):
    full_name: str
    headline: Optional[str] = None   # e.g. "Senior Data Engineer | Microsoft Fabric & Power BI Architect"
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None


class ExperienceEntry(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = ""   # nullable — AI may omit dates for some entries
    end_date: Optional[str] = ""     # "Present" or date string; "" means not extracted
    bullets: list[str] = []
    technologies: list[str] = []


class EducationEntry(BaseModel):
    degree: str
    institution: str
    location: Optional[str] = None
    year: Optional[str] = None   # nullable — AI may omit graduation year
    gpa: Optional[str] = None


class ProjectEntry(BaseModel):
    name: str
    description: str
    technologies: list[str] = []
    link: Optional[str] = None
    bullets: list[str] = []


class CertificationEntry(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None


class ParsedResume(BaseModel):
    personal_info: PersonalInfo
    summary: Optional[str] = None
    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    projects: list[ProjectEntry] = []
    certifications: list[CertificationEntry] = []
    languages: list[str] = []
    total_years_experience: Optional[float] = None
    primary_domain: Optional[str] = None
    tech_stack: list[str] = []
    raw_text: Optional[str] = None
