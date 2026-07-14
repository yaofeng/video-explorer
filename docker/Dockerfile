# 阶段 1：构建前端（使用 bun）
FROM oven/bun:1 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# 阶段 2：后端（使用 uv）
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY backend/requirements.txt backend/
RUN uv pip install --system -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist backend/app/static/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
