# CLAUDE.md — fund-watch

This file guides Claude (and other coding agents) when working in this project.

## Project Goal

Build a practical A-share public fund watcher focused on:
- estimated NAV (盘中估值)
- low-noise alerts
- AI-assisted fund import & selection (截图 OCR / AI 选基)
- persistent snapshots for trend analysis

Current scope is **free data sources first**, then harden for multi-user usage.

---

## Tech Stack

- Backend: FastAPI (Python >=3.12, `uv` 管理)
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS v4 + React Router v7 + TanStack Query (bun 管理)
- Storage: SQLite（`FUND_WATCH_DB` 可覆盖路径，默认 `backend/data/fund_watch.db`）
- Charts: Recharts
- Realtime source: `fundgz.1234567.com.cn`
- Historical source: `fund.eastmoney.com/pingzhongdata`
- Fund search: `fundsuggest.eastmoney.com`
- Market indices: `hq.sinajs.cn`（新浪行情，3 次重试退避）

---

## Architecture

真实目录结构以 `ls` 为准，本节只约定分层规则，不逐文件维护。

**重要**：生产后端是 `backend/app/`（分层架构，前端所有接口在此）。修改接口一律改 `app/`。

### Backend (`backend/app/`)

```text
main.py          应用装配：FastAPI/CORS/中间件/lifespan/路由注册
core.py          共享常量与校验（CST、UPLOAD_DIR、validate_code）
schemas.py       Pydantic 请求模型
db.py            SQLite 初始化/连接
fund_source.py   外部数据源适配（估值/详情/搜索/指数）
ocr_service.py   截图 OCR（rapidocr）
routers/         API 路由，按域拆分
services/        业务逻辑
repositories/    SQL 访问层
```

分层规则：
- **routers 保持薄**：只做参数校验、依赖注入和编排，业务逻辑放 services
- **SQL 只写在 repositories**：services/routers 不直接拼 SQL
- 新增域时按 router → service → repository 同名拆分

### Frontend (`frontend/src/`)

```text
pages/           路由页面（见 routes.tsx）
components/      共享组件 + 按页面分的子目录（portfolio/ fund-detail/ import/ add-fund/ layout/）
lib/             API 封装、TanStack Query、context、工具
services/        组合多个 API 的前端流程（如截图导入）
```

分层规则：
- **响应类型唯一来源 `lib/api-types.ts`**，请求函数在 `lib/api-endpoints.ts`，`lib/api.ts` 是薄 barrel
- TanStack Query 的 queryClient/keys/hooks/mutations 集中在 `lib/queries.ts`
- 涨跌配色统一走 `lib/color-context.tsx`，加载/空态占位统一用 `components/PageState.tsx`

---

## Runbook

### 一键启动（推荐）

```bash
cd /home/niko/hobby/fund-watch/fund-watch
./start.sh
```

### Backend

```bash
cd backend
uv sync
uv run python run.py          # 或: uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd frontend
bun install
bun run dev
```

Frontend: `http://127.0.0.1:5173` | Backend: `http://127.0.0.1:8010` | Swagger: `http://127.0.0.1:8010/docs`

### Tests & Lint

```bash
# 后端（backend/ 目录下）
uv run pytest                 # 全量；tests/unit/ 与 tests/integration/ 可分开跑
uv run ruff check .
uv run mypy .

# 前端（frontend/ 目录下）
bun run lint                  # tsc --noEmit
```

---

## API Conventions

接口清单不在此维护——活文档见 Swagger `http://127.0.0.1:8010/docs`，源码真相在 `backend/app/routers/`。

扩展 API 时的约定：
- keep response shape stable; prefer additive changes
- 基金/股票代码一律校验为 6 位数字字符串
- 数据源失败返回明确错误（带来源上下文）；行情类接口降级返回空数据 + error 字段而非 502
- 估算净值 ≠ 最终净值，响应和前端都要明确标注

### 截图导入

`/import` 页面流程：上传截图 → `POST /api/ocr/fund-code` 识别代码（识别不到时按基金名模糊搜索）→ 搜索补全名称 → 用户勾选确认 → `POST /api/funds/batch` 批量入库：

```json
{"codes": ["110011", "161725", "012414"]}
```

---

## Coding Rules

1. Keep changes minimal and focused.
2. Do not break existing endpoint names unless explicitly requested.
3. 遵守 Architecture 节的分层规则（routers 薄 / 业务在 services / SQL 在 repositories / 前端类型唯一来源）。
4. Clearly label estimated NAV data as estimate (not final NAV).
5. Avoid noisy alert logic; default to conservative thresholds.
6. **GitNexus 使用约定**（覆盖本文件末尾及 AGENTS.md 中自动注入块的 MUST 规则）：GitNexus 是辅助工具，不是硬性流程。跨模块重构、重命名、删除符号时建议用 `gitnexus_impact` / `gitnexus_rename`；日常小改以 `uv run pytest` + `bun run lint` 验证为准，不强制每次编辑前跑 impact、每次提交前跑 detect_changes。

---

## Data Source Notes

- Free endpoints can be unstable; build retry + fallback behavior.
- `fundgz` returns JSONP-like payload; parser must be robust.

---

## Status & Next Priorities

核心流程端到端可用：基金池管理、盘中估值快照、多组合持仓与 P&L、交易记录、截图 OCR 导入、AI 选基（SSE 流式）、股票反查持仓基金、大盘指数。

Next:
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
- backend tests pass and frontend builds successfully
- flow "search fund → add to pool → pull snapshot → view detail" works end-to-end
- README is updated if behavior changes

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **fund-watch** (800 symbols, 2049 relationships, 59 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
