FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install .

EXPOSE 8000
CMD ["uvicorn", "resolveai.main:app", "--host", "0.0.0.0", "--port", "8000"]
