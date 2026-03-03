# CLAUDE.md — fund-watch

This file guides Claude (and other coding agents) when working in this project.

## Project Goal

Build a practical A-share public fund watcher focused on:
- estimated NAV (盘中估值)
- low-noise alerts
- OCR-based fund code extraction
- persistent snapshots for trend analysis

Current scope is **free data sources first**, then harden for multi-user usage.

---

## Tech Stack

- Backend: FastAPI (Python 3.x)
- Frontend: React 18 + Vite + TypeScript
- Storage: SQLite (early stage)
- OCR: `rapidocr-onnxruntime`
- Charts: Recharts (planned)
- Realtime source: `fundgz.1234567.com.cn`
- Historical source: `fund.eastmoney.com/pingzhongdata`

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
│   │   ├── fund_source.py      # 估值源适配（fundgz JSONP解析）
│   │   └── ocr_service.py      # RapidOCR + 6位代码提取
│   └── data/
│       ├── fund_watch.db       # SQLite 数据库（运行后生成）
│       └── uploads/            # OCR 上传图片
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx            # React 入口
        ├── App.tsx             # 单文件主组件
        └── styles.css          # 全局样式
```

---

## Runbook

### Backend

```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend
/home/linuxbrew/.linuxbrew/bin/uv venv
/home/linuxbrew/.linuxbrew/bin/uv pip install -r requirements.txt
/home/linuxbrew/.linuxbrew/bin/uv run uvicorn app.main:app --reload --port 8010
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

- `GET /api/health`
- `GET /api/funds` — 基金池列表
- `POST /api/funds/{code}` — 添加单只基金
- `POST /api/funds/batch` — 批量添加基金
- `GET /api/funds/overview` — 基金池 + 最新估算数据
- `GET /api/quote/{code}` — 实时估值
- `POST /api/snapshots/pull` — 批量拉取快照并落库
- `GET /api/snapshots/{code}?limit=30` — 历史快照序列
- `POST /api/ocr/fund-code` — OCR 识别基金代码

When extending APIs:
- keep response shape stable
- prefer additive changes
- add explicit error messages for invalid fund codes / source failures

---

## Coding Rules

1. Keep changes minimal and focused.
2. Do not break existing endpoint names unless explicitly requested.
3. Validate all fund codes as 6-digit numeric strings.
4. Persist OCR results (`raw_text`, matched codes, timestamp) for auditability.
5. Clearly label estimated NAV data as estimate (not final NAV).
6. Avoid noisy alert logic; default to conservative thresholds.

---

## Data Source Notes

- Free endpoints can be unstable; build retry + fallback behavior.
- `fundgz` returns JSONP-like payload; parser must be robust.
- If source parsing fails, return a clear 502 with source context.
- 估算净值 ≠ 最终成交净值，前端需明确风险提示。

---

## Implementation Status

### Done (M1 + M2 基础)
- ✅ FastAPI 全部核心接口
- ✅ SQLite 三表（funds / fund_snapshots / ocr_records）
- ✅ fundgz 实时估值拉取与 JSONP 解析
- ✅ RapidOCR 本地识别 + 6位代码提取
- ✅ 前端：手动添加、OCR上传、基金池表格、涨跌色标
- ✅ 端到端流程可用

### Next Priorities
1. **趋势折线图** — 用 Recharts 替换当前蓝点占位，展示快照时序
2. **定时拉取** — pull_quotes.py 完善 + cron 配置（30-60s）
3. **提醒规则** — 涨跌阈值 + 冷却时间 + 降噪
4. **组合级统计** — 多基金汇总涨跌
5. **用户维度** — 多人使用 + 分享权限

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
- flow "upload screenshot -> detect fund code -> add to pool -> pull snapshot" works end-to-end
- README is updated if behavior changes
