FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY shared/ ./shared/
COPY services/consumer/ ./service/

RUN uv pip install --system --no-cache ./shared ./service

CMD ["python", "-m", "consumer.main"]
