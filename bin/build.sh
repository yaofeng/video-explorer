#!/bin/bash

# 构建前端
cd frontend
export PATH="$HOME/.bun/bin:$PATH"
bun run build
cd ..

# 复制到后端静态资源
rm -rf backend/app/static
cp -r frontend/dist backend/app/static

echo "前端已构建并复制到 backend/app/static"
