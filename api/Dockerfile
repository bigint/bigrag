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
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY bigrag/ bigrag/
RUN pip install --no-cache-dir .

# Strip heavy unnecessary files from the venv
RUN SITE=/opt/venv/lib/python3.12/site-packages \
    # Remove sympy/mpmath (torch dep only for symbolic tracing, not inference) \
    && pip uninstall -y sympy mpmath \
    # Remove test dirs, caches, bytecode \
    && find /opt/venv -depth -type d \( -name "tests" -o -name "test" -o -name "__pycache__" \) -exec rm -rf {} + \
    && find /opt/venv \( -name "*.pyc" -o -name "*.pyo" \) -delete \
    # Torch: remove C++ headers and CMake files (not needed at runtime) \
    && rm -rf $SITE/torch/include $SITE/torch/share \
    # Torch: remove test .so files \
    && rm -f $SITE/torch/lib/libtorchbind_test.so \
             $SITE/torch/lib/libjitbackend_test.so \
             $SITE/torch/lib/libbackend_with_compiler.so \
             $SITE/torch/lib/libaoti_custom_ops.so \
    # Strip debug symbols from shared libraries \
    && find /opt/venv -name "*.so*" -exec strip --strip-unneeded {} + 2>/dev/null \
    ; true

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

EXPOSE 6100
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:6100/health || exit 1

ENTRYPOINT ["python", "-m", "bigrag.main"]
CMD ["--host", "0.0.0.0", "--port", "6100"]
