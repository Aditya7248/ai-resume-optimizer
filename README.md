# AI Resume Optimizer & Template Generator

> Intelligent resume tailoring — ATS-optimized, hallucination-free, template-preserved.

---

## Overview

An end-to-end web application that accepts a candidate's resume, a target Job Description, and a DOCX template — then uses GPT-4o to rewrite and optimize the resume for maximum ATS compatibility, while preserving the exact visual design of the uploaded template.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.11) + Uvicorn |
| AI Engine | OpenAI GPT-4o (structured JSON output) |
| Document Processing | python-docx, pdfplumber, pypdf |
| PDF Generation | LibreOffice headless |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| Containerization | Docker + Docker Compose |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose installed
- OpenAI API key

### 1. Clone and configure

```bash
git clone <repo-url>
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

# Set env variables
export OPENAI_API_KEY=sk-your-key-here

# Run
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Set env
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Your OpenAI API key |
| `ENVIRONMENT` | No | `development` or `production` |
| `NEXT_PUBLIC_API_URL` | No | Backend URL (default: http://localhost:8000) |

---

## API Endpoints

Full interactive docs at `/docs` (Swagger UI).

| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload/` | Upload resume, JD, and template files |
| POST | `/analyze/` | Run preflight analysis (flags, ATS score, skills) |
| POST | `/optimize/` | Run AI optimization with user confirmation |
| GET | `/download/{id}/docx` | Download optimized DOCX |
| GET | `/download/{id}/pdf` | Download optimized PDF |
| GET | `/download/{id}/report` | Download optimization report PDF |
| GET | `/download/{id}/status` | Check session status |
| GET | `/health` | Health check |

---

## Application Flow

```
1. Upload (resume + JD + template)
        ↓
2. Parse (extract structured data from all files)
        ↓
3. Analyze (ATS score, skill gaps, preflight flags)
        ↓
4. Review & Confirm (user approves each change)
        ↓
5. AI Rewrite (GPT-4o rewrites content per user choices)
        ↓
6. Hallucination Guard (verify nothing was fabricated)
        ↓
7. Template Injection (content → DOCX/PDF)
        ↓
8. Download (DOCX + PDF + Report)
```

---

## Project Structure

```
ai-resume-optimizer/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── routers/                   # upload, analyze, optimize, download
│   ├── services/
│   │   ├── parser/                # resume_parser.py, jd_parser.py
│   │   ├── ai/                    # ai_service.py, prompts.py
│   │   ├── validator/             # preflight.py
│   │   ├── ats/                   # ats_scorer.py
│   │   ├── template/              # docx_engine.py, html_engine.py
│   │   └── report/                # report_gen.py
│   ├── models/                    # Pydantic schemas
│   ├── templates/prebuilt/        # modern.html, classic.html, minimal.html
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── page.tsx               # Upload page
│       ├── review/page.tsx        # Review & Confirm panel
│       └── result/page.tsx        # Download + report
├── docker-compose.yml
└── .env.example
```

---

## AI Guardrails

The AI layer enforces strict constraints to prevent fabrication:

| Prohibited | Allowed |
|---|---|
| Invent companies or job titles | Rewrite sentence structure |
| Add certifications not in original | Rearrange sections |
| Create fake projects | Improve action verbs |
| Change employment dates | Include JD keywords naturally |
| Modify education | Expand/condense bullet descriptions |

A **two-step hallucination guard** runs after every rewrite — any invented content is automatically reverted to the original.

---

## ATS Scoring Model

Our ATS score is a 6-signal weighted model grounded in research on Workday, Taleo, Greenhouse, and Lever:

| Signal | Max | Basis |
|---|---|---|
| Keyword Match | 30 | Hard + soft keyword presence |
| Section Completeness | 20 | Standard sections present and labeled |
| Format Parsability | 20 | No tables/text boxes in main content, single column |
| Keyword Placement | 15 | Keywords in summary/skills carry more weight |
| Date Consistency | 10 | Consistent format, reverse chronological |
| File Health | 5 | Text extractable, no garbled encoding |

> This score reflects general ATS compatibility, not any specific vendor's system.

---

## Sample Files

Sample inputs are in `/Required-documents/`:
- `Sample-Resumes/` — real resume PDFs for testing
- `JD-samples/` — real JD PDFs for testing
- `CV-templates/` — DOCX templates for testing

---

## License

For academic/assignment purposes only. Confidential.
