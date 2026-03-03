# Trend Chart Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace blue-dot placeholder with a Recharts dual-axis line chart showing estimated NAV (gsz) and change % (gszzl) over time.

**Architecture:** Install Recharts, update the Snapshot type to include gszzl/gztime, replace the `.trend` div with a `<ResponsiveContainer>` + `<LineChart>` using dual YAxis. No backend changes needed.

**Tech Stack:** Recharts, React 18, TypeScript

---

### Task 1: Install Recharts

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install dependency**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npm install recharts
```

**Step 2: Verify install**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && node -e "require('recharts'); console.log('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add recharts dependency for trend chart"
```

---

### Task 2: Update Snapshot type and fetch logic

**Files:**
- Modify: `frontend/src/App.tsx:24-27` (Snapshot type)
- Modify: `frontend/src/App.tsx:52-57` (loadSnapshots function)

**Step 1: Update `Snapshot` type** (line 24-27)

Replace:
```typescript
type Snapshot = {
  captured_at: string
  gsz?: number | null
}
```

With:
```typescript
type Snapshot = {
  captured_at: string
  gsz?: number | null
  gszzl?: number | null
  gztime?: string | null
}
```

**Step 2: Update `loadSnapshots` to sort chronologically** (line 52-57)

The API returns `ORDER BY id DESC` (newest first). Recharts needs oldest→newest for left-to-right time axis.

Replace:
```typescript
  async function loadSnapshots(code: string) {
    setSelectedCode(code)
    const res = await fetch(`${API}/api/snapshots/${code}?limit=30`)
    const data = await res.json()
    setSnapshots(data.items ?? [])
  }
```

With:
```typescript
  async function loadSnapshots(code: string) {
    if (selectedCode === code) {
      setSelectedCode(null)
      setSnapshots([])
      return
    }
    setSelectedCode(code)
    const res = await fetch(`${API}/api/snapshots/${code}?limit=30`)
    const data = await res.json()
    const items: Snapshot[] = data.items ?? []
    setSnapshots(items.reverse())
  }
```

**Step 3: Verify build**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npx tsc --noEmit
```
Expected: no errors

**Step 4: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/App.tsx
git commit -m "feat: extend Snapshot type with gszzl/gztime, add toggle & chronological sort"
```

---

### Task 3: Replace blue-dot section with Recharts line chart

**Files:**
- Modify: `frontend/src/App.tsx:1` (add Recharts imports)
- Modify: `frontend/src/App.tsx:190-201` (replace trend section content)

**Step 1: Add Recharts imports** (line 1)

After the existing React import, add:
```typescript
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
```

**Step 2: Replace trend section** (lines 190-201)

Replace:
```tsx
      <section className="card">
        <h2>趋势（最近 30 条）{selectedCode ? ` · ${selectedCode}` : ''}</h2>
        {snapshots.length === 0 ? (
          <p>请选择基金查看</p>
        ) : (
          <div className="trend">
            {snapshots.map((s, i) => (
              <div key={`${s.captured_at}-${i}`} className="dot" title={`${s.captured_at} | ${s.gsz ?? '-'}`} />
            ))}
          </div>
        )}
      </section>
```

With:
```tsx
      {selectedCode && (
        <section className="card">
          <h2>趋势（最近 30 条） · {selectedCode}</h2>
          {snapshots.length === 0 ? (
            <p>暂无快照数据</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={snapshots} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="gztime"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v?.slice(11, 16) ?? ''}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11 }}
                    domain={['auto', 'auto']}
                    label={{ value: '估算净值', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    domain={['auto', 'auto']}
                    label={{ value: '涨跌幅%', angle: 90, position: 'insideRight', style: { fontSize: 11 } }}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) =>
                      [name === '估算净值' ? value?.toFixed(4) : `${value?.toFixed(2)}%`, name]
                    }
                    labelFormatter={(label: string) => `时间: ${label}`}
                  />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="gsz" name="估算净值" stroke="#2563eb" dot={false} strokeWidth={2} />
                  <Line yAxisId="right" type="monotone" dataKey="gszzl" name="涨跌幅%" stroke="#15803d" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
              <p className="disclaimer">以上为盘中估算数据，非最终成交净值</p>
            </>
          )}
        </section>
      )}
```

**Step 3: Verify build**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npx tsc --noEmit
```
Expected: no errors

**Step 4: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/App.tsx
git commit -m "feat: replace blue-dot placeholder with Recharts dual-axis trend chart"
```

---

### Task 4: Update styles

**Files:**
- Modify: `frontend/src/styles.css` (replace `.trend`/`.dot` with `.disclaimer`)

**Step 1: Replace old trend styles**

Remove these rules:
```css
.trend {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
  opacity: 0.75;
}
```

Add:
```css
.disclaimer {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
  text-align: center;
}
```

**Step 2: Verify build**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npm run build
```
Expected: build succeeds with no errors

**Step 3: Commit**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/styles.css
git commit -m "style: replace blue-dot styles with chart disclaimer"
```

---

### Task 5: Visual verification

**Step 1: Start backend**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend && /home/linuxbrew/.linuxbrew/bin/uv run uvicorn app.main:app --reload --port 8010
```

**Step 2: Start frontend**

Run:
```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend && npm run dev
```

**Step 3: Manual verification**

1. Open `http://127.0.0.1:5173`
2. Add a fund (e.g. `161725`)
3. Click "看趋势" — chart section should appear below table
4. Click same fund again — chart should collapse
5. Hover on chart — tooltip shows time + gsz + gszzl%
6. Legend clickable to toggle lines

**Step 4: Final commit if any tweaks needed**
