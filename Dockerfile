FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --upgrade pip && \
  pip install -r requirements.txt

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
