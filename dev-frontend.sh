#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"

if [ ! -d node_modules ]; then
  echo "首次运行，正在安装前端依赖..."
  npm install
fi

npm run dev
