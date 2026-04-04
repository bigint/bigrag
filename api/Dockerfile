FROM python:3.12-slim AS build

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install CPU-only PyTorch first (avoids pulling ~2GB CUDA bundles)
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
COPY bigrag/ bigrag/
RUN pip install .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /data/uploads && \
    useradd -r -m -s /bin/false bigrag && \
    chown -R bigrag:bigrag /data /home/bigrag

USER bigrag

EXPOSE 6000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:6000/health || exit 1

ENTRYPOINT ["python", "-m", "bigrag.main"]
CMD ["--host", "0.0.0.0", "--port", "6000"]
