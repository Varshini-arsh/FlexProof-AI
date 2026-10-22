FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
ENV VITE_API_BASE_URL=/api
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY simulator ./simulator
COPY optimization ./optimization
COPY baselines ./baselines
COPY evaluation ./evaluation
COPY flexproof ./flexproof
COPY contracts ./contracts
COPY configs ./configs
COPY backend ./backend
RUN pip install --no-cache-dir ".[api]"
COPY --from=frontend /frontend/dist ./frontend_dist
RUN mkdir -p /app/data && chmod 777 /app/data
ENV FLEXPROOF_DB_PATH=/app/data/flexproof_runs.sqlite3
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
