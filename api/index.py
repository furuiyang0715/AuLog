import sys
from pathlib import Path

# 保证 Vercel Serverless 能 import 项目根目录下的 app 包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="off")
