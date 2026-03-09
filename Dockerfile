# Stage 1: Builder – install dependencies only
FROM python:3.9-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies (exclude test/dev)
RUN grep -v "^#" requirements.txt | grep -v "pytest" | grep -v "mypy" | grep -v "types-" > requirements-runtime.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-runtime.txt

# Stage 2: Runtime – minimal image, no build tools
FROM python:3.9-slim AS runtime

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code (no tests, no dev tools)
COPY downloader/ ./downloader/
COPY uploader/ ./uploader/
COPY resizer/ ./resizer/
COPY utils/ ./utils/
COPY run.py config.py ./

RUN mkdir -p /app/shared

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "run.py"]
