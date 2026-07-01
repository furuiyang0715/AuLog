#!/usr/bin/env python3
"""本地测试 MongoDB 连接。在项目根目录 .env 配置 MONGODB_URI 后运行：python scripts/test_mongodb.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

uri = os.getenv("MONGODB_URI")
db_name = os.getenv("MONGODB_DB", "aulog")

if not uri:
    print("错误：未找到 MONGODB_URI。")
    print("请执行：cp .env.example .env")
    print("然后在 .env 中填入 Atlas 连接串。")
    sys.exit(1)

print(f"正在连接…（数据库名: {db_name}）")

try:
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    info = client.server_info()
    db = client[db_name]
    collections = db.list_collection_names()
    print("✓ 连接成功")
    print(f"  MongoDB 版本: {info.get('version')}")
    print(f"  数据库: {db_name}")
    print(f"  现有集合: {collections if collections else '(无，首次使用正常)'}")
except Exception as exc:
    print("✗ 连接失败")
    print(f"  {type(exc).__name__}: {exc}")
    print()
    print("常见原因：")
    print("  1. Atlas Network Access 未添加 0.0.0.0/0")
    print("  2. 用户名或密码错误（密码含特殊字符需 URL 编码）")
    print("  3. 本机网络无法访问 mongodb.net")
    sys.exit(1)
