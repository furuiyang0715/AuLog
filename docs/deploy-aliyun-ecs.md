# AuLog 阿里云 ECS 部署指南

本文档适用于在**中国大陆阿里云 ECS** 上部署 AuLog，使用 **IP + 端口** 访问（暂不绑定域名、暂不 ICP 备案）。

| 项 | 值 |
|---|---|
| 服务器项目路径 | `/root/AuLog` |
| 推荐系统 | Ubuntu 22.04 / 24.04 / 26.04 LTS |
| Python | **3.12**（推荐，via deadsnakes）；Ubuntu 26.04 自带 3.14 会导致 pip 编译极慢 |
| Web 端口 | `18888` |
| 数据库 | Docker 运行 MongoDB 7，仅本机访问 |

---

## 架构概览

```text
公网浏览器
    ↓  http://<公网IP>:18888
阿里云安全组（放行 18888）
    ↓
uvicorn (FastAPI)
    ├── /          → Vue 静态页 (static/dist)
    └── /api/*     → 后端 API
    ↓
MongoDB (Docker, 127.0.0.1:27017)
```

---

## 0. 阿里云安全组

AuLog 默认监听 **18888** 端口。外网访问前必须在安全组放行该端口。

### 0.1 控制台添加规则（逐步操作）

1. 登录 [阿里云 ECS 控制台](https://ecs.console.aliyun.com/)
2. 左侧 **实例与镜像** → **实例**，找到你的服务器（如 `iZbp1cy0hep7dcgfzpggcgZ`）
3. 点击实例 ID 进入详情页
4. 打开 **安全组** 标签页 → 点击已绑定的**安全组 ID**（蓝色链接）
5. 切到 **入方向** → **手动添加**（或 **快速添加**）
6. 填写：

| 配置项 | 填写值 |
|--------|--------|
| 授权策略 | 允许 |
| 优先级 | 1（数字越小越优先） |
| 协议类型 | 自定义 TCP |
| 端口范围 | `18888/18888` |
| 授权对象 | `0.0.0.0/0`（任意 IP；仅自己用时填你的公网 IP/32） |
| 描述 | AuLog Web |

7. 点击 **保存**

> 若实例绑定了**多个安全组**，每个都可能生效；至少要在**当前实例关联的安全组**里添加上述规则。

**快速添加** 方式：勾选 **HTTP(80)** 旁的自定义，或选「自定义 TCP」，端口填 `18888`。

### 0.2 规则参考

| 端口 | 协议 | 授权对象 | 说明 |
|------|------|----------|------|
| 22 | TCP | 你的本机公网 IP/32 | SSH，尽量限制来源 |
| 18888 | TCP | `0.0.0.0/0` 或指定 IP | AuLog Web 服务 |

**切勿**对公网开放 `27017`（MongoDB）。

### 0.3 放行后仍不通：服务器侧排查

在 SSH 里依次检查：

```bash
# 1. 服务是否在跑、是否监听 18888
systemctl status aulog          # 若已配 systemd
ss -tlnp | grep 18888
# 或试跑时：uvicorn 应 --host 0.0.0.0 --port 18888

# 2. 本机能否访问（在服务器上执行）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18888/

# 3. 系统防火墙（Ubuntu 若启用了 ufw）
ufw status
# 若 active，需放行：
# ufw allow 18888/tcp
```

| 检查项 | 正常表现 |
|--------|----------|
| `ss -tlnp \| grep 18888` | 有 `0.0.0.0:18888` 或 `*:18888` |
| 本机 `curl 127.0.0.1:18888` | 返回 `200` 或 HTML |
| 浏览器 `http://公网IP:18888` | 能打开页面 |

本机 curl 正常、外网仍不通 → 几乎一定是**安全组或授权对象**问题，回到 **0.1** 核对。

---

## 1. SSH 登录与系统更新

```bash
ssh root@<公网IP>

apt update && apt upgrade -y
apt install -y git curl ca-certificates
```

确认系统与 Python 版本：

```bash
cat /etc/os-release
python3 --version
```

Ubuntu 26.04 自带 `Python 3.14.x`，但 **不建议直接用于本项目**（见第 3、6 节）。22.04 / 24.04 若已是 3.10+，可直接用系统 `python3`。

---

## 2. 安装 Docker（运行 MongoDB）

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

docker --version
docker compose version
```

---

## 3. 安装 Python 3.12、Node.js

> **为何用 3.12？** Ubuntu 26.04 自带 Python 3.14 过新，`pymongo`、`pydantic-core` 等往往没有预编译 wheel，pip 会从源码编译，耗时 **5～15 分钟甚至更久**。Python 3.12 可直接下载 wheel，通常 **1～2 分钟** 装完。

### 3.1 安装 Python 3.12（推荐）

```bash
apt update
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.12 python3.12-venv python3.12-dev

python3.12 --version
# 期望：Python 3.12.x
```

Ubuntu 22.04 / 24.04 若系统 `python3 --version` 已是 **3.10+**，可跳过 3.1，改用 `python3` 创建虚拟环境。

### 3.2 安装 Node.js（构建前端）

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

node --version
npm --version
```

### 3.3 配置 pip 镜像（可选）

阿里云 ECS 通常已自动使用内网源 `mirrors.cloud.aliyuncs.com`。可手动确认：

```bash
pip config set global.index-url http://mirrors.cloud.aliyuncs.com/pypi/simple/
pip config set install.trusted-host mirrors.cloud.aliyuncs.com
```

> 换镜像只能加速**下载**，无法避免 Python 3.14 下的**源码编译**；根本解决办法仍是使用 **3.12**。

---

## 4. 获取项目代码

### 方式 A：Git 克隆（推荐）

```bash
cd /root
git clone <你的仓库地址> AuLog
cd /root/AuLog
```

### 方式 B：本地上传

在本地电脑执行：

```bash
scp -r ./AuLog root@<公网IP>:/root/AuLog
```

然后在服务器上：

```bash
cd /root/AuLog
```

---

## 5. 启动 MongoDB（Docker Compose）

### 5.1 限制 MongoDB 仅本机访问（必做）

编辑 `/root/AuLog/docker-compose.yml`，将 `ports` 改为：

```yaml
services:
  mongodb:
    image: mongo:7
    ports:
      - "127.0.0.1:27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

### 5.2 启动容器

```bash
cd /root/AuLog
docker compose up -d

docker compose ps
docker compose logs mongodb
```

### 5.3 验证 MongoDB

> `mongosh` 在 **Docker 容器内**，宿主机未安装时会报 `command not found`，请用 `docker exec` 执行。

在服务器上执行：

```bash
docker compose ps

docker exec -it aulog-mongodb-1 mongosh --eval "db.runCommand({ ping: 1 })"
```

若容器名不同，先查再执行：

```bash
docker ps
docker exec -it $(docker ps -qf "ancestor=mongo:7") mongosh --eval "db.runCommand({ ping: 1 })"
```

期望返回 `{ ok: 1 }`。

### 5.4 确认端口仅绑定本机（建议）

```bash
ss -tlnp | grep 27017
```

- 若看到 `127.0.0.1:27017` → 正常
- 若是 `0.0.0.0:27017` → 按 **5.1** 修改 `docker-compose.yml` 中的 `ports` 为 `127.0.0.1:27017:27017`，然后：

```bash
cd /root/AuLog
docker compose down
docker compose up -d
```

### 5.5 Docker 拉取镜像超时（大陆 ECS 常见）

若出现类似报错：

```text
failed to resolve reference "docker.io/library/mongo:7": dial tcp ...:443: i/o timeout
```

说明服务器访问 **Docker Hub** 超时。按下面顺序处理。

#### 方案 A：配置阿里云镜像加速器（推荐）

1. 登录 [阿里云控制台](https://cr.console.aliyun.com/) → **容器镜像服务** → **镜像工具** → **镜像加速器**
2. 复制你的专属加速器地址（形如 `https://xxxxxx.mirror.aliyuncs.com`）
3. 在服务器执行：

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://你的加速器地址.mirror.aliyuncs.com"
  ]
}
EOF

systemctl daemon-reload
systemctl restart docker

cd /root/AuLog
docker compose up -d
```

#### 方案 B：DaoCloud 镜像站手动拉取

> 注意：`registry.cn-hangzhou.aliyuncs.com/library/mongo` **已不可用**，不要再用该地址。

```bash
docker pull docker.m.daocloud.io/library/mongo:7
docker tag docker.m.daocloud.io/library/mongo:7 mongo:7

cd /root/AuLog
docker compose up -d
```

或直接把 `docker-compose.yml` 里的镜像改为：

```yaml
image: docker.m.daocloud.io/library/mongo:7
```

#### 方案 C：不用 Docker，本机安装 MongoDB（最稳）

Docker 镜像始终拉不下来时，推荐直接用 apt 安装：

```bash
apt install -y gnupg curl

curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Ubuntu 26.04 暂无官方源，用 noble(24.04) 源通常可安装
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/7.0 multiverse" | \
  tee /etc/apt/sources.list.d/mongodb-org-7.0.list

apt update
apt install -y mongodb-org
```

限制 MongoDB 只监听本机（安全）：

```bash
grep bindIp /etc/mongod.conf
# 确认 net.bindIp 为 127.0.0.1；若是 0.0.0.0，执行：
sed -i 's/bindIp: 0.0.0.0/bindIp: 127.0.0.1/' /etc/mongod.conf

systemctl enable mongod
systemctl start mongod
systemctl status mongod
```

验证：

```bash
mongosh --eval "db.runCommand({ ping: 1 })"
```

`.env` 仍使用：

```env
MONGODB_URI=mongodb://127.0.0.1:27017
```

此方式跳过 `docker compose`，其余部署步骤不变。

---

## 6. Python 虚拟环境与依赖

```bash
cd /root/AuLog

python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

若系统 Python 为 3.10+ 且未安装 3.12，将上面 `python3.12` 换成 `python3` 即可。

安装完成后确认：

```bash
python --version
pip list | grep -E "fastapi|pydantic|pymongo"
```

### 6.1 pip 安装极慢或卡在 `Preparing metadata`

**原因**：使用了 Python 3.14，部分依赖（如 `pydantic-core`、`pymongo`）无 wheel，需本地编译。

**方案 A（推荐）：改用 Python 3.12 重建虚拟环境**

```bash
# 若 pip 仍在运行，先 Ctrl+C 停掉

apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.12 python3.12-venv python3.12-dev

cd /root/AuLog
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

systemd 中 `ExecStart` 路径仍为 `/root/AuLog/.venv/bin/uvicorn`，无需修改。

**方案 B：坚持用 Python 3.14，安装编译依赖后等待**

```bash
apt install -y python3-dev build-essential rustc cargo libssl-dev

cd /root/AuLog
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install --prefer-binary -r requirements.txt
```

`pydantic-core` 编译仍可能需 **5～15 分钟**，属正常现象。

| 方式 | 速度 | 说明 |
|------|------|------|
| Python 3.12 + venv | ⭐⭐⭐ 最快 | 推荐，与项目 `runtime.txt` 一致 |
| Python 3.14 源码编译 | ⭐ 很慢 | 仅无法安装 3.12 时使用 |
| 更换 pip 镜像 | 几乎无提升 | ECS 内网源已足够 |

---

## 7. 环境变量 `.env`

```bash
cd /root/AuLog
cp .env.example .env
nano .env
```

生产环境建议配置：

```env
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB=aulog
HOST=0.0.0.0
PORT=18888
JWT_SECRET=<至少32位随机字符串>
JWT_EXPIRE_DAYS=7
```

生成随机 `JWT_SECRET`：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 8. 构建前端

> `npm ci` **必须在 `frontend` 目录下执行**，该目录才有 `package-lock.json`。

```bash
cd /root/AuLog/frontend
npm ci
npm run build
```

确认构建产物存在：

```bash
ls -la /root/AuLog/static/dist/
# 应包含 index.html 和 assets/
```

### 8.1 `npm ci` 报错 `package-lock.json`

**原因 1：当前目录不对**（最常见）

```bash
# 错误：在 /root/AuLog 根目录执行 npm ci
# 正确：
cd /root/AuLog/frontend
ls package-lock.json   # 应能看到该文件
npm ci
```

**原因 2：服务器上缺少 lock 文件**

```bash
cd /root/AuLog
git pull
ls frontend/package-lock.json
```

若仍不存在，改用 `npm install`（会按 package.json 生成 lock 并安装）：

```bash
cd /root/AuLog/frontend
npm install
npm run build
```

---

## 9. 手动试跑（确认后再配置 systemd）

```bash
cd /root/AuLog
source .venv/bin/activate
set -a && source .env && set +a

uvicorn app.main:app --host 0.0.0.0 --port 18888
```

浏览器访问：

```text
http://<公网IP>:18888
```

注册账号并测试基本功能。确认无误后按 `Ctrl+C` 停止，继续下一步。

### 快速自检（另开 SSH 窗口）

```bash
curl -s http://127.0.0.1:18888/ | head
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18888/api/auth/me
# 未登录时 /api/auth/me 返回 401 属正常
```

---

## 10. systemd 开机自启

创建服务文件：

```bash
nano /etc/systemd/system/aulog.service
```

写入以下内容：

```ini
[Unit]
Description=AuLog FastAPI Application
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/AuLog
EnvironmentFile=/root/AuLog/.env
ExecStart=/root/AuLog/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 18888
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
systemctl daemon-reload
systemctl enable aulog
systemctl start aulog
systemctl status aulog
```

查看日志：

```bash
journalctl -u aulog -f
```

常用命令：

```bash
systemctl restart aulog    # 重启应用
systemctl stop aulog       # 停止应用
journalctl -u aulog -n 50 # 最近 50 行日志
```

---

## 11. MongoDB 数据备份（建议）

```bash
mkdir -p /root/backups/mongodb

docker exec $(docker ps -qf "ancestor=mongo:7") \
  mongodump --archive --gzip > /root/backups/mongodb/aulog-$(date +%F).gz
```

每日自动备份（可选）：

```bash
crontab -e
```

添加一行：

```cron
0 3 * * * docker exec $(docker ps -qf "ancestor=mongo:7") mongodump --archive --gzip > /root/backups/mongodb/aulog-$(date +\%F).gz
```

---

## 12. 更新部署

代码有更新时：

```bash
cd /root/AuLog
git pull

source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm ci && npm run build && cd ..

systemctl restart aulog
```

---

## 常见问题

| 现象 | 排查 |
|------|------|
| 浏览器无法打开 / 18888 连接不通 | 安全组入方向放行 18888，见 **0.1～0.3 节** |
| 页面 404 / 空白 | 是否执行 `npm run build`；检查 `static/dist/index.html` |
| API 报错 / 500 | `journalctl -u aulog -n 50` 查看 Python 异常 |
| MongoDB 连接失败 | `docker compose ps`；`.env` 中 `MONGODB_URI` 是否为 `127.0.0.1` |
| `Unable to locate package python3.12` | Ubuntu 26.04 需先加 deadsnakes PPA，见 **3.1 / 6.1 节** |
| pip 安装极慢 / 卡在 metadata | Python 3.14 无 wheel 需编译；改用 **3.12**，见 **6.1 节** |
| pip 安装失败 | 贴出完整报错；3.14 下可试 **6.1 方案 B** 装编译依赖 |
| `mongo:7` 拉取 timeout | Docker Hub 超时；见 **5.5 节** 方案 A |
| `pull access denied` … `library/mongo` | 阿里云公共 `library/` 镜像已下线；用 **5.5 方案 B/C** |
| `mongosh: command not found` | 正常；在容器内执行，见 **5.3 节** |
| `npm ci` 找不到 package-lock.json | 先 `cd frontend`；见 **8.1 节** |

---

## 安全提醒

1. MongoDB 端口映射使用 `127.0.0.1:27017:27017`，安全组不要开放 27017。
2. `JWT_SECRET` 必须使用强随机值，不要用 `.env.example` 中的默认值。
3. SSH 建议改用密钥登录，并限制 22 端口来源 IP。
4. 当前为 **HTTP 明文**，适合 IP 临时访问；正式对外服务需域名 + HTTPS（大陆机房需 ICP 备案，或选用香港/海外实例）。

---

## 可选：后续接入域名与 HTTPS

完成 ICP 备案并绑定域名后，可安装 Nginx + Let's Encrypt：

- Nginx 对外监听 443
- uvicorn 改为只监听 `127.0.0.1:18888`
- 由 Nginx 反代 `/` 与 `/api`

此步骤需在备案完成后进行，本文暂不展开。

---

## 最小命令清单（速查）

```bash
# 依赖
apt update && apt upgrade -y
apt install -y git curl ca-certificates software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa && apt update
apt install -y python3.12 python3.12-venv python3.12-dev
curl -fsSL https://get.docker.com | sh
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs

# 代码（Git）
cd /root && git clone <仓库地址> AuLog && cd /root/AuLog

# MongoDB（先改 docker-compose.yml 绑定 127.0.0.1；镜像拉不下来见 5.5 节）
docker pull docker.m.daocloud.io/library/mongo:7
docker tag docker.m.daocloud.io/library/mongo:7 mongo:7
docker compose up -d

# Python（务必用 3.12）
python3.12 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
cp .env.example .env && nano .env

# 前端
cd frontend && npm ci && npm run build && cd ..

# 试跑
source .venv/bin/activate && set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 18888

# 常驻（配置 aulog.service 后）
systemctl daemon-reload && systemctl enable --now aulog
```
