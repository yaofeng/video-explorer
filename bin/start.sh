#!/bin/bash
set -euo pipefail

# 切到仓库根目录（基于脚本自身位置），保证可从任意 cwd 执行（L7）
cd "$(dirname "$0")/.."

export BACKEND_PORT=8002

cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ../data/logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "backend:$BACKEND_PID" > ./data/app.pid
echo "生产环境后端已启动（PID: $BACKEND_PID）"
