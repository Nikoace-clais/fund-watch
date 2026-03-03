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

- Backend: FastAPI (Python)
- Frontend: React + Vite + TypeScript
- Storage: SQLite (early stage)
- OCR: `rapidocr-onnxruntime`
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
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── fund_source.py
│   │   └── ocr_service.py
│   └── data/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
```

---

## Runbook

### Backend

```bash
cd /home/niko/.openclaw/workspace/fund-watch/backend
/home/linuxbrew/.linuxbrew/bin/uv venv
/home/linuxbrew/.linuxbrew/bin/uv pip install -r requirements.txt
/home/linuxbrew/.linuxbrew/bin/uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd /home/niko/.openclaw/workspace/fund-watch/frontend
npm install
npm run dev
```

---

## API Contract (current)

- `GET /api/health`
- `GET /api/funds`
- `POST /api/funds/{code}`
- `GET /api/quote/{code}`
- `POST /api/snapshots/pull`
- `POST /api/ocr/fund-code`

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

---

## Next Priorities

1. Fund pool page improvements (manual add + show latest estimated move)
2. Snapshot query endpoint + small trend chart support
3. OCR UX: batch add + dedupe + invalid candidate hints
4. Scheduled snapshot pull job (30–60s cadence, configurable)

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
