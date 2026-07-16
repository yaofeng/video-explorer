#!/bin/bash
set -euo pipefail

# 切到仓库根目录（基于脚本自身位置），保证可从任意 cwd 执行（L7）
cd "$(dirname "$0")/.."

# 构建前端
cd frontend
export PATH="$HOME/.bun/bin:$PATH"
bun run build
cd ..

# 复制到后端静态资源
rm -rf backend/app/static
cp -r frontend/dist backend/app/static

echo "前端已构建并复制到 backend/app/static"
