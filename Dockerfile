FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG INSTALL_EMBEDDING_STACK=0
ARG INSTALL_CELERY_STACK=0

COPY requirements.txt ./requirements.txt
COPY requirements-embeddings.txt ./requirements-embeddings.txt
COPY requirements-celery.txt ./requirements-celery.txt

RUN pip install --upgrade pip && \
  pip install -r requirements.txt && \
  if [ "$INSTALL_EMBEDDING_STACK" = "1" ]; then pip install -r requirements-embeddings.txt; fi && \
  if [ "$INSTALL_CELERY_STACK" = "1" ]; then pip install -r requirements-celery.txt; fi

COPY api ./api
COPY static ./static
COPY templates ./templates
COPY data ./data
COPY docs ./docs
COPY scripts ./scripts
COPY docker ./docker
COPY README.md ./
COPY .env.example ./.env.example

EXPOSE 8000

CMD ["sh", "/app/docker/app/entrypoint.sh"]
