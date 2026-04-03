FROM node:22-alpine AS ui-build

RUN corepack enable && corepack prepare pnpm@latest --activate

# Build the TypeScript SDK
WORKDIR /sdks/typescript
COPY sdks/typescript/ .
RUN pnpm install && pnpm build

# Build the UI
WORKDIR /ui
COPY ui/package.json ui/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile
COPY ui/ .
ENV NEXT_PUBLIC_BIGRAG_URL=""
RUN pnpm build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system deps for docling (poppler for PDF, tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY api/pyproject.toml .
COPY api/bigrag/ bigrag/
RUN pip install --upgrade pip && \
    pip install .

# Copy UI static build
COPY --from=ui-build /ui/out /app/ui

# Create data directory
RUN mkdir -p /data/uploads && \
    useradd -r -s /bin/false bigrag && \
    chown -R bigrag:bigrag /data

USER bigrag

EXPOSE 6000

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:6000/health || exit 1

ENTRYPOINT ["python", "-m", "bigrag.main"]
CMD ["--host", "0.0.0.0", "--port", "6000"]
