# ---- 前端构建 ----
FROM oven/bun:1 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# 空串 = 同源相对路径(api-client.ts 以 ?? 回落,仅未设置时才用 dev 地址)
ENV VITE_API_URL=""
RUN bun run build

# ---- 后端运行时 ----
# ponytail: 仅 linux/amd64;paddle 的 aarch64 轮子情况不明,NAS 若是 ARM 再加多架构
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# libgomp1: paddlepaddle 运行依赖;libglib2.0-0: opencv-headless 运行依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
# 先只拷锁文件装依赖,让 paddle 大层独立缓存;项目本身不安装(直接以 cwd 运行 app/)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
# 前端静态产物;main.py 检测到 backend/static/ 存在时挂载并做 SPA fallback
COPY --from=frontend /build/dist ./static
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
EXPOSE 8010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
