FROM python:3.13.14-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --no-cache-dir --root-user-action=ignore \
        -r /app/requirements.txt \
    && groupadd --gid 10001 airmonitor \
    && useradd --uid 10001 --gid airmonitor --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin airmonitor

COPY --chown=10001:10001 app /app/app
COPY --chown=10001:10001 alembic /app/alembic
COPY --chown=10001:10001 alembic.ini /app/alembic.ini
COPY --chown=10001:10001 --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
