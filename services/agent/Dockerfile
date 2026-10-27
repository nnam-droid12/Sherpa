FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY sherpa ./sherpa
RUN pip install . && pip install --no-deps paypal-agent-toolkit==1.11.0 python-dotenv==1.0.1

ENV PORT=8080
CMD exec uvicorn sherpa.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers
