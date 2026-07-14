#!/bin/bash
export BACKEND_PORT=8002

cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ../data/logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "backend:$BACKEND_PID" > ./data/app.pid
echo "生产环境后端已启动（PID: $BACKEND_PID）"
