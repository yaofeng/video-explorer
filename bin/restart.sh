#!/bin/bash
set -euo pipefail

# 切到仓库根目录（基于脚本自身位置），保证可从任意 cwd 执行（L7）
cd "$(dirname "$0")/.."

./bin/stop.sh
sleep 2
./bin/start.sh
