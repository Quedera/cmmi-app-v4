FROM python:3.11-slim AS base

# QUEDERA Pulse (cmmi-app-v4) backend — FastAPI + uvicorn + aiosqlite.
# Mirrors cmmi-app/backend/Dockerfile but uses cmmi_v4.sqlite as the seed
# filename and the Azure Files mount target. v4 = rebranded ITSM Assessment.

WORKDIR /app

# Install pip dependencies first (cache layer)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Bake the seed database (the rebranded / ITSM-scrubbed Pulse dataset) into
# the image so a fresh container can serve traffic immediately. On first start,
# the entrypoint copies it into /app/data/cmmi_v4.sqlite — the Azure Files
# mount target in prod.
RUN mkdir -p /app/seed /app/data
COPY backend/cmmi_v4.sqlite /app/seed/cmmi_v4.sqlite

# Environment
ENV PYTHONPATH=/app
ENV CMMI_DB_PATH=/app/data/cmmi_v4.sqlite
ENV PORT=8000

# Entrypoint: seed DB if missing, then exec the CMD
COPY backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Health check (Azure liveness probe uses this)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]