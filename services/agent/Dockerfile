FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl libatomic1 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY sherpa ./sherpa
RUN pip install . && pip install --no-deps paypal-agent-toolkit==1.11.0 python-dotenv==1.0.1
# Fail the build, not a live run, if Playwright's driver can't start (it needs libatomic1, among others).
RUN python -m playwright --version

ENV PORT=8080
CMD exec uvicorn sherpa.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers
