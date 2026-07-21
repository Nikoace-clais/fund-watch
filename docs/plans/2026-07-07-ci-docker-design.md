# CI + Docker 化 Design Document

**Date:** 2026-07-07
**Status:** Approved（plan-mode 会话中经用户确认：范围 = CI + Docker 镜像构建，e2e 暂不进 CI）
**Executor:** Sonnet（最新）

## Goal

给仓库补上缺失的 CI(lint + 测试 + 构建自动化),并落地路线图第 6 项 Docker 化,产出可在 NAS 一条命令部署的单镜像。

## 方案

### 数据模型

无。

### Backend API

无新增接口。`app/main.py` 在所有路由注册之后,若 `backend/static/` 目录存在(仅镜像内存在):
- 挂载 `/assets` 静态资源;
- GET catch-all `/{path:path}` 做 SPA fallback(文件存在返回文件,否则返回 `index.html`)。

本地开发无 `static/` 目录,行为零变化。

### Frontend

`lib/api-client.ts:3` 的 `||` 改为 `??`:`VITE_API_URL=""` 表示同源相对路径(Docker 单镜像用),未设置时仍回落 `http://127.0.0.1:8010`(本地 dev 不变)。

### Docker

单镜像(非 nginx 双容器):多阶段 Dockerfile——`oven/bun:1` 构建前端静态产物,拷入 `python:3.12-slim` + uv 的后端镜像,uvicorn 直接服务 API + 静态页。前后端同源,生产无需 CORS 配置。compose 单 service,卷挂载 `./data:/app/backend/data`(DB + 上传截图一起持久化)。

### CI(GitHub Actions)

`.github/workflows/ci.yml`,push main + PR 触发,三个 job:
- **backend**:setup-uv(缓存)→ `uv sync --extra dev` → ruff / mypy / pytest(测试已全 mock,无需网络与 OCR 推理)
- **frontend**:setup-bun → `bun install --frozen-lockfile` → lint / vitest / build
- **docker**:needs 前两者,buildx + gha 层缓存;main push 推 `ghcr.io/nikoace-clais/fund-watch`,PR 只构建不推

## 不做什么

- CD 到具体环境(NAS 手动 `docker compose pull && up`,有真实需求再自动化)
- Playwright e2e 进 CI(仅 1 个冒烟用例,用例多了再加)
- 多架构镜像(仅 linux/amd64,paddle aarch64 轮子情况不明)、OCR 模型预烤、path 过滤、覆盖率上报

## 风险与权衡

- paddle 系列 ~1GB+ 在核心依赖里,CI 与镜像构建靠 uv 缓存 / buildx gha 层缓存吸收;镜像体积大(~2-3GB)是 OCR 功能的固有代价。
- PaddleOCR 模型运行时首启后台下载,容器需要外网;可接受(NAS 有网)。
- GHA 缓存上限 10GB,paddle 层可能被逐出导致偶发慢构建;可接受。
