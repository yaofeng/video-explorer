#!/bin/bash
export BACKEND_PORT=8002

# 启动后端（开发模式）
cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ../data/logs/backend-dev.log 2>&1 &
BACKEND_PID=$!
cd ..

# 启动前端（开发模式）
cd frontend
export PATH="$HOME/.bun/bin:$PATH"
nohup bun run dev > ../data/logs/frontend-dev.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 写入 PID
echo "backend:$BACKEND_PID" > ./data/app.pid
echo "frontend:$FRONTEND_PID" >> ./data/app.pid

echo "开发服务器已启动（后端 PID: $BACKEND_PID，前端 PID: $FRONTEND_PID）"
