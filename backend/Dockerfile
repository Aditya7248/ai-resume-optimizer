FROM python:3.11-slim

# Install system dependencies: LibreOffice for DOCX→PDF, poppler for PDF utils
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    poppler-utils \
    fonts-liberation \
    fonts-dejavu \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# LibreOffice needs a home directory to write temp files
ENV HOME=/tmp

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
