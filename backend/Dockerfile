FROM node:22-bookworm-slim AS base-build

WORKDIR /opt/flowpilot-base
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY integrations/base/package.json integrations/base/package-lock.json ./
RUN npm ci --ignore-scripts --omit=dev --no-audit --no-fund
COPY integrations/base/workspace ./workspace
RUN npm run validate && npm test

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BASE_RUNTIME_DIRECTORY=/opt/flowpilot-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=base-build /usr/local/bin/node /usr/local/bin/node
COPY --from=base-build /opt/flowpilot-base/node_modules /opt/flowpilot-base/node_modules
COPY integrations/base/package.json integrations/base/package-lock.json integrations/base/runtime.mjs /opt/flowpilot-base/
COPY integrations/base/workspace /opt/flowpilot-base/workspace
COPY backend/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
