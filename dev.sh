#!/usr/bin/env bash
# 同时启动后端 (uvicorn) 和前端 (vite)。Ctrl+C 会一起停掉。
set -e
cd "$(dirname "$0")"

trap 'kill $(jobs -p) 2>/dev/null; wait' EXIT INT TERM

./run.sh &
./dev-frontend.sh &
wait
