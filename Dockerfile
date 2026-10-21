FROM node:22-bookworm-slim AS frontend

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY web ./web
COPY fixtures/example-plan.txt ./fixtures/example-plan.txt
COPY tsconfig*.json vite.config.ts ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY server ./server
COPY fixtures ./fixtures
COPY LICENSE README.md ./
COPY --from=frontend /app/web/dist ./web/dist

EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn server.main:app --host 0.0.0.0 --port ${PORT}"]
