FROM node:22-bookworm-slim AS node
FROM ubuntu:24.04
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends asterisk python3 python3-venv espeak-ng ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/voice
COPY phone/requirements.txt /tmp/requirements.txt
RUN /opt/voice/bin/pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app
COPY server.mjs faq.json ./
COPY phone ./phone
ENV PATH="/opt/voice/bin:$PATH" PYTHONUNBUFFERED=1 HF_HOME=/models/huggingface OLLAMA_URL=http://host.docker.internal:11434
RUN chmod +x /app/phone/call_id.py
CMD ["python", "phone/launch.py"]
