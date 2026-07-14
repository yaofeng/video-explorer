#!/bin/bash
set -e
source .env
DATA_PATH=${DATA_PATH:-.}

cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ${DATA_PATH}/logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "backend:$BACKEND_PID" > ${DATA_PATH}/app.pid
echo "生产环境后端已启动（PID: $BACKEND_PID）"
