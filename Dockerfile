FROM node:24-slim AS frontend
RUN npm install -g pnpm@11.19.0
WORKDIR /build
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY --from=frontend /build/dist web/dist/
RUN useradd --create-home folio && mkdir -p data/documents && chown -R folio:folio /app
USER folio
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
