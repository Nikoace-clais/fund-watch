# ---- 前端构建 ----
# 钉 minor(bun 1.3.x),patch 随官方滚动
FROM oven/bun:1.3 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# 空串 = 同源相对路径(api-client.ts 以 ?? 回落,仅未设置时才用 dev 地址)
ENV VITE_API_URL=""
RUN bun run build

# ---- 后端运行时 ----
# 钉 minor + Debian 代号(python 3.12 + bookworm),patch 随官方滚动,升级大版本需人工
# ponytail: 仅 linux/amd64;paddle 的 aarch64 轮子情况不明,NAS 若是 ARM 再加多架构
FROM python:3.12-slim-bookworm
# uv 钉具体版本,升级需手动改这里
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
# libgomp1: paddlepaddle 运行依赖;libglib2.0-0: opencv-headless 运行依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# 非 root 运行(uid/gid 1000);PaddleOCR 首次运行把模型下载到 $HOME,必须可写
RUN groupadd --gid 1000 fundwatch \
    && useradd --uid 1000 --gid fundwatch --create-home --shell /usr/sbin/nologin fundwatch
WORKDIR /app/backend
# 先只拷锁文件装依赖,让 paddle 大层独立缓存;项目本身不安装(直接以 cwd 运行 app/)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
# 前端静态产物;main.py 检测到 backend/static/ 存在时挂载并做 SPA fallback
COPY --from=frontend /build/dist ./static
# SQLite + 上传截图都在 data/ 下;bind mount 会覆盖此处属主,host 侧要求见 compose 注释
RUN mkdir -p /app/backend/data && chown -R fundwatch:fundwatch /app/backend/data
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER fundwatch
EXPOSE 8010
# 镜像内无 curl,用 python 探测;PaddleOCR 首次下载模型较慢,start-period 给足 120s
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8010/api/health',timeout=5)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
