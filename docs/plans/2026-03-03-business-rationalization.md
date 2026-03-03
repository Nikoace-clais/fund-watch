# 业务合理化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一「份额」为核心数据模型，实现完整盈亏计算（已实现+未实现），修复 CSV 去重、删除校验、卖出手续费三个 Bug。

**Architecture:** 后端 `_compute_pnl()` 重写加入已实现盈亏；`_recompute_fund_amount()` 简化为只更新 `holding_shares`；前端废弃 `amount`/`percentage` 字段依赖，改为纯前端计算市值和占比。份额编辑统一：有交易记录=自动，无交易=手动可编辑。

**Tech Stack:** Python decimal.Decimal (后端)，decimal.js (前端)，SQLite TEXT 存储精确数值。

---

### Task 1: 后端 — 重写 `_recompute_fund_amount()`

**Files:**
- Modify: `backend/app/main.py:79-98`

**Step 1: 修改 `_recompute_fund_amount`，只更新 `holding_shares`，不再写 `amount`/`amount_mode`**

将 `_recompute_fund_amount` 替换为：

```python
def _recompute_holding_shares(conn, code: str) -> None:
    """Recompute funds.holding_shares from transactions."""
    rows = conn.execute(
        "SELECT direction, shares FROM transactions WHERE code=?", (code,)
    ).fetchall()
    if not rows:
        conn.execute("UPDATE funds SET holding_shares=NULL WHERE code=?", (code,))
        return
    holding = Decimal("0")
    for r in rows:
        s = Decimal(r["shares"])
        if r["direction"] == "buy":
            holding += s
        else:
            holding -= s
    conn.execute(
        "UPDATE funds SET holding_shares=? WHERE code=?",
        (str(holding), code),
    )
```

**Step 2: 全局替换所有 `_recompute_fund_amount` 调用为 `_recompute_holding_shares`**

涉及行（搜索 `_recompute_fund_amount`）：
- `add_transaction` 端点（约 main.py:468）
- `delete_transaction` 端点（约 main.py:482）
- `import_csv` 端点（约 main.py:544）

**Step 3: 验证**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "refactor: rename _recompute_fund_amount to _recompute_holding_shares, only update shares"
```

---

### Task 2: 后端 — 重写 `_compute_pnl()` 加入已实现盈亏

**Files:**
- Modify: `backend/app/main.py:101-149`

**Step 1: 替换 `_compute_pnl` 函数**

```python
def _compute_pnl(conn, code: str, current_nav: str | None = None) -> dict:
    """Compute full P&L (realized + unrealized) for a fund."""
    rows = conn.execute(
        "SELECT direction, nav, shares, amount, fee FROM transactions WHERE code=? ORDER BY trade_date",
        (code,),
    ).fetchall()

    buy_shares = Decimal("0")
    buy_amount = Decimal("0")
    buy_fee = Decimal("0")
    sell_shares = Decimal("0")
    sell_amount = Decimal("0")
    sell_fee = Decimal("0")

    for r in rows:
        s = Decimal(r["shares"])
        a = Decimal(r["amount"])
        f = Decimal(r["fee"])
        if r["direction"] == "buy":
            buy_shares += s
            buy_amount += a
            buy_fee += f
        else:
            sell_shares += s
            sell_amount += a
            sell_fee += f

    holding_shares = buy_shares - sell_shares
    total_cost = buy_amount + buy_fee
    avg_cost_nav = (total_cost / buy_shares).quantize(Decimal("0.0001")) if buy_shares > 0 else Decimal("0")

    # Realized P&L: sell proceeds - cost of sold shares - sell fees
    realized_pnl = Decimal("0")
    if sell_shares > 0:
        realized_pnl = sell_amount - sell_shares * avg_cost_nav - sell_fee
    realized_pnl = realized_pnl.quantize(Decimal("0.01"))

    # Unrealized P&L
    unrealized_pnl = None
    total_pnl = None
    total_pnl_rate = None

    if current_nav and holding_shares > 0:
        nav_d = Decimal(current_nav)
        unrealized_pnl = (holding_shares * (nav_d - avg_cost_nav)).quantize(Decimal("0.01"))
        total_pnl = (realized_pnl + unrealized_pnl).quantize(Decimal("0.01"))
        total_pnl_rate = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")
    elif current_nav and holding_shares == 0 and sell_shares > 0:
        # All sold — only realized P&L
        unrealized_pnl = Decimal("0")
        total_pnl = realized_pnl
        total_pnl_rate = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    return {
        "holding_shares": str(holding_shares),
        "buy_shares": str(buy_shares),
        "sell_shares": str(sell_shares),
        "total_cost": str(total_cost),
        "avg_cost_nav": str(avg_cost_nav),
        "sell_amount": str(sell_amount),
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
        "total_pnl": str(total_pnl) if total_pnl is not None else None,
        "total_pnl_rate": str(total_pnl_rate) if total_pnl_rate is not None else None,
        "current_nav": current_nav,
    }
```

**Step 2: 验证**

```bash
cd backend && uv run python -c "from app.main import _compute_pnl; print('OK')"
```

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: complete P&L calculation with realized + unrealized + sell fees"
```

---

### Task 3: 后端 — CSV 去重

**Files:**
- Modify: `backend/app/main.py` — `import_csv` 函数（约 507-548 行）

**Step 1: 在 CSV 导入循环内，INSERT 前加去重查询**

在 `conn.execute("""INSERT INTO transactions...` 之前（约 534 行），添加：

```python
                # Dedup check
                dup = conn.execute(
                    """SELECT id FROM transactions
                       WHERE code=? AND direction=? AND trade_date=? AND nav=? AND shares=?""",
                    (c, direction, row["trade_date"].strip(), str(nav_d), str(shares_d)),
                ).fetchone()
                if dup:
                    skipped += 1
                    continue
```

同时在函数开头添加 `skipped = 0`（在 `imported = 0` 旁边），返回值加 `"skipped": skipped`。

**Step 2: 验证**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "fix: CSV import dedup by code+direction+date+nav+shares"
```

---

### Task 4: 后端 — 删除交易前校验份额不为负

**Files:**
- Modify: `backend/app/main.py` — `delete_transaction` 函数（约 474-484 行）

**Step 1: 在 DELETE 执行前，模拟删除后的份额**

将 `delete_transaction` 替换为：

```python
@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT code, direction, shares FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="transaction not found")
        code = row["code"]

        # Simulate post-delete shares
        if row["direction"] == "buy":
            buy_sum = Decimal(str(conn.execute(
                "SELECT COALESCE(SUM(CAST(shares AS REAL)),0) as s FROM transactions WHERE code=? AND direction='buy'", (code,)
            ).fetchone()["s"]))
            sell_sum = Decimal(str(conn.execute(
                "SELECT COALESCE(SUM(CAST(shares AS REAL)),0) as s FROM transactions WHERE code=? AND direction='sell'", (code,)
            ).fetchone()["s"]))
            after_shares = buy_sum - Decimal(row["shares"]) - sell_sum
            if after_shares < 0:
                raise HTTPException(status_code=400, detail="删除失败：会导致持有份额为负")

        conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        _recompute_holding_shares(conn, code)
        conn.commit()
    return {"ok": True, "deleted": tx_id}
```

**Step 2: 验证**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "fix: prevent deleting buy transaction if it would result in negative shares"
```

---

### Task 5: 后端 — 清理废弃字段和端点

**Files:**
- Modify: `backend/app/main.py`

**Step 1: 简化 funds 查询，去掉 amount/percentage/amount_mode 依赖**

将 `list_funds` 和 `funds_overview` 中的 SELECT 改为：

```sql
SELECT code, name, sector, holding_shares, created_at FROM funds ORDER BY created_at DESC
```

**Step 2: 新增 `PATCH /api/funds/{code}` 支持编辑 `holding_shares`**

修改 `UpdateFundPayload`：

```python
class UpdateFundPayload(BaseModel):
    holding_shares: str | None = None
    sector: str | None = None
```

修改 `update_fund` 端点：

```python
@app.patch("/api/funds/{code}")
def update_fund(code: str, payload: UpdateFundPayload) -> dict:
    code = _validate_code(code)
    with get_conn() as conn:
        # If has transactions, reject manual shares edit
        if payload.holding_shares is not None:
            tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)).fetchone()["c"]
            if tx_count > 0:
                raise HTTPException(status_code=400, detail="有交易记录时不可手动编辑份额")
            try:
                Decimal(payload.holding_shares)
            except InvalidOperation:
                raise HTTPException(status_code=400, detail="无效的份额数值")

        updates = []
        params: list = []
        if payload.holding_shares is not None:
            updates.append("holding_shares=?")
            params.append(payload.holding_shares)
        if payload.sector is not None:
            updates.append("sector=?")
            params.append(payload.sector)
        if not updates:
            raise HTTPException(status_code=400, detail="nothing to update")
        params.append(code)
        conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
        conn.commit()
    return {"ok": True, "code": code}
```

**Step 3: overview 返回加 `has_transactions` 标记**

在 `funds_overview` 的循环中，查询该基金是否有交易记录：

```python
        tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)).fetchone()["c"]
        items.append({"fund": f, "latest": latest_snapshot, "has_transactions": tx_count > 0})
```

**Step 4: 清理前端不再调用的 `recalc-percentage` 引用**

（端点保留但不再主动调用，前端侧改动在 Task 6 处理）

**Step 5: 验证**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

**Step 6: Commit**

```bash
git add backend/app/main.py
git commit -m "refactor: simplify fund queries, support manual shares edit, add has_transactions flag"
```

---

### Task 6: 前端 — 重写基金表格和盈亏卡片

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: 更新类型定义**

```typescript
type FundOverview = {
  fund: {
    code: string
    name?: string | null
    sector?: string | null
    holding_shares?: string | null
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
  has_transactions: boolean
}

type PnlData = {
  has_transactions: boolean
  holding_shares?: string
  total_cost?: string
  avg_cost_nav?: string
  realized_pnl?: string | null
  unrealized_pnl?: string | null
  total_pnl?: string | null
  total_pnl_rate?: string | null
  current_nav?: string | null
}
```

**Step 2: 去掉所有 `recalc-percentage` 调用**

搜索并删除所有：
```typescript
await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
```

**Step 3: 份额编辑改为编辑 `holding_shares`**

将 `editingAmount`/`editAmountVal`/`saveAmount` 重命名为 `editingShares`/`editSharesVal`/`saveShares`：

```typescript
const [editingShares, setEditingShares] = useState<string | null>(null)
const [editSharesVal, setEditSharesVal] = useState('')

async function saveShares(code: string, shares: string) {
    await fetch(`${API}/api/funds/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holding_shares: shares }),
    })
    await loadFunds()
    setEditingShares(null)
}
```

**Step 4: 表头和表体**

表头：

```tsx
<tr>
  <th>代码</th>
  <th>名称</th>
  <th>板块</th>
  <th>份额</th>
  <th>市值(元)</th>
  <th>占比%</th>
  <th>估算净值</th>
  <th>估算涨跌%</th>
  <th>涨跌额</th>
  <th>时间</th>
  <th></th>
</tr>
```

表体每行核心逻辑：

```tsx
{funds.map((f) => {
  const shares = f.fund.holding_shares ? new Decimal(f.fund.holding_shares) : null
  const gsz = f.latest?.gsz != null ? new Decimal(f.latest.gsz) : null
  const marketValue = shares && gsz ? shares.mul(gsz).toNumber() : null
  const canEditShares = !f.has_transactions
  return (
    <tr key={f.fund.code}>
      <td>{f.fund.code}</td>
      <td>{f.latest?.name || f.fund.name || '-'}</td>
      <td>{f.fund.sector || '-'}</td>
      {/* 份额列 */}
      <td
        className={canEditShares ? 'editable' : undefined}
        onClick={() => {
          if (canEditShares) {
            setEditingShares(f.fund.code)
            setEditSharesVal(f.fund.holding_shares ?? '')
          }
        }}
      >
        {editingShares === f.fund.code ? (
          <input className="inline-input" value={editSharesVal} autoFocus
            onChange={(e) => setEditSharesVal(e.target.value)}
            onBlur={() => {
              if (editSharesVal.trim()) saveShares(f.fund.code, editSharesVal.trim())
              else setEditingShares(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && editSharesVal.trim()) saveShares(f.fund.code, editSharesVal.trim())
              else if (e.key === 'Escape') setEditingShares(null)
            }}
          />
        ) : (
          shares ? fmtDecimal(f.fund.holding_shares, 2) : (canEditShares ? '点击输入' : '-')
        )}
      </td>
      {/* 市值列 */}
      <td>{marketValue != null ? fmtAmount(marketValue) : '-'}</td>
      ...
    </tr>
  )
})}
```

**Step 5: 占比% 前端实时计算**

在合计行上方计算 `totalMarketValue`，每行的占比 = `marketValue / totalMarketValue * 100`：

```tsx
// 在 funds.map 之前或用 useMemo 算出
const totalMarketValue = funds.reduce((sum, f) => {
  const sh = f.fund.holding_shares ? new Decimal(f.fund.holding_shares) : null
  const g = f.latest?.gsz != null ? new Decimal(f.latest.gsz) : null
  return sum + (sh && g ? sh.mul(g).toNumber() : 0)
}, 0)

// 每行内：
<td>{marketValue != null && totalMarketValue > 0
  ? `${(marketValue / totalMarketValue * 100).toFixed(1)}%`
  : '-'}</td>
```

**Step 6: 盈亏卡片新增已实现/总盈亏**

```tsx
{pnl?.has_transactions && (
  <div className="pnl-card">
    <div className="pnl-item">
      <div className="label">持有份额</div>
      <div className="value">{fmtDecimal(pnl.holding_shares)}</div>
    </div>
    <div className="pnl-item">
      <div className="label">成本均价</div>
      <div className="value">{fmtDecimal(pnl.avg_cost_nav, 4)}</div>
    </div>
    <div className="pnl-item">
      <div className="label">总成本</div>
      <div className="value">{fmtDecimal(pnl.total_cost)}</div>
    </div>
    <div className="pnl-item">
      <div className="label">当前估算净值</div>
      <div className="value">{pnl.current_nav ?? '-'}</div>
    </div>
    <div className="pnl-item">
      <div className="label">已实现盈亏</div>
      <div className={`value ${pnlClass(pnl.realized_pnl)}`}>
        {pnl.realized_pnl != null ? `${Number(pnl.realized_pnl) >= 0 ? '+' : ''}${pnl.realized_pnl}` : '-'}
      </div>
    </div>
    <div className="pnl-item">
      <div className="label">未实现盈亏</div>
      <div className={`value ${pnlClass(pnl.unrealized_pnl)}`}>
        {pnl.unrealized_pnl != null ? `${Number(pnl.unrealized_pnl) >= 0 ? '+' : ''}${pnl.unrealized_pnl}` : '-'}
      </div>
    </div>
    <div className="pnl-item">
      <div className="label">总盈亏</div>
      <div className={`value ${pnlClass(pnl.total_pnl)}`}>
        {pnl.total_pnl != null ? `${Number(pnl.total_pnl) >= 0 ? '+' : ''}${pnl.total_pnl}` : '-'}
      </div>
    </div>
    <div className="pnl-item">
      <div className="label">总盈亏率</div>
      <div className={`value ${pnlClass(pnl.total_pnl_rate)}`}>
        {pnl.total_pnl_rate != null ? `${Number(pnl.total_pnl_rate) >= 0 ? '+' : ''}${pnl.total_pnl_rate}%` : '-'}
      </div>
    </div>
  </div>
)}
```

**Step 7: 验证**

```bash
cd frontend && npm run build
```

Expected: 构建成功

**Step 8: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: shares-centric UI with full P&L display and real-time percentage calc"
```

---

### Task 7: 端到端验证

**Step 1: 启动后端**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8010
```

**Step 2: 验证 DB 初始化**

```bash
uv run python -c "from app.db import init_db; init_db(); print('OK')"
```

**Step 3: 测试交易 CRUD + 盈亏**

```bash
# 添加买入
curl -s -X POST http://127.0.0.1:8010/api/funds/161725/transactions \
  -H 'Content-Type: application/json' \
  -d '{"direction":"buy","trade_date":"2024-01-15","nav":"1.2345","shares":"1000","fee":"1.23"}'

# 添加卖出
curl -s -X POST http://127.0.0.1:8010/api/funds/161725/transactions \
  -H 'Content-Type: application/json' \
  -d '{"direction":"sell","trade_date":"2024-06-15","nav":"1.5000","shares":"500","fee":"0.75"}'

# 查看盈亏（应有 realized_pnl, unrealized_pnl, total_pnl）
curl -s http://127.0.0.1:8010/api/funds/161725/pnl | python -m json.tool
```

Expected: pnl 返回包含 `realized_pnl`, `unrealized_pnl`, `total_pnl`, `total_pnl_rate`

**Step 4: 测试 CSV 去重**

导入同一 CSV 两次，第二次 `imported` 应为 0，`skipped` > 0。

**Step 5: 测试删除校验**

尝试删除一笔买入交易，如果会导致份额为负，应返回 400 错误。

**Step 6: 前端构建验证**

```bash
cd frontend && npm run build
```

Expected: 构建成功，无类型错误

**Step 7: Commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: address issues found in e2e testing"
```
