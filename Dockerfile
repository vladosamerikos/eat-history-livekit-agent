# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libs nativas para audio (silero/onnx, opus, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY agent.py ./

# Pre-descarga del modelo Silero VAD para que el primer job sea rápido.
RUN python -c "from livekit.plugins import silero; silero.VAD.load()"

# El comando "start" lanza el worker que se registra contra LIVEKIT_URL
# (vía LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET en env).
ENTRYPOINT ["python", "agent.py"]
CMD ["start"]
