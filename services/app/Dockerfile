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

# Fail the build if the CLI is not runnable. The npm package ships a stub at
# bin/claude.exe that its postinstall replaces with the native binary for this
# platform; if that step is skipped the stub stays in place — a JS file with a
# .exe extension — and every invocation dies with ERR_UNKNOWN_FILE_EXTENSION.
RUN claude --version

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r studyaio && useradd -r -g studyaio -d /app -s /sbin/nologin studyaio

# === Bake the sentence-transformers embedding model into the image ===
#
# Why bake it. The api container runs as `studyaio`, whose home is `/app`, which
# is root-owned — so sentence-transformers could not create a model cache and
# every embedding call in the API process failed: `POST /api/qa` returned 500,
# and chat caught the same error and answered with no lecture context at all,
# silently, for six months (issue #44). The worker was only ever working by
# accident, because docker-compose.yml gives it uid 0 for the Claude credential
# mounts. A world-readable cache populated at build time fixes the api without
# granting it write access or root — read access is all a warm cache needs —
# and takes the Hugging Face download off the runtime start path for both
# containers, which is a network dependency the pipeline should not have.
#
# Why HF_HOME, and only HF_HOME. sentence-transformers 3.4.1 reads
# SENTENCE_TRANSFORMERS_HOME into its `cache_folder` (SentenceTransformer.py
# lines 205-206) and, when that is unset, hands `cache_dir=None` to
# huggingface_hub, which resolves `$HF_HOME/hub` (huggingface_hub/constants.py
# lines 129-151). So HF_HOME alone governs, and it is the variable the rest of
# the HF stack honours too. Setting both would give sentence-transformers a
# *different* cache root (`$HF_HOME`) from every other huggingface_hub caller
# (`$HF_HOME/hub`): one model, two caches, and only whichever the build happened
# to populate would be warm.
ENV HF_HOME=/opt/models

# The model name is read from the app's own default so the bake and the runtime
# loader cannot drift apart. It comes off the field default rather than an
# instantiated Settings, so the build needs no environment; and only config.py
# is copied, because the full source arrives further down and this layer must
# not be invalidated — i.e. the model re-downloaded — by every source edit.
COPY app/__init__.py app/config.py /tmp/bake/app/

# Instantiating SentenceTransformer is what populates the cache, and that is
# deliberate: it lays the files out exactly as the runtime loader expects to
# find them. Copying files into place by hand would be a guess about
# huggingface_hub's cache layout, and a guess of precisely that kind is what
# produced this bug.
RUN set -eux; \
    PYTHONPATH=/tmp/bake python -c 'from app.config import Settings; print(Settings.model_fields["embedding_model"].default)' > /tmp/bake/model; \
    printf '%s\n' \
      'from pathlib import Path' \
      'from sentence_transformers import SentenceTransformer' \
      'name = Path("/tmp/bake/model").read_text().strip()' \
      'model = SentenceTransformer(name)' \
      'print("embedding model loaded:", name, model.get_sentence_embedding_dimension())' \
      > /tmp/bake/load.py; \
    python /tmp/bake/load.py; \
    chmod -R a+rX "$HF_HOME"

# Serve the baked cache and nothing else. Without this, huggingface_hub still
# HEADs huggingface.co on every load to check the revision — so the download is
# gone but the network dependency is not, and when the Hub is unreachable the
# retry ladder (1s, 2s, 4s, 8s, 8s, per file) stalls the load for ~3 minutes
# before it falls back to the cache it already had. Measured in this image:
# 3s online, 197s with --network none, identical vectors either way. Three
# minutes is longer than the api's healthcheck tolerates, so an outage at
# Hugging Face would have turned into a restart loop here.
#
# Offline also makes the bake a real pin: the image ships one revision and uses
# it, rather than silently following whatever `main` becomes.
#
# It is an ENV, not a hardcode, precisely so the escape hatch stays open: an
# operator overriding EMBEDDING_MODEL to something not baked here must also set
# HF_HUB_OFFLINE=0, and gets the runtime download back — in the worker, which
# runs as root. It still cannot work in the api, which cannot write a cache.
# See the note beside EMBEDDING_MODEL in .env.example.
ENV HF_HUB_OFFLINE=1

# Fail the build if the baked cache is not usable — offline — by the user the
# api actually runs as. Without this the bake is unverifiable until deploy: CI
# does not build this image on pull requests, so nothing else would notice a
# cache that came out root-only, or an HF_HOME the loader does not consult.
# `su` drops to studyaio, whose HOME is the unwritable /app: the exact condition
# that broke production.
RUN su -s /bin/sh studyaio -c 'python /tmp/bake/load.py' \
    && rm -rf /tmp/bake

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
