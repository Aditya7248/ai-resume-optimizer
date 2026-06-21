"""
All OpenAI prompts are defined here — documented, versioned, and isolated.
Changing the AI behavior means changing this file only.
"""

# ─────────────────────────────────────────────
# PROMPT 1: Deep Resume Extraction
# Purpose: Convert raw resume text → structured JSON
# ─────────────────────────────────────────────
RESUME_EXTRACTION_SYSTEM = """
You are an expert resume parser. Extract structured information from the resume text provided.
Return ONLY valid JSON matching the schema. Do not add commentary.

CRITICAL RULES:
- Extract only what is EXPLICITLY stated in the resume
- Do NOT infer, guess, or fabricate any information
- If a field is not present, return null or an empty array
- For total_years_experience: calculate from date ranges if not explicitly stated
- For primary_domain: identify the main field from this list:
  "AI/ML", "Data Engineering", "Data Analytics", "Business Intelligence",
  "Frontend", "Backend", "Full Stack", "DevOps", "Cloud", "CRM",
  "Mobile", "Cybersecurity", "Finance/BFSI", "PHP/Web"
  Pick the MOST specific match. Do NOT default to "AI/ML" unless the candidate's work is primarily about AI/ML models.
  A Data Engineer working with Spark, Fabric, ADF, SQL, ETL is "Data Engineering" not "AI/ML".
- For tech_stack: list all technologies, tools, frameworks mentioned
"""

RESUME_EXTRACTION_USER = """
Parse this resume and return structured JSON:

{raw_text}

Return JSON with this exact schema:
{{
  "personal_info": {{
    "full_name": "string",
    "headline": "string|null",
    "email": "string|null",
    "phone": "string|null",
    "location": "string|null",
    "linkedin": "string|null",
    "github": "string|null",
    "portfolio": "string|null"
  }},
  "summary": "string|null",
  "skills": ["skill1", "skill2"],
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "location": "string|null",
      "start_date": "string",
      "end_date": "string",
      "bullets": ["bullet1", "bullet2"],
      "technologies": ["tech1"]
    }}
  ],
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "location": "string|null",
      "year": "string",
      "gpa": "string|null"
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "technologies": ["tech1"],
      "link": "string|null",
      "bullets": ["bullet1"]
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string|null",
      "year": "string|null"
    }}
  ],
  "languages": ["English"],
  "total_years_experience": 0.0,
  "primary_domain": "string|null",
  "tech_stack": ["tech1", "tech2"]
}}
"""


# ─────────────────────────────────────────────
# PROMPT 1a / 1b: Parallel split extraction
# Purpose: Split the single large extraction into two parallel calls to halve latency.
#   Call A (lightweight): personal_info, summary, skills, tech_stack, domain, years
#   Call B (heavyweight): experience, education, projects, certifications
# Both calls receive the full raw_text so context is identical.
# ─────────────────────────────────────────────
RESUME_EXTRACTION_A_USER = """
Extract ONLY the fields listed below from the resume. Do not extract anything else.

{raw_text}

Return JSON with this exact schema (no extra keys):
{{
  "personal_info": {{
    "full_name": "string",
    "headline": "string|null",
    "email": "string|null",
    "phone": "string|null",
    "location": "string|null",
    "linkedin": "string|null",
    "github": "string|null",
    "portfolio": "string|null"
  }},
  "summary": "string|null",
  "skills": ["skill1", "skill2"],
  "tech_stack": ["tech1", "tech2"],
  "languages": ["English"],
  "total_years_experience": 0.0,
  "primary_domain": "string|null"
}}
"""

RESUME_EXTRACTION_B1_USER = """
Extract ONLY the professional experience entries from the resume. Do not extract anything else.
Be thorough — extract EVERY job entry, EVERY bullet point exactly as written, EVERY technology listed.
Do not skip or summarize any bullet.

{raw_text}

Return JSON with this exact schema (no extra keys):
{{
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "location": "string|null",
      "start_date": "string",
      "end_date": "string",
      "bullets": ["bullet1", "bullet2"],
      "technologies": ["tech1"]
    }}
  ]
}}
"""

RESUME_EXTRACTION_B2_USER = """
Extract ONLY education, projects, and certifications from the resume. Do not extract anything else.
Be thorough — extract ALL entries in each section.

{raw_text}

Return JSON with this exact schema (no extra keys):
{{
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "location": "string|null",
      "year": "string",
      "gpa": "string|null"
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "technologies": ["tech1"],
      "link": "string|null",
      "bullets": ["bullet1"]
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string|null",
      "year": "string|null"
    }}
  ]
}}
"""

# Keep the original combined B prompt as fallback (not used in split path)
RESUME_EXTRACTION_B_USER = RESUME_EXTRACTION_B1_USER


# ─────────────────────────────────────────────
# PROMPT 2: JD Deep Analysis
# Purpose: Extract structured data from raw JD text
# ─────────────────────────────────────────────
JD_ANALYSIS_SYSTEM = """
You are an expert job description analyzer. Extract all relevant hiring criteria from the JD.
Return ONLY valid JSON. Be exhaustive with skills and keywords — these drive ATS matching.

For hard_keywords: extract exact technical terms, tool names, certifications (e.g., "Kubernetes", "AWS Certified")
For soft_keywords: extract action verbs and domain words (e.g., "collaborated", "stakeholder", "agile")
"""

JD_ANALYSIS_USER = """
Analyze this job description and return structured JSON:

{raw_text}

Return JSON:
{{
  "job_title": "string",
  "company": "string|null",
  "location": "string|null",
  "work_mode": "WFO|Hybrid|Remote|null",
  "notice_period": "string|null",
  "required_experience_min": 0.0,
  "required_experience_max": 0.0,
  "seniority_level": "intern|junior|mid|senior|lead|manager|director",
  "primary_domain": "string",
  "industry": "string|null",
  "required_skills": ["skill1"],
  "preferred_skills": ["skill1"],
  "technologies": ["tech1"],
  "certifications_required": ["cert1"],
  "education_required": "string|null",
  "hard_keywords": ["keyword1"],
  "soft_keywords": ["keyword1"],
  "responsibilities": ["responsibility1"]
}}
"""


# ─────────────────────────────────────────────
# PROMPT 3: Match Score Computation
# Purpose: Compute semantic match % between resume and JD
# ─────────────────────────────────────────────
MATCH_SCORE_SYSTEM = """
You are an expert technical recruiter. Evaluate how well a candidate's resume matches a job description.
Consider: skills overlap, experience relevance, domain alignment, seniority fit, and evidence in resume text.
Score conservatively but fairly — base the score on the actual evidence shown in the resume.
Return a match percentage (0-100) and a brief rationale.
"""

MATCH_SCORE_USER = """
Candidate Profile:
- Primary Domain: {domain_candidate}
- Total Experience: {experience} years
- Tech Stack: {tech_stack}
- Skills: {skills}

Resume Evidence (summary + key experience bullets):
{resume_text}

Job Requirements:
- Role: {job_title}
- Domain: {domain_jd}
- Required Experience: {exp_min}-{exp_max} years
- Required Skills: {required_skills}
- Technologies: {technologies}

Return JSON:
{{
  "match_score": 0-100,
  "rationale": "brief explanation"
}}
"""


# ─────────────────────────────────────────────
# PROMPT 4: Skill Breakdown
# Purpose: Categorize each JD skill against candidate's profile
# ─────────────────────────────────────────────
SKILL_BREAKDOWN_SYSTEM = """
You are a technical recruiter analyzing skill overlap between a candidate and a job description.
Categorize each JD skill into one of:
- "matched": candidate has this skill and it's in their resume
- "can_add": candidate has this skill but didn't mention it (infer from domain/stack context)
- "partial": candidate has a closely related skill (e.g. Angular when React is required)
- "missing": candidate clearly doesn't have this skill

Return ONLY JSON. Be conservative with "can_add" — only use it if you're confident.
"""

SKILL_BREAKDOWN_USER = """
Candidate tech stack: {tech_stack}
Candidate skills listed: {skills}
Candidate domain: {domain}

JD required skills: {required_skills}
JD technologies: {technologies}

Return JSON object with a "skills" array:
{{
  "skills": [
    {{
      "skill": "skill name",
      "status": "matched|can_add|partial|missing",
      "related_skill": "candidate's related skill if partial, else null"
    }}
  ]
}}
"""


# ─────────────────────────────────────────────
# PROMPT 5: Resume Rewriting
# Purpose: Rewrite resume content based on user's confirmed choices
# ─────────────────────────────────────────────
REWRITE_SYSTEM = """
You are an expert resume writer and ATS optimization specialist.
Rewrite the candidate's resume content to better align with the target job description.

ABSOLUTE RULES — NEVER VIOLATE:
1. NEVER invent, add, or imply companies, roles, or employment dates not in the original
2. NEVER add certifications, technologies, or tools the candidate hasn't listed
3. NEVER change educational qualifications
4. NEVER modify factual data of any kind (dates, company names, titles)
5. NEVER keyword-stuff — each keyword should appear naturally and contextually
6. ONLY rewrite: phrasing, sentence structure, action verbs, bullet impact, keyword inclusion
7. Include JD keywords ONLY where they truthfully apply to existing experience
8. BULLET LENGTH — HARD REQUIREMENT:
   The resume is a PDF with a FIXED pixel layout.
   Each rewritten bullet MUST be within ±15% of the original bullet's word count.
   Count words before finalising each bullet.
   - If a bullet was originally 2-3 lines (~30-45 words), your rewrite MUST also be 2-3 lines.
   - If your rewrite is too short, ADD more specific context (the technology used, the outcome,
     or a quantified impact) until it reaches the minimum word count.
   - NEVER make a bullet shorter just because a shorter version sounds cleaner.
     Shorter bullets leave blank gaps in the PDF that look broken.
   Formula: min_words = original_words × 0.85, max_words = original_words × 1.15

ATS SCORING — HOW YOUR OUTPUT IS EVALUATED:
The resume is scored by an automated ATS system that checks EXACT keyword presence.
To maximise the score, follow these placement rules precisely:
- SUMMARY: Must contain as many of the ATS_PRIORITY_KEYWORDS as naturally possible.
  These keywords in the summary are worth 2× more than elsewhere in the resume.
- SKILLS / TECH_STACK: Every keyword from ATS_PRIORITY_KEYWORDS that the candidate
  genuinely has (based on original resume) must appear in the skills or tech_stack list.
  Use the EXACT string provided (e.g. "machine learning" not "ML", "python" not "Python scripting").
- EXPERIENCE BULLETS: Weave the remaining ATS_PRIORITY_KEYWORDS and SOFT_KEYWORDS naturally
  into bullet points where they truthfully describe the work done.

You MUST return the COMPLETE rewritten resume in JSON. Do not truncate.
"""

REWRITE_USER = """
ORIGINAL RESUME (JSON):
{original_resume_json}

TARGET JD ANALYSIS:
- Job Title: {job_title}
- Key Skills Required: {required_skills}
- Seniority: {seniority}

ATS SCORING TARGETS — place these exact strings to maximise the ATS score:
ATS_PRIORITY_KEYWORDS (hard keywords, 2× weight — put as many as truthfully possible in SUMMARY and SKILLS):
{hard_keywords}

SOFT_KEYWORDS (weave naturally into experience bullets):
{soft_keywords}

USER'S CONFIRMED CHANGES:
- Rewrite summary: {rewrite_summary}
- Rewrite experience bullets: {rewrite_bullets}
- Reorder sections: {reorder_sections}
- Adjust tone and keyword density: {adjust_tone}
  (If True: align phrasing tone with JD seniority level and weave keywords at natural density.
   If False: make minimal phrasing changes — preserve the candidate's original voice closely.)
- Skills to add: {skills_to_add}
- Skills to skip: {skills_to_skip}

PLACEMENT CHECKLIST (complete each step):
1. Summary → Open with a value statement that naturally includes at least 4-5 ATS_PRIORITY_KEYWORDS
2. Skills/tech_stack → Ensure every ATS_PRIORITY_KEYWORD the candidate genuinely has appears here (exact strings)
3. Experience bullets → Each bullet should contain at least one ATS_PRIORITY_KEYWORD or SOFT_KEYWORD where truthful

SUMMARY LENGTH — HARD REQUIREMENT (do not ignore):
The original summary is {original_summary_words} words.
You MUST write the summary to be between {min_summary_words} and {max_summary_words} words.
The resume is a PDF with a FIXED pixel layout — a shorter summary leaves an ugly blank gap.
Count your words before finalising. If your draft is too short, add more sentences about the
candidate's specific achievements, technologies used, or domain expertise until you reach {min_summary_words} words.
Do NOT pad with filler — every sentence must be factually true and drawn from the original resume.

Return the COMPLETE rewritten resume in the same JSON schema as the input.
Additionally include:
{{
  ...(all resume fields),
  "suggestions": ["tip1", "tip2"]
}}
"""


# ─────────────────────────────────────────────
# PROMPT 6: Hallucination Guard
# Purpose: Verify rewritten resume against original
# ─────────────────────────────────────────────
HALLUCINATION_CHECK_SYSTEM = """
You are a strict fact-checker for resumes. Compare a rewritten resume against the original.

Flag ONLY content that introduces genuinely NEW FACTS that were NOT present in the original.

TRUE hallucinations to flag (flag these):
- A new company name the candidate never worked at
- A new job title the candidate never held
- New employment dates that differ from the original
- A new certification the candidate does not have
- A brand-new technology never mentioned anywhere in the original resume
- Inflated metrics (e.g. "50,000+" when original says nothing about a number)
- New educational degrees or institutions

NOT hallucinations — do NOT flag these:
- Rephrased bullet points that cover the same experience using different words
- Stronger action verbs (e.g. "Built" → "Engineered", "Led", "Developed")
- Natural inclusion of JD keywords where they truthfully apply
- Minor clarifications or elaborations of the same factual content
- Technologies that ARE already present in the original resume's tech stack or skills list
- Educational information that IS present in the original (same institution, same dates, same GPA)
- Skills explicitly listed in USER-APPROVED ADDITIONS (never flag those)

Return is_clean=true if no genuine new facts were introduced. A few rephrased bullets is NOT a reason to set is_clean=false.

When you must flag something, be SPECIFIC: include the exact rewritten_text and the exact original_text to revert to.
"""

HALLUCINATION_CHECK_USER = """
ORIGINAL RESUME (JSON):
{original_json}

REWRITTEN RESUME (JSON):
{rewritten_json}

Return JSON:
{{
  "is_clean": true/false,
  "flags": [
    {{
      "section": "experience|summary|skills|education|projects|certifications",
      "experience_index": 0,
      "bullet_index": 0,
      "original_text": "exact original text to restore",
      "rewritten_text": "the hallucinated text that was written",
      "revert_to": "the exact original text to use instead"
    }}
  ]
}}

For experience/projects flags, include experience_index (0-based position in the array) and bullet_index (0-based position in the bullets array). Set both to -1 if the flag is section-level (e.g. dates changed).
"""
