# TPDL Lead Intelligence — production container for Azure App Service.
#
# Build:  docker build -t tpdl-intel .
# Run:    docker run -p 8000:8000 --env-file .env tpdl-intel
#
# One worker on purpose: the app runs an in-process APScheduler and holds
# WebSocket/realtime state in memory, so multiple workers would double-fire
# scheduled jobs and split the live state. A single async uvicorn worker
# comfortably serves the whole team for this workload.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System deps: build tools for wheels that need them (kept minimal).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Azure App Service probes the port from WEBSITES_PORT; we listen on $PORT.
EXPOSE 8000

# gunicorn as the process manager, one uvicorn async worker (see note above).
# --timeout 120 covers the longest Claude/agent calls without a worker kill.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:${PORT} --timeout 120 --access-logfile - --error-logfile -"]
