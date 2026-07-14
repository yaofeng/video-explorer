#!/bin/bash
source .env
DATA_PATH=${DATA_PATH:-.}

if [ ! -f ${DATA_PATH}/app.pid ]; then
  echo "未找到 PID 文件"
  exit 0
fi

while IFS=: read -r role pid; do
  if kill -0 $pid 2>/dev/null; then
    kill $pid
    echo "已停止 $role（PID: $pid）"
  fi
done < ${DATA_PATH}/app.pid

rm -f ${DATA_PATH}/app.pid
