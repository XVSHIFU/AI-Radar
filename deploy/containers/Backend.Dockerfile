FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend/src:/app/backend
WORKDIR /app/backend
COPY deploy/containers/backend-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt && rm /tmp/requirements.txt
RUN groupadd -g 10001 radar && useradd -u 10001 -g radar -M -d /nonexistent radar \
    && install -d -o radar -g radar -m 0700 /var/lib/radar-model /run/radar-service-locks /run/radar-control \
    && install -d -m 0755 /opt/ai-radar/gvisor/20260907.0
COPY backend/src ./src
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY agent/research /app/agent/research
USER 10001:10001
ENTRYPOINT ["python", "-m", "radar.container_entry"]
CMD ["api"]

FROM docker:28.5.2-cli@sha256:625d9431a9f54c5a2bc90f24f0e1c3d55b1349fd857dd85035f98c2c9acbdd4d AS docker-cli
FROM backend AS controller
COPY --from=docker-cli /usr/local/bin/docker /usr/bin/docker
ENTRYPOINT ["python", "-m", "radar.sandbox_container"]
CMD []
