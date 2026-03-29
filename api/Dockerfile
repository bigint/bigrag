FROM python:3.12-slim AS base

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
COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install .

# Copy application code
COPY bigrag/ bigrag/

# Create data directory
RUN mkdir -p /data/uploads && \
    useradd -r -s /bin/false bigrag && \
    chown -R bigrag:bigrag /data

USER bigrag

EXPOSE 8080

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["python", "-m", "bigrag.main"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
