# Risk Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在基金详情页新增风险指标卡片，展示夏普比率、最大回撤、年化波动率、年化收益率，并配 emoji 等级标识；同时顺带展示 EastMoney 提供的基金经理 5 维能力评分。

**Architecture:** 前端从已有的 `history`（NavPoint[]，含 `dailyReturn`）直接计算所有风险指标，零新 API 调用。后端仅在 `fetch_fund_detail` 中增加解析 `Data_currentFundManager.power`，通过已有 `FundDetailData` 传给前端。新组件 `RiskMetrics.tsx` 独立承担计算与渲染。

**Tech Stack:** Python/FastAPI (backend parsing), React/TypeScript/Tailwind CSS v4 (frontend)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/fund_source.py` | `fetch_fund_detail()` 中解析 `manager_power_scores` / `manager_power_categories` |
| Modify | `frontend/src/lib/api.ts` | `FundDetailData` 添加两个可选字段 |
| Create | `frontend/src/components/fund-detail/RiskMetrics.tsx` | 计算指标 + 渲染卡片（含 emoji 等级） |
| Modify | `frontend/src/pages/FundDetail.tsx` | 引入并插入 `<RiskMetrics>` |

---

## Task 1: 后端解析 manager_power

**Files:**
- Modify: `backend/app/fund_source.py`（在 `fetch_fund_detail` 末尾追加解析）

- [ ] **Step 1: 打开文件，找到 `fetch_fund_detail` 的 `return result` 前**

文件路径：`backend/app/fund_source.py`，约第 275-285 行。目前代码末尾为：

```python
    result["sector"] = _extract_sector(result["name"]) if result["name"] else None

    # Subscription fee rates
    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]*)"', text)
    result["subscription_rate"] = _to_float(m.group(1)) if m else None

    m = re.search(r'var fund_Rate\s*=\s*"([^"]*)"', text)
    result["subscription_rate_discounted"] = _to_float(m.group(1)) if m else None

    return result
```

- [ ] **Step 2: 在 `return result` 前插入 manager_power 解析**

```python
    # Manager power scores from Data_currentFundManager
    raw_managers = _extract_js_array(text, "Data_currentFundManager")
    result["manager_power_scores"] = None
    result["manager_power_categories"] = None
    if raw_managers:
        try:
            power = raw_managers[0].get("power", {})
            result["manager_power_scores"] = power.get("data")
            result["manager_power_categories"] = power.get("categories")
        except (IndexError, AttributeError):
            pass

    return result
```

- [ ] **Step 3: 验证后端解析正确**

```bash
cd /home/niko/hobby/fund-watch/fund-watch/backend
uv run python3 -c "
import asyncio
from app.fund_source import fetch_fund_detail
result = asyncio.run(fetch_fund_detail('110011'))
print('scores:', result.get('manager_power_scores'))
print('cats:', result.get('manager_power_categories'))
"
```

预期输出类似：
```
scores: [97.3, 51.5, 58.6, 93.2, 62.6]
cats: ['经验值', '收益率', '抗风险', '稳定性', '择时能力']
```

- [ ] **Step 4: 更新 `FundDetailData` 类型**

文件：`frontend/src/lib/api.ts`，`FundDetailData` 类型定义末尾追加两个可选字段：

```typescript
export type FundDetailData = {
  code: string
  name?: string
  fund_type?: string
  manager?: string
  size?: number
  established_date?: string
  one_month_return?: number
  three_month_return?: number
  six_month_return?: number
  one_year_return?: number
  asset_allocation: Array<{ name: string; value: number }>
  sector?: string
  subscription_rate?: number
  subscription_rate_discounted?: number
  manager_power_scores?: number[] | null        // 新增
  manager_power_categories?: string[] | null   // 新增
}
```

- [ ] **Step 5: 提交**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add backend/app/fund_source.py frontend/src/lib/api.ts
git commit -m "feat: expose manager power scores from pingzhongdata"
```

---

## Task 2: 创建 RiskMetrics 组件

**Files:**
- Create: `frontend/src/components/fund-detail/RiskMetrics.tsx`

- [ ] **Step 1: 创建文件，写入计算函数 + 组件**

```tsx
import type { NavPoint, FundDetailData } from '@/lib/api'

// ── Computation ──────────────────────────────────────────────────────────────

function computeMetrics(history: NavPoint[]) {
  // Use last 252 trading days; skip null dailyReturn points
  const slice = history.slice(-252)
  const returns = slice
    .filter(p => p.dailyReturn != null)
    .map(p => p.dailyReturn! / 100)  // decimal form

  if (returns.length < 30) return null

  // Annualized return from NAV endpoints
  const navSlice = slice.filter(p => p.nav != null)
  const startNav = navSlice[0]?.nav
  const endNav = navSlice[navSlice.length - 1]?.nav
  const n = returns.length
  const annualReturn =
    startNav && endNav
      ? (Math.pow(endNav / startNav, 252 / n) - 1) * 100
      : null

  // Annualized volatility
  const mean = returns.reduce((a, b) => a + b, 0) / n
  const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / n
  const annualVol = Math.sqrt(variance * 252) * 100

  // Max drawdown
  let peak = -Infinity
  let maxDD = 0
  for (const p of navSlice) {
    if (p.nav! > peak) peak = p.nav!
    const dd = (peak - p.nav!) / peak
    if (dd > maxDD) maxDD = dd
  }
  const maxDrawdown = maxDD * 100

  // Sharpe ratio (risk-free = 2% annual)
  const RISK_FREE = 2
  const sharpe =
    annualReturn != null && annualVol > 0
      ? (annualReturn - RISK_FREE) / annualVol
      : null

  return { annualReturn, annualVol, maxDrawdown, sharpe }
}

// ── Emoji grading ─────────────────────────────────────────────────────────────

function returnGrade(v: number) {
  if (v >= 20) return '🚀'
  if (v >= 5)  return '📈'
  if (v >= 0)  return '😐'
  return '📉'
}

function volGrade(v: number) {
  if (v < 10) return '🧊'
  if (v < 20) return '💧'
  if (v < 30) return '🌊'
  return '🌪️'
}

function ddGrade(v: number) {
  if (v < 10) return '🛡️'
  if (v < 20) return '💚'
  if (v < 30) return '🟡'
  return '🔴'
}

function sharpeGrade(v: number) {
  if (v >= 1.5) return '🏆'
  if (v >= 1.0) return '⭐'
  if (v >= 0.5) return '👍'
  if (v >= 0)   return '😐'
  return '⚠️'
}

// ── Component ─────────────────────────────────────────────────────────────────

type Props = {
  history: NavPoint[]
  detail: FundDetailData
}

function MetricCard({
  label, value, grade, hint,
}: { label: string; value: string; grade: string; hint?: string }) {
  return (
    <div className="text-center p-3 bg-slate-50 rounded-lg" title={hint}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-base font-bold text-slate-800">{value}</p>
      <p className="text-lg mt-0.5">{grade}</p>
    </div>
  )
}

function PowerBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-slate-500 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full bg-blue-400 rounded-full"
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="w-8 text-right text-slate-600 font-medium">{score.toFixed(0)}</span>
    </div>
  )
}

export function RiskMetrics({ history, detail }: Props) {
  const metrics = computeMetrics(history)

  const fmt = (v: number | null, suffix = '%') =>
    v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}${suffix}` : '--'

  const fmtSharpe = (v: number | null) =>
    v != null ? v.toFixed(2) : '--'

  const hasPower =
    detail.manager_power_scores &&
    detail.manager_power_categories &&
    detail.manager_power_scores.length === detail.manager_power_categories.length

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
      <div className="flex items-center gap-2">
        <span className="text-slate-600">📊</span>
        <h2 className="text-lg font-semibold text-slate-800">风险指标</h2>
        <span className="text-xs text-slate-400 ml-1">（近252交易日）</span>
      </div>

      {metrics ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard
            label="年化收益率"
            value={fmt(metrics.annualReturn)}
            grade={metrics.annualReturn != null ? returnGrade(metrics.annualReturn) : '–'}
            hint="≥20%🚀 ≥5%📈 ≥0%😐 <0%📉"
          />
          <MetricCard
            label="年化波动率"
            value={fmt(metrics.annualVol)}
            grade={volGrade(metrics.annualVol)}
            hint="<10%🧊 <20%💧 <30%🌊 ≥30%🌪️"
          />
          <MetricCard
            label="最大回撤"
            value={`-${metrics.maxDrawdown.toFixed(2)}%`}
            grade={ddGrade(metrics.maxDrawdown)}
            hint="<10%🛡️ <20%💚 <30%🟡 ≥30%🔴"
          />
          <MetricCard
            label="夏普比率"
            value={fmtSharpe(metrics.sharpe)}
            grade={metrics.sharpe != null ? sharpeGrade(metrics.sharpe) : '–'}
            hint="≥1.5🏆 ≥1.0⭐ ≥0.5👍 ≥0😐 <0⚠️"
          />
        </div>
      ) : (
        <p className="text-sm text-slate-400">数据不足，无法计算风险指标</p>
      )}

      {hasPower && (
        <div className="space-y-2 pt-1 border-t border-slate-100">
          <p className="text-xs font-medium text-slate-500">基金经理能力（天天基金评分）</p>
          {detail.manager_power_categories!.map((cat, i) => (
            <PowerBar
              key={cat}
              label={cat}
              score={detail.manager_power_scores![i]}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 前端类型检查**

```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend
bun run lint
```

预期：无 TypeScript 错误。

- [ ] **Step 3: 提交**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/components/fund-detail/RiskMetrics.tsx
git commit -m "feat: add RiskMetrics component with emoji grading"
```

---

## Task 3: 接入 FundDetail 页面

**Files:**
- Modify: `frontend/src/pages/FundDetail.tsx`

- [ ] **Step 1: 加 import**

在 `FundDetail.tsx` 顶部现有 import 区末尾追加：

```typescript
import { RiskMetrics } from '@/components/fund-detail/RiskMetrics'
```

- [ ] **Step 2: 在 `StageReturns` 下方插入 `RiskMetrics`**

找到左侧大列的内容（约第 165-168 行）：

```tsx
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          <NavChart history={history} transactions={transactions} />
          <StageReturns detail={detail} />
        </div>
```

修改为：

```tsx
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          <NavChart history={history} transactions={transactions} />
          <StageReturns detail={detail} />
          <RiskMetrics history={history} detail={detail} />
        </div>
```

- [ ] **Step 3: 前端类型检查**

```bash
cd /home/niko/hobby/fund-watch/fund-watch/frontend
bun run lint
```

预期：无错误。

- [ ] **Step 4: 启动应用，人工验证**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
./start.sh
```

打开 `http://127.0.0.1:5173`，进入任意基金详情页，确认：
- 「风险指标」卡片出现在「阶段涨幅」下方
- 4 个格子显示数值 + emoji
- 有基金经理数据时显示能力进度条
- 数据不足 30 天时显示"数据不足"提示

- [ ] **Step 5: 提交**

```bash
cd /home/niko/hobby/fund-watch/fund-watch
git add frontend/src/pages/FundDetail.tsx
git commit -m "feat: wire RiskMetrics into FundDetail page"
```
