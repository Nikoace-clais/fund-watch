# CLAUDE.md — fund-watch

This file guides Claude (and other coding agents) when working in this project.

## Project Goal

Build a practical A-share public fund watcher focused on:
- estimated NAV (盘中估值)
- low-noise alerts
- AI-assisted fund import (截图 → AI 识别 → JSON → 批量导入)
- persistent snapshots for trend analysis

Current scope is **free data sources first**, then harden for multi-user usage.

---

## Tech Stack

- Backend: FastAPI (Python 3.x)
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS v4 + React Router v7
- Storage: SQLite (early stage)
- Charts: Recharts
- Realtime source: `fundgz.1234567.com.cn`
- Historical source: `fund.eastmoney.com/pingzhongdata`
- Fund search: `fundsuggest.eastmoney.com`

---

## Repository Layout

```text
fund-watch/
├── PLAN.md
├── README.md
├── CLAUDE.md
├── backend/
│   ├── requirements.txt
│   ├── pull_quotes.py          # 定时拉取脚本
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI 入口 + 所有路由
│   │   ├── db.py               # SQLite 初始化/连接
│   │   └── fund_source.py      # 估值源 / 详情 / 搜索适配
│   └── data/
│       └── fund_watch.db       # SQLite 数据库（运行后生成）
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx            # React 入口
        ├── routes.tsx          # 路由定义
        ├── styles/             # Tailwind CSS v4
        ├── lib/
        │   ├── api.ts          # API 客户端
        │   └── utils.ts        # 工具函数
        ├── components/
        │   └── Layout.tsx      # 侧边栏布局
        └── pages/
            ├── Dashboard.tsx   # 概览
            ├── FundExplorer.tsx # 基金市场
            ├── FundDetail.tsx  # 基金详情
            └── Portfolio.tsx   # 自选基金
```

---

## Runbook

### Backend

```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend
/home/niko/.local/bin/uv venv
/home/niko/.local/bin/uv pip install -r requirements.txt
/home/niko/.local/bin/uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173` | Backend: `http://127.0.0.1:8010` | Swagger: `http://127.0.0.1:8010/docs`

---

## API Contract (current)

### Fund management
- `GET /api/funds` — 基金池列表
- `POST /api/funds/{code}` — 添加单只基金
- `POST /api/funds/batch` — 批量添加 `{"codes": [...]}`
- `DELETE /api/funds/{code}` — 删除基金及关联数据
- `GET /api/funds/overview` — 基金池 + 最新估算数据
- `GET /api/funds/search?q=关键词` — 按名称/代码搜索

### Quotes & detail
- `GET /api/quote/{code}` — 实时估值
- `GET /api/funds/{code}/detail` — 基金经理、规模、涨幅、配置
- `GET /api/funds/{code}/nav-history?limit=365` — 历史 NAV
- `GET /api/funds/{code}/holdings` — 重仓股票

### Snapshots & portfolio
- `POST /api/snapshots/pull` — 批量拉取快照并落库
- `GET /api/snapshots/{code}?limit=30` — 盘中快照序列
- `GET /api/portfolio/summary` — 组合汇总统计

When extending APIs:
- keep response shape stable
- prefer additive changes
- add explicit error messages for invalid fund codes / source failures

---

## AI Import Format

不再使用 OCR 识别截图。改为让 AI 识别截图后按以下 JSON 格式输出，再通过 `/api/funds/batch` 导入：

```json
{"codes": ["110011", "161725", "012414"]}
```

Prompt 示例：
> 请识别这张图中的所有基金，输出它们的 6 位基金代码，格式为 JSON：`{"codes": ["代码1", "代码2"]}`。如果只看到基金名称，请查询对应的 6 位代码。

---

## Coding Rules

1. Keep changes minimal and focused.
2. Do not break existing endpoint names unless explicitly requested.
3. Validate all fund codes as 6-digit numeric strings.
4. Clearly label estimated NAV data as estimate (not final NAV).
5. Avoid noisy alert logic; default to conservative thresholds.

---

## Data Source Notes

- Free endpoints can be unstable; build retry + fallback behavior.
- `fundgz` returns JSONP-like payload; parser must be robust.
- If source parsing fails, return a clear 502 with source context.
- 估算净值 ≠ 最终成交净值，前端需明确风险提示。

---

## Implementation Status

### Done
- ✅ FastAPI 全部核心接口（基金管理/估值/详情/快照/搜索/组合）
- ✅ SQLite 持久化（funds / fund_snapshots / transactions）
- ✅ fundgz 实时估值拉取与 JSONP 解析
- ✅ eastmoney 基金详情/NAV 历史/重仓股票/资产配置
- ✅ 天天基金搜索 API 适配
- ✅ 前端全新 UI（Tailwind v4 + React Router + Recharts）
- ✅ Dashboard / FundExplorer / FundDetail / Portfolio 四大页面
- ✅ 端到端流程可用

### Next Priorities
1. **AI 导入页面** — 前端粘贴 JSON → 批量添加
2. **定时拉取** — pull_quotes.py 完善 + cron 配置
3. **提醒规则** — 涨跌阈值 + 冷却时间 + 降噪
4. **用户维度** — 多人使用 + 分享权限

---

## Safety / Ops

- Never commit secrets/tokens.
- Keep DB local in `backend/data/` during MVP.
- If adding cron/automation, document command + rollback.

---

## Definition of Good Change

A change is considered good when:
- backend runs without errors
- frontend builds successfully
- flow "search fund → add to pool → pull snapshot → view detail" works end-to-end
- README is updated if behavior changes
