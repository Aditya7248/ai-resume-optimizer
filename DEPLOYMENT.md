# Deployment Guide

## Local (Docker Compose) — Recommended for MVP

```bash
# 1. Copy env file
cp .env.example .env

# 2. Add your API key to .env
OPENAI_API_KEY=sk-your-key-here

# 3. Build and start
docker-compose up --build

# 4. Access
# Frontend:  http://localhost:3000
# API:       http://localhost:8000
# Swagger:   http://localhost:8000/docs
```

### Stop
```bash
docker-compose down
```

### Rebuild after code changes
```bash
docker-compose up --build --force-recreate
```

---

## Manual Local (No Docker)

### Backend
```bash
cd backend

# Install LibreOffice (required for PDF conversion)
# macOS:
brew install libreoffice
# Ubuntu/Debian:
sudo apt-get install libreoffice

# Python setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
OPENAI_API_KEY=sk-your-key uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Notes

- All resume data is processed in-memory — no database, no persistent PII storage
- Session data lives in the backend process memory for the duration of the session
- Output files are written to `/tmp/resume-optimizer/{session_id}/` and persist only for the server process lifetime
- For production deployment, replace the in-memory session store with Redis
