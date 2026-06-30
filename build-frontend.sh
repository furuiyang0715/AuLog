#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"
npm install
npm run build
echo "前端已构建到 static/dist，重启后端后访问 http://<本机IP>:${PORT:-18888}（局域网可用）"
