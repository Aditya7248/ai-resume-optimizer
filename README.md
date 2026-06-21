# AI Resume Optimizer

> Intelligent resume tailoring — ATS-optimized, hallucination-free, layout-preserved.

Built by **Dynamics Monk** · Powered by GPT-4o · FastAPI · Next.js

---

## Overview

An end-to-end web application that takes a candidate's resume and a target Job Description, analyzes the skill and keyword gap, and uses GPT-4o to rewrite the resume for maximum ATS compatibility — without changing a single fact. The original PDF/DOCX layout is preserved exactly.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.14) + Uvicorn |
| AI Engine | OpenAI GPT-4o + GPT-4o-mini (structured JSON mode) |
| Document Processing | pdfplumber, PyMuPDF (fitz), python-docx |
| PDF Generation | PyMuPDF inplace edit · xhtml2pdf · ReportLab (fallback) |
| Template Rendering | Jinja2 (HTML → PDF via xhtml2pdf) |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| Containerization | Docker + Docker Compose |

---

## Features

- **Keep My Format** — rewrites only the text; every font, colour, and layout element in your original PDF/DOCX is preserved
- **Pre-built Templates** — Modern, Classic, and Minimal professional layouts
- **Upload Your Own Template** — DOCX with `{{PLACEHOLDER}}` tags
- **6-Signal ATS Scoring** — keyword match, section completeness, format parsability, keyword placement, date consistency, file health
- **Preflight Flags** — experience gap, domain mismatch, seniority mismatch, missing certifications, location mismatch
- **Hallucination Guard** — GPT-4o verifies every rewrite; fabricated content is automatically reverted
- **Optimization Report** — PDF report showing before/after scores, changes made, and known gaps
- **Semantic Match Score** — AI-judged fit between candidate and JD (0–100%)

---

## Quick Start

### Prerequisites
- Docker & Docker Compose installed
- OpenAI API key

### 1. Clone and configure

```bash
git clone https://github.com/Aditya7248/ai-resume-optimizer.git
cd ai-resume-optimizer
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start with Docker Compose

```bash
docker-compose up --build
```

This starts:
- Backend API at http://localhost:8000
- Frontend at http://localhost:3000
- Swagger docs at http://localhost:8000/docs

### 3. Open the app

Navigate to **http://localhost:3000**

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Your OpenAI API key |
| `NEXT_PUBLIC_API_URL` | No | Backend URL (default: `http://localhost:8000`) |

---

## API Endpoints

Full interactive docs at `/docs` (Swagger UI).

| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload/` | Upload resume + JD (+ optional template). Returns `session_id` |
| POST | `/analyze/` | Run full analysis — ATS score, match %, skill gaps, preflight flags |
| POST | `/optimize/` | AI rewrite with user-confirmed choices |
| GET | `/download/{id}/pdf` | Download optimized resume PDF |
| GET | `/download/{id}/docx` | Download optimized resume DOCX/HTML |
| GET | `/download/{id}/report` | Download optimization report PDF |
| GET | `/download/{id}/status` | Check session status |
| GET | `/health` | Health check |

---

## Application Flow

```
1. Upload   →  Resume (PDF/DOCX) + JD (PDF/DOCX/TXT) + Template choice
        ↓
2. Parse    →  Text extraction (pdfplumber / python-docx)
        ↓
3. Enrich   →  GPT-4o-mini structures resume + JD into typed JSON (parallel calls)
        ↓
4. Analyze  →  ATS score · match % · skill breakdown · preflight flags
        ↓
5. Review   →  User confirms: which skills to add, rewrite summary/bullets, template
        ↓
6. Rewrite  →  GPT-4o rewrites content with JD keywords woven in naturally
        ↓
7. Guard    →  Hallucination check — fabricated content reverted bullet-by-bullet
        ↓
8. Generate →  PDF inplace edit / DOCX edit / Jinja2 → xhtml2pdf
        ↓
9. Download →  Optimized Resume (PDF) + Optimization Report (PDF)
```

---

## Project Structure

```
ai-resume-optimizer/
├── backend/
│   ├── main.py                        # FastAPI app, CORS, session cleanup
│   ├── routers/                       # upload, analyze, optimize, download
│   ├── services/
│   │   ├── ai/                        # ai_service.py, prompts.py
│   │   ├── ats/                       # ats_scorer.py (6-signal model)
│   │   ├── parser/                    # resume_parser.py, jd_parser.py
│   │   ├── template/                  # pdf_inplace_engine.py, docx_engine.py,
│   │   │                              # html_engine.py, pdf_resume_gen.py
│   │   ├── report/                    # report_gen.py (ReportLab)
│   │   └── validator/                 # preflight.py
│   ├── models/                        # Pydantic schemas (resume, jd, optimization)
│   ├── templates/prebuilt/            # modern.html, classic.html, minimal.html
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── page.tsx                   # Upload + template selection
│       ├── review/page.tsx            # Review & Confirm panel
│       └── result/page.tsx            # Scores, download buttons
├── docker-compose.yml
└── .env.example
```

---

## AI Guardrails

The hallucination guard enforces strict constraints after every rewrite:

| Prohibited | Allowed |
|---|---|
| Invent companies or job titles | Rewrite sentence structure |
| Add certifications not in original | Rearrange section order |
| Create fake projects or skills | Improve action verbs |
| Change employment dates | Weave in JD keywords naturally |
| Modify education or degrees | Expand/condense bullet descriptions |

Reverts are applied at **bullet level** — a single bad bullet is reverted without touching the rest of the entry. User-approved skills (`skills_to_add`) are explicitly protected from revert.

---

## ATS Scoring Model

6-signal deterministic model grounded in Workday, Taleo, Greenhouse, and Lever behavior:

| Signal | Max | What it measures |
|---|---|---|
| Keyword Match | 30 | Hard & soft JD keywords found in resume (skills, bullets, summary) |
| Section Completeness | 20 | Name, email, phone, summary, experience+dates, skills, education |
| Format Parsability | 20 | Text is machine-readable; no image-based PDF; no excessive tables |
| Keyword Placement | 15 | JD keywords appear early — in summary and first bullets |
| Date Consistency | 10 | All experience entries have valid start and end dates |
| File Health | 5 | File size, encoding, no corruption indicators |

> Score reflects general ATS compatibility. Not a guarantee for any specific system.

---

## License

For academic/assignment purposes only. Confidential.
