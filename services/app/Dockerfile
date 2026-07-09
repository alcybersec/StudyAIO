# === Stage 1: Builder — install Python dependencies ===
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to compile Python packages (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# === Stage 2: Runtime — lean image, no build tools ===
FROM python:3.12-slim AS runtime

WORKDIR /app

# Only runtime C libs (no compiler, no headers)
# nodejs + npm needed for Claude Code CLI
# libreoffice-{impress,writer} render PPTX/DOCX to PDF for inline preview.
# Fonts: liberation (Arial/Times/Courier metrics), carlito (=Calibri) and
# caladea (=Cambria) so Office decks substitute with matching glyph widths —
# without these, LibreOffice picks a mismatched fallback and text renders gappy.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    nodejs \
    npm \
    libreoffice-impress \
    libreoffice-writer \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-dejavu-core \
    && fc-cache -f \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r studyaio && useradd -r -g studyaio -d /app -s /sbin/nologin studyaio

# OCI image labels
LABEL org.opencontainers.image.source="https://github.com/alcybersec/StudyAIO"
LABEL org.opencontainers.image.description="StudyAIO API + Celery worker"
LABEL org.opencontainers.image.licenses="MIT"

COPY . .

# Ensure data dir is writable by studyaio
RUN mkdir -p /app/data && chown -R studyaio:studyaio /app/data

USER studyaio

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
