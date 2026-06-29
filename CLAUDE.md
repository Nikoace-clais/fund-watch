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
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS v4 + React Router v7 + TanStack Query
- Storage: SQLite (early stage)
- Charts: Recharts
- Realtime source: `fundgz.1234567.com.cn`
- Historical source: `fund.eastmoney.com/pingzhongdata`
- Fund search: `fundsuggest.eastmoney.com`
- Market indices: `hq.sinajs.cn`（新浪行情，3 次重试退避）

---

## Repository Layout

```text
fund-watch/
├── PLAN.md
├── README.md
├── CLAUDE.md
├── start.sh                    # 一键启动前后端
├── backend/
│   ├── pyproject.toml          # uv 配置
│   ├── run.py                  # 开发服务器入口（启动 app.main:app）
│   ├── pull_quotes.py          # 定时拉取脚本
│   ├── app/                    # ★ 生产后端（分层架构，前端所有接口在此）
│   │   ├── main.py             # 应用装配：FastAPI/CORS/中间件/lifespan/路由注册
│   │   ├── core.py             # 共享常量与校验（CST、UPLOAD_DIR、validate_code）
│   │   ├── schemas.py          # Pydantic 请求模型
│   │   ├── db.py               # SQLite 初始化/连接（FUND_WATCH_DB 可覆盖路径）
│   │   ├── fund_source.py      # 估值源 / 详情 / 搜索适配
│   │   ├── ocr_service.py      # 截图 OCR（rapidocr）
│   │   ├── routers/            # API 路由（按域拆分）
│   │   │   ├── health.py  funds.py  quotes.py  portfolio.py
│   │   │   └── transactions.py  dca.py  ocr.py  market.py
│   │   └── services/           # 业务逻辑
│   │       ├── holdings.py     # 份额重算 + P&L 计算
│   │       ├── snapshots.py    # 快照拉取 + 交易时段调度器
│   │       └── dca.py          # 定投绩效统计
│   └── data/
│       └── fund_watch.db       # SQLite 数据库（运行后生成）
└── frontend/
    ├── package.json            # bun 管理依赖
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx            # React 入口
        ├── routes.tsx          # 路由定义
        ├── styles/             # Tailwind CSS v4
        ├── lib/
        │   ├── api.ts          # API 客户端 + 全部响应类型（唯一类型来源）
        │   ├── queries.ts      # TanStack Query：queryClient/keys/hooks
        │   ├── color-context.tsx # 涨跌配色（colorFor/badgeClassFor/chartColorFor）
        │   └── utils.ts        # 工具函数
        ├── services/
        │   └── import.ts       # 截图导入预览/确认（基于 lib/api）
        ├── components/
        │   ├── Layout.tsx      # 侧边栏布局（含 cron 状态、移动端红点）
        │   ├── PageState.tsx   # 统一加载/空态占位
        │   ├── portfolio/      # Portfolio 页子组件（表格/统计卡/图表/弹窗）
        │   └── fund-detail/    # FundDetail 页子组件（净值图/配置/定投等）
        └── pages/
            ├── Dashboard.tsx   # 概览
            ├── FundDetail.tsx  # 基金详情
            ├── Portfolio.tsx   # 自选基金
            ├── Market.tsx      # 行情数据
            ├── Dca.tsx         # 定投计划
            └── ImportPage.tsx  # 截图导入
```

**重要**：生产后端是 `backend/app/`（已完成分层拆分）。历史遗留的 `backend/src/fund_watch/`
已删除，新浪指数数据源已移植到 `app/fund_source.py`。修改接口一律改 `app/`。

---

## Runbook

### 一键启动（推荐）

```bash
cd /home/niko/hobby/fund-watch/fund-watch
./start.sh
```

### Backend

```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend
uv sync
uv run python run.py          # 或: uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend
bun install
bun run dev
```

Frontend: `http://127.0.0.1:5173` | Backend: `http://127.0.0.1:8010` | Swagger: `http://127.0.0.1:8010/docs`

### Tests & Lint

```bash
# 后端测试
cd /home/niko/hobby/fund-watch/fund-watch/backend
uv run pytest                          # 全量
uv run pytest tests/unit/             # 单元
uv run pytest tests/integration/      # 集成

# 后端 lint
uv run ruff check .
uv run mypy .

# 前端类型检查
cd /home/niko/hobby/fund-watch/fund-watch/frontend
bun run lint                           # tsc --noEmit
```

## 环境要求

- Python >=3.12（`uv` 管理）
- bun 1.3.10+（`bun install` 自动安装依赖）
- 可选环境变量：`FUND_WATCH_DB=<path>` 覆盖 SQLite 路径（默认 `backend/data/fund_watch.db`）

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
- `GET /api/portfolio/history?limit=90` — 组合市值历史

### Transactions & DCA
- `GET/POST /api/funds/{code}/transactions` — 交易记录
- `DELETE /api/transactions/{tx_id}` — 删除交易
- `POST /api/transactions/csv` — CSV 批量导入
- `/api/dca/plans*`、`/api/dca/records*`、`/api/dca/stats` — 定投计划/记录/统计

### OCR & misc
- `POST /api/ocr/fund-code` — 截图识别基金代码（rapidocr）
- `POST /api/ocr/transaction` — 截图识别交易记录
- `GET /api/market/indices` — 大盘指数（新浪源；失败时返回空 items + error 字段，不抛 502）
- `GET /api/cron/status` — 快照调度状态

When extending APIs:
- keep response shape stable
- prefer additive changes
- add explicit error messages for invalid fund codes / source failures

---

## 截图导入

前端 `/import` 页面（ImportPage → ImportPreview）走以下流程：

1. 上传截图 → `POST /api/ocr/fund-code`（rapidocr 识别 6 位代码，识别不到代码时按基金名模糊搜索）
2. 缺名称的代码通过 `GET /api/funds/search?q=代码` 补全
3. 用户勾选确认 → `POST /api/funds/batch` 批量入库

```json
{"codes": ["110011", "161725", "012414"]}
```

也可以让 AI 识别截图后直接按上述 JSON 调 `/api/funds/batch` 导入。

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
- ✅ 六大页面：Dashboard / FundDetail / Portfolio / Market / Dca / Import
- ✅ 端到端流程可用
- ✅ 截图 OCR 导入（ImportPage + rapidocr + 基金名回退搜索）
- ✅ 定投计划/记录/统计（DCA）
- ✅ 大盘指数（新浪源 + 降级容错）

### Next Priorities
1. **提醒规则** — 涨跌阈值 + 冷却时间 + 降噪
2. **定时拉取完善** — pull_quotes.py + cron 配置文档化
3. **用户维度** — 多人使用 + 分享权限

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **fund-watch** (561 symbols, 1389 relationships, 41 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/fund-watch/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/fund-watch/context` | Codebase overview, check index freshness |
| `gitnexus://repo/fund-watch/clusters` | All functional areas |
| `gitnexus://repo/fund-watch/processes` | All execution flows |
| `gitnexus://repo/fund-watch/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

- Re-index: `npx gitnexus analyze`
- Check freshness: `npx gitnexus status`
- Generate docs: `npx gitnexus wiki`

<!-- gitnexus:end -->
