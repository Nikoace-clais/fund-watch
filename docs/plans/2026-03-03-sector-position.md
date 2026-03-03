# Sector & Position Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add fund sector (板块), position amount (持仓金额), and position percentage (持仓占比) to each fund, with OCR import support for Alipay screenshots.

**Architecture:** Add 3 columns to `funds` table (sector, amount, percentage). Add `fetch_fund_info()` to auto-fetch sector from fund name keywords. Enhance OCR to extract amounts from Alipay-style screenshots. Update frontend table with new columns and inline-editable amount field.

**Tech Stack:** FastAPI, SQLite, RapidOCR, React 18, TypeScript

---

### Task 1: Database migration — add sector/amount columns

**Files:**
- Modify: `backend/app/db.py`

**Step 1: Add migration logic to `init_db()`**

After the existing `CREATE TABLE IF NOT EXISTS funds` block, add ALTER TABLE statements (wrapped in try/except to be idempotent):

In `backend/app/db.py`, after line 26 (`)`), before the `conn.execute` for `fund_snapshots`, add:

```python
        # Migration: add sector, amount columns to funds
        for col, coltype in [("sector", "TEXT"), ("amount", "REAL"), ("percentage", "REAL")]:
            try:
                conn.execute(f"ALTER TABLE funds ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass  # column already exists
```

**Step 2: Verify backend starts**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend && uv run python -c "from app.db import init_db; init_db(); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add backend/app/db.py
git commit -m "feat: add sector/amount/percentage columns to funds table

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Add `fetch_fund_info()` for sector extraction

**Files:**
- Modify: `backend/app/fund_source.py`

**Step 1: Add sector extraction function**

Append to the end of `backend/app/fund_source.py`:

```python
PINGZHONG_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"

# Common fund sector keywords to extract from fund name
_SECTOR_KEYWORDS = [
    "白酒", "医药", "医疗", "新能源", "光伏", "半导体", "芯片", "科技",
    "消费", "食品饮料", "军工", "国防", "银行", "证券", "金融", "地产",
    "房地产", "互联网", "传媒", "农业", "煤炭", "钢铁", "有色",
    "化工", "汽车", "电力", "环保", "养老", "红利", "沪深300",
    "中证500", "中证1000", "创业板", "科创", "恒生", "港股", "纳斯达克",
    "标普", "QDII", "债", "货币",
]


def _extract_sector(name: str) -> str | None:
    """Extract sector keyword from fund name."""
    for kw in _SECTOR_KEYWORDS:
        if kw in name:
            return kw
    return None


async def fetch_fund_info(code: str) -> dict[str, Any]:
    """Fetch fund basic info (name, sector) from eastmoney pingzhongdata."""
    url = PINGZHONG_URL.format(code=code)
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    # Parse: var fS_name = "招商中证白酒指数(LOF)A";
    name_m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else None

    sector = _extract_sector(name) if name else None

    return {"name": name, "sector": sector}
```

**Step 2: Verify it works**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend && uv run python -c "
import asyncio
from app.fund_source import fetch_fund_info
r = asyncio.run(fetch_fund_info('161725'))
print(r)
"
```
Expected: `{'name': '招商中证白酒指数(LOF)A', 'sector': '白酒'}`

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add backend/app/fund_source.py
git commit -m "feat: add fetch_fund_info() for sector extraction from fund name

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Enhance OCR to extract amounts

**Files:**
- Modify: `backend/app/ocr_service.py`

**Step 1: Replace the entire file content**

```python
from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

CODE_RE = re.compile(r"\b\d{6}\b")
# Match amounts like: ¥1,234.56  1,234.56元  1234.56  持有金额 1,234.56
AMOUNT_RE = re.compile(r"[¥￥]?\s*([\d,]+\.\d{1,2})\s*元?")


def extract_fund_codes_from_image(image_path: Path) -> tuple[str, list[str]]:
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", []

    raw_text = "\n".join([line[1] for line in result if len(line) >= 2])
    codes = sorted(set(CODE_RE.findall(raw_text)))
    return raw_text, codes


def extract_funds_with_amounts(image_path: Path) -> tuple[str, list[dict]]:
    """Extract fund codes and nearby amounts from OCR text.

    Returns (raw_text, matched_funds) where matched_funds is a list of
    {"code": "161725", "amount": 1234.56} dicts. amount may be None.
    """
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", []

    # result items: [bbox, text, confidence]
    lines = [line[1] for line in result if len(line) >= 2]
    raw_text = "\n".join(lines)

    matched_funds: list[dict] = []
    seen_codes: set[str] = set()

    for i, line_text in enumerate(lines):
        codes_in_line = CODE_RE.findall(line_text)
        for code in codes_in_line:
            if code in seen_codes:
                continue
            seen_codes.add(code)

            # Search current line and nearby lines (±2) for an amount
            amount = _find_nearby_amount(lines, i, window=2)
            matched_funds.append({"code": code, "amount": amount})

    return raw_text, matched_funds


def _find_nearby_amount(lines: list[str], center: int, window: int = 2) -> float | None:
    """Search lines around center index for an amount pattern."""
    start = max(0, center - window)
    end = min(len(lines), center + window + 1)

    for idx in range(start, end):
        m = AMOUNT_RE.search(lines[idx])
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None
```

**Step 2: Verify**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend && uv run python -c "
from app.ocr_service import _find_nearby_amount, AMOUNT_RE
# Test amount regex
for t in ['¥1,234.56', '1234.56元', '持有金额 12,345.67', '收益 +12.34']:
    m = AMOUNT_RE.search(t)
    print(f'{t:30s} => {m.group(1) if m else None}')
"
```
Expected:
```
¥1,234.56                      => 1,234.56
1234.56元                      => 1234.56
持有金额 12,345.67              => 12,345.67
收益 +12.34                    => 12.34
```

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add backend/app/ocr_service.py
git commit -m "feat: enhance OCR to extract amounts near fund codes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update API endpoints

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Add import for `fetch_fund_info`**

Change line 12:
```python
from .fund_source import fetch_realtime_estimate
```
To:
```python
from .fund_source import fetch_fund_info, fetch_realtime_estimate
```

**Step 2: Add import for `extract_funds_with_amounts`**

Change line 13:
```python
from .ocr_service import extract_fund_codes_from_image
```
To:
```python
from .ocr_service import extract_fund_codes_from_image, extract_funds_with_amounts
```

**Step 3: Add Pydantic model for add fund with amount**

After `class BatchFundsPayload` (line 28), add:

```python

class AddFundPayload(BaseModel):
    amount: float | None = None


class BatchFundsPayload2(BaseModel):
    codes: list[str]
    amounts: dict[str, float] | None = None
```

**Step 4: Update `add_fund` endpoint** (line 56-66)

Replace:
```python
@app.post("/api/funds/{code}")
def add_fund(code: str) -> dict:
    code = _validate_code(code)
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO funds(code,name,created_at) VALUES(?,?,?)",
            (code, None, now),
        )
        conn.commit()
    return {"ok": True, "code": code}
```

With:
```python
@app.post("/api/funds/{code}")
async def add_fund(code: str, payload: AddFundPayload | None = None) -> dict:
    code = _validate_code(code)
    now = datetime.now(timezone.utc).isoformat()

    # Fetch fund info (name + sector) from data source
    name = None
    sector = None
    try:
        info = await fetch_fund_info(code)
        name = info.get("name")
        sector = info.get("sector")
    except Exception:
        pass

    amount = payload.amount if payload else None

    with get_conn() as conn:
        existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
        if existing:
            # Update amount if provided
            if amount is not None:
                conn.execute("UPDATE funds SET amount=? WHERE code=?", (amount, code))
            if sector and not conn.execute("SELECT sector FROM funds WHERE code=? AND sector IS NOT NULL", (code,)).fetchone():
                conn.execute("UPDATE funds SET sector=?, name=? WHERE code=?", (sector, name, code))
        else:
            conn.execute(
                "INSERT INTO funds(code,name,sector,amount,created_at) VALUES(?,?,?,?,?)",
                (code, name, sector, amount, now),
            )
        conn.commit()
    return {"ok": True, "code": code, "name": name, "sector": sector}
```

**Step 5: Update `add_funds_batch` endpoint** (line 69-92)

Replace:
```python
@app.post("/api/funds/batch")
def add_funds_batch(payload: BatchFundsPayload) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    valid: list[str] = []
    invalid: list[str] = []

    for c in payload.codes:
        c = c.strip()
        if c.isdigit() and len(c) == 6:
            valid.append(c)
        else:
            invalid.append(c)

    valid = sorted(set(valid))

    with get_conn() as conn:
        for code in valid:
            conn.execute(
                "INSERT OR IGNORE INTO funds(code,name,created_at) VALUES(?,?,?)",
                (code, None, now),
            )
        conn.commit()

    return {"ok": True, "added": valid, "invalid": invalid}
```

With:
```python
@app.post("/api/funds/batch")
async def add_funds_batch(payload: BatchFundsPayload) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    valid: list[str] = []
    invalid: list[str] = []

    for c in payload.codes:
        c = c.strip()
        if c.isdigit() and len(c) == 6:
            valid.append(c)
        else:
            invalid.append(c)

    valid = sorted(set(valid))
    amounts = payload.amounts if hasattr(payload, "amounts") and payload.amounts else {}

    with get_conn() as conn:
        for code in valid:
            # Fetch sector info
            name = None
            sector = None
            try:
                info = await fetch_fund_info(code)
                name = info.get("name")
                sector = info.get("sector")
            except Exception:
                pass

            existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
            if existing:
                updates = []
                params: list = []
                if name:
                    updates.append("name=?")
                    params.append(name)
                if sector:
                    updates.append("sector=?")
                    params.append(sector)
                amt = amounts.get(code)
                if amt is not None:
                    updates.append("amount=?")
                    params.append(amt)
                if updates:
                    params.append(code)
                    conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
            else:
                conn.execute(
                    "INSERT INTO funds(code,name,sector,amount,created_at) VALUES(?,?,?,?,?)",
                    (code, name, sector, amounts.get(code), now),
                )
        conn.commit()

    return {"ok": True, "added": valid, "invalid": invalid}
```

**Step 6: Update BatchFundsPayload** to support amounts

Replace the original `BatchFundsPayload`:
```python
class BatchFundsPayload(BaseModel):
    codes: list[str]
```
With:
```python
class BatchFundsPayload(BaseModel):
    codes: list[str]
    amounts: dict[str, float] | None = None
```

Remove the `BatchFundsPayload2` added earlier (it's no longer needed since we updated the original).

**Step 7: Update `funds_overview` endpoint** (line 105-142)

Replace the SELECT in `list_funds` (line 44-45):
```python
        rows = conn.execute("SELECT code,name,created_at FROM funds ORDER BY created_at DESC").fetchall()
```
With:
```python
        rows = conn.execute("SELECT code,name,sector,amount,percentage,created_at FROM funds ORDER BY created_at DESC").fetchall()
```

Replace the SELECT in `funds_overview` (line 108):
```python
        funds = [dict(r) for r in conn.execute("SELECT code,name,created_at FROM funds ORDER BY created_at DESC").fetchall()]
```
With:
```python
        funds = [dict(r) for r in conn.execute("SELECT code,name,sector,amount,percentage,created_at FROM funds ORDER BY created_at DESC").fetchall()]
```

**Step 8: Update OCR endpoint** to return amounts

Replace the OCR endpoint (line 199-221):

```python
@app.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, codes = extract_fund_codes_from_image(path)
    _, matched_funds = extract_funds_with_amounts(path)

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at) VALUES(?,?,?,?)",
            (path.name, raw_text, json.dumps(codes, ensure_ascii=False), now),
        )
        conn.commit()

    return {
        "ok": True,
        "image": path.name,
        "matched_codes": codes,
        "matched_funds": matched_funds,
        "raw_text": raw_text,
        "saved_at": now,
    }
```

**Step 9: Add endpoint to update fund amount**

After the `add_funds_batch` endpoint, add:

```python

class UpdateFundPayload(BaseModel):
    amount: float | None = None
    sector: str | None = None


@app.patch("/api/funds/{code}")
def update_fund(code: str, payload: UpdateFundPayload) -> dict:
    code = _validate_code(code)
    updates = []
    params: list = []
    if payload.amount is not None:
        updates.append("amount=?")
        params.append(payload.amount)
    if payload.sector is not None:
        updates.append("sector=?")
        params.append(payload.sector)
    if not updates:
        raise HTTPException(status_code=400, detail="nothing to update")
    params.append(code)
    with get_conn() as conn:
        conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
        conn.commit()
    return {"ok": True, "code": code}
```

**Step 10: Add endpoint to recalculate percentages**

After the `update_fund` endpoint, add:

```python

@app.post("/api/funds/recalc-percentage")
def recalc_percentage() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT code, amount FROM funds").fetchall()
        total = sum(r["amount"] for r in rows if r["amount"])
        if total > 0:
            for r in rows:
                pct = round((r["amount"] / total) * 100, 2) if r["amount"] else None
                conn.execute("UPDATE funds SET percentage=? WHERE code=?", (pct, r["code"]))
        conn.commit()
    return {"ok": True, "total": total}
```

**Step 11: Verify backend starts**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend && uv run python -c "from app.main import app; print('OK')"
```
Expected: `OK`

**Step 12: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add backend/app/main.py
git commit -m "feat: add sector/amount to fund APIs, enhance OCR response, add PATCH and recalc endpoints

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update frontend — types, table columns, OCR amounts, inline edit

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Update `FundOverview` type** (line 7-21)

Replace:
```typescript
type FundOverview = {
  fund: {
    code: string
    name?: string | null
    created_at: string
  }
  latest?: {
    code: string
    name?: string | null
    gsz?: number | null
    gszzl?: number | null
    gztime?: string | null
    captured_at?: string | null
  } | null
}
```

With:
```typescript
type FundOverview = {
  fund: {
    code: string
    name?: string | null
    sector?: string | null
    amount?: number | null
    percentage?: number | null
    created_at: string
  }
  latest?: {
    code: string
    name?: string | null
    gsz?: number | null
    gszzl?: number | null
    gztime?: string | null
    captured_at?: string | null
  } | null
}
```

**Step 2: Update `OcrResp` type** (line 23-26)

Replace:
```typescript
type OcrResp = {
  matched_codes: string[]
  raw_text: string
}
```

With:
```typescript
type OcrMatchedFund = {
  code: string
  amount?: number | null
}

type OcrResp = {
  matched_codes: string[]
  matched_funds: OcrMatchedFund[]
  raw_text: string
}
```

**Step 3: Update state — add ocrFunds and editingAmount**

Replace:
```typescript
  const [ocrCodes, setOcrCodes] = useState<string[]>([])
```
With:
```typescript
  const [ocrCodes, setOcrCodes] = useState<string[]>([])
  const [ocrFunds, setOcrFunds] = useState<OcrMatchedFund[]>([])
  const [editingAmount, setEditingAmount] = useState<string | null>(null)
  const [editAmountVal, setEditAmountVal] = useState('')
  const [manualAmount, setManualAmount] = useState('')
```

**Step 4: Update `onUpload` function** (line 71-88)

Replace:
```typescript
  async function onUpload(file: File) {
    setLoading(true)
    setMsg('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/ocr/fund-code`, { method: 'POST', body: form })
      if (!res.ok) throw new Error('OCR 请求失败')
      const data: OcrResp = await res.json()
      const filtered = (data.matched_codes || []).filter((c) => /^\d{6}$/.test(c))
      const invalidCount = (data.matched_codes || []).length - filtered.length
      setOcrCodes(filtered)
      setMsg(`识别完成：${filtered.join(', ') || '未识别到基金代码'}${invalidCount > 0 ? `（过滤无效 ${invalidCount} 条）` : ''}`)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : '上传失败')
    } finally {
      setLoading(false)
    }
  }
```

With:
```typescript
  async function onUpload(file: File) {
    setLoading(true)
    setMsg('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/ocr/fund-code`, { method: 'POST', body: form })
      if (!res.ok) throw new Error('OCR 请求失败')
      const data: OcrResp = await res.json()
      const funds = (data.matched_funds || []).filter((f) => /^\d{6}$/.test(f.code))
      const codes = funds.map((f) => f.code)
      setOcrCodes(codes)
      setOcrFunds(funds)
      const summary = funds.map((f) => f.amount ? `${f.code}(¥${f.amount})` : f.code).join(', ')
      setMsg(`识别完成：${summary || '未识别到基金代码'}`)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : '上传失败')
    } finally {
      setLoading(false)
    }
  }
```

**Step 5: Update `addFund` to support amount**

Replace:
```typescript
  async function addFund(code: string) {
    setMsg('')
    const res = await fetch(`${API}/api/funds/${code}`, { method: 'POST' })
    if (!res.ok) {
      setMsg(`添加 ${code} 失败`)
      return
    }
    await loadFunds()
    setMsg(`已加入基金池：${code}`)
  }
```

With:
```typescript
  async function addFund(code: string, amount?: number | null) {
    setMsg('')
    const opts: RequestInit = { method: 'POST' }
    if (amount != null) {
      opts.headers = { 'Content-Type': 'application/json' }
      opts.body = JSON.stringify({ amount })
    }
    const res = await fetch(`${API}/api/funds/${code}`, opts)
    if (!res.ok) {
      setMsg(`添加 ${code} 失败`)
      return
    }
    await loadFunds()
    setMsg(`已加入基金池：${code}`)
  }
```

**Step 6: Update `addFundManual`**

Replace:
```typescript
  async function addFundManual() {
    const code = manualCode.trim()
    if (!/^\d{6}$/.test(code)) {
      setMsg('请输入 6 位基金代码')
      return
    }
    await addFund(code)
    setManualCode('')
  }
```

With:
```typescript
  async function addFundManual() {
    const code = manualCode.trim()
    if (!/^\d{6}$/.test(code)) {
      setMsg('请输入 6 位基金代码')
      return
    }
    const amt = manualAmount.trim() ? parseFloat(manualAmount) : undefined
    await addFund(code, amt)
    setManualCode('')
    setManualAmount('')
  }
```

**Step 7: Update `addAllOcrCodes` to include amounts**

Replace:
```typescript
  async function addAllOcrCodes() {
    if (dedupedCodes.length === 0) return
    const res = await fetch(`${API}/api/funds/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: dedupedCodes }),
    })
    if (!res.ok) {
      setMsg('批量加入失败')
      return
    }
    const data = await res.json()
    await loadFunds()
    setMsg(`批量加入完成：${(data.added || []).join(', ') || '无新增'}${(data.invalid || []).length ? `；无效：${data.invalid.join(',')}` : ''}`)
  }
```

With:
```typescript
  async function addAllOcrCodes() {
    if (dedupedCodes.length === 0) return
    const amounts: Record<string, number> = {}
    for (const f of ocrFunds) {
      if (f.amount != null) amounts[f.code] = f.amount
    }
    const res = await fetch(`${API}/api/funds/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: dedupedCodes, amounts: Object.keys(amounts).length > 0 ? amounts : undefined }),
    })
    if (!res.ok) {
      setMsg('批量加入失败')
      return
    }
    const data = await res.json()
    // Recalculate percentages after batch add
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setMsg(`批量加入完成：${(data.added || []).join(', ') || '无新增'}${(data.invalid || []).length ? `；无效：${data.invalid.join(',')}` : ''}`)
  }
```

**Step 8: Add `saveAmount` function** (after `addAllOcrCodes`)

```typescript
  async function saveAmount(code: string, amount: number) {
    await fetch(`${API}/api/funds/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount }),
    })
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setEditingAmount(null)
  }
```

**Step 9: Update manual add section** (line 133-139)

Replace:
```tsx
      <section className="card">
        <h2>手动添加基金</h2>
        <div className="row">
          <input value={manualCode} placeholder="输入 6 位代码，如 161725" onChange={(e) => setManualCode(e.target.value)} />
          <button onClick={addFundManual}>添加</button>
        </div>
      </section>
```

With:
```tsx
      <section className="card">
        <h2>手动添加基金</h2>
        <div className="row">
          <input value={manualCode} placeholder="6 位代码" onChange={(e) => setManualCode(e.target.value)} style={{ flex: 2 }} />
          <input value={manualAmount} placeholder="持仓金额(可选)" onChange={(e) => setManualAmount(e.target.value)} style={{ flex: 1 }} />
          <button onClick={addFundManual}>添加</button>
        </div>
      </section>
```

**Step 10: Update OCR chips** (line 152-164)

Replace:
```tsx
        {dedupedCodes.length > 0 && (
          <>
            <div className="chips">
              {dedupedCodes.map((c) => (
                <button key={c} onClick={() => addFund(c)}>
                  加入 {c}
                </button>
              ))}
            </div>
            <button className="batch" onClick={addAllOcrCodes}>
              批量加入全部识别结果
            </button>
          </>
        )}
```

With:
```tsx
        {ocrFunds.length > 0 && (
          <>
            <div className="chips">
              {ocrFunds.map((f) => (
                <button key={f.code} onClick={() => addFund(f.code, f.amount)}>
                  加入 {f.code}{f.amount != null ? ` (¥${f.amount})` : ''}
                </button>
              ))}
            </div>
            <button className="batch" onClick={addAllOcrCodes}>
              批量加入全部识别结果
            </button>
          </>
        )}
```

**Step 11: Update fund table** (line 173-199)

Replace the entire table:
```tsx
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>估算净值</th>
                <th>估算涨跌%</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {funds.map((f) => (
                <tr key={f.fund.code}>
                  <td>{f.fund.code}</td>
                  <td>{f.latest?.name || '-'}</td>
                  <td>{fmtNum(f.latest?.gsz)}</td>
                  <td className={Number(f.latest?.gszzl || 0) >= 0 ? 'up' : 'down'}>{fmtNum(f.latest?.gszzl)}</td>
                  <td>{f.latest?.gztime || '-'}</td>
                  <td>
                    <button onClick={() => loadSnapshots(f.fund.code)}>看趋势</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
```

With:
```tsx
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>板块</th>
                <th>持仓(元)</th>
                <th>占比%</th>
                <th>估算净值</th>
                <th>估算涨跌%</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {funds.map((f) => (
                <tr key={f.fund.code}>
                  <td>{f.fund.code}</td>
                  <td>{f.latest?.name || f.fund.name || '-'}</td>
                  <td>{f.fund.sector || '-'}</td>
                  <td
                    className="editable"
                    onClick={() => { setEditingAmount(f.fund.code); setEditAmountVal(f.fund.amount?.toString() ?? '') }}
                  >
                    {editingAmount === f.fund.code ? (
                      <input
                        className="inline-input"
                        value={editAmountVal}
                        autoFocus
                        onChange={(e) => setEditAmountVal(e.target.value)}
                        onBlur={() => {
                          const v = parseFloat(editAmountVal)
                          if (!isNaN(v)) saveAmount(f.fund.code, v)
                          else setEditingAmount(null)
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const v = parseFloat(editAmountVal)
                            if (!isNaN(v)) saveAmount(f.fund.code, v)
                          } else if (e.key === 'Escape') {
                            setEditingAmount(null)
                          }
                        }}
                      />
                    ) : (
                      f.fund.amount != null ? fmtAmount(f.fund.amount) : '点击输入'
                    )}
                  </td>
                  <td>{f.fund.percentage != null ? `${f.fund.percentage}%` : '-'}</td>
                  <td>{fmtNum(f.latest?.gsz)}</td>
                  <td className={Number(f.latest?.gszzl || 0) >= 0 ? 'up' : 'down'}>{fmtNum(f.latest?.gszzl)}</td>
                  <td>{f.latest?.gztime || '-'}</td>
                  <td>
                    <button onClick={() => loadSnapshots(f.fund.code)}>看趋势</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
```

**Step 12: Add `fmtAmount` helper** (after `fmtNum`)

```typescript

function fmtAmount(v: number) {
  return v >= 10000 ? `${(v / 10000).toFixed(2)}万` : v.toFixed(2)
}
```

**Step 13: Verify build**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npm run build
```
Expected: build succeeds

**Step 14: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/App.tsx
git commit -m "feat: add sector/amount/percentage columns, OCR amount display, inline amount editing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Update styles for inline editing

**Files:**
- Modify: `frontend/src/styles.css`

**Step 1: Add styles**

Append to `frontend/src/styles.css`:

```css

td.editable {
  cursor: pointer;
  color: #2563eb;
}

td.editable:hover {
  background: #f1f5f9;
}

.inline-input {
  width: 80px;
  padding: 2px 4px;
  font-size: 13px;
  border: 1px solid #2563eb;
  border-radius: 4px;
}
```

**Step 2: Verify build**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npm run build
```
Expected: build succeeds

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/styles.css
git commit -m "style: add inline-edit styles for amount column

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: End-to-end verification

**Step 1: Restart backend**

```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend
kill $(lsof -ti:8010) 2>/dev/null; sleep 1
uv run uvicorn app.main:app --port 8010 &
```

**Step 2: Test API**

```bash
# Add fund with amount
curl -s -X POST "http://127.0.0.1:8010/api/funds/161725" -H "Content-Type: application/json" -d '{"amount": 5000}'

# Check overview returns sector + amount
curl -s "http://127.0.0.1:8010/api/funds/overview" | python3 -m json.tool | head -20

# Update amount
curl -s -X PATCH "http://127.0.0.1:8010/api/funds/161725" -H "Content-Type: application/json" -d '{"amount": 8000}'

# Recalculate
curl -s -X POST "http://127.0.0.1:8010/api/funds/recalc-percentage"
```

**Step 3: Verify frontend**

Open `http://localhost:5174` and check:
1. Table shows 板块, 持仓(元), 占比% columns
2. Click amount cell to edit inline
3. OCR upload shows detected amounts next to fund codes
4. Manual add has amount input field
