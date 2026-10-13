FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_DIR=/app/storage

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY requirements.txt requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN pip install -r requirements.txt && \
    if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

COPY . .
# Storage gehört dem App-User; ein benanntes Volume übernimmt diese Rechte beim ersten Anlegen
RUN mkdir -p /app/storage/images /app/storage/documents && \
    chown -R app:app /app/storage && \
    chmod +x /app/docker-entrypoint.sh

USER app
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
