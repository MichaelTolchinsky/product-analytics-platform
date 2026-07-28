FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY shared/ ./shared/
COPY services/serving/ ./service/
COPY dashboard/ ./dashboard/

RUN uv pip install --system --no-cache ./shared ./service

CMD ["uvicorn", "serving.main:app", "--host", "0.0.0.0", "--port", "8001"]
