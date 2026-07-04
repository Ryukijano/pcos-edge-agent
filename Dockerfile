# PCOS Context Broker — Docker image
# FastAPI service for routing, planning, and Chrome↔Android relay

FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY broker/ ./broker/
COPY memory/ ./memory/
COPY tests/ ./tests/

# Environment defaults (override at runtime)
ENV PCOS_BROKER_HOST=0.0.0.0
ENV PCOS_BROKER_PORT=8000
ENV PCOS_CORS_ORIGINS=["*"]
ENV PCOS_DB_PATH=/data/pcos_metrics.db

# Create data directory for SQLite metrics
RUN mkdir -p /data
VOLUME /data

EXPOSE 8000

# Health check
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); exit(0 if r.status_code==200 else 1)"

# Run with uvicorn, single worker for WebSocket bridge compatibility
CMD ["uvicorn", "broker.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "auto"]
