# 基金详情页买卖明细 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 FundDetail 页面的净值折线图上用彩色圆点标注买入/卖出，并在页面底部新增全宽买卖明细表格。

**Architecture:** 复用已有后端接口 `GET /api/funds/{code}/transactions`；前端新增 `fetchTransactions` API 函数，FundDetail 并行加载交易数据，用 Recharts `ReferenceDot` 在图上标点，底部追加表格 section。

**Tech Stack:** React 18, TypeScript, Recharts (ReferenceDot), Tailwind CSS v4

---

### Task 1: 前端 API 函数

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: 新增 Transaction 类型和 fetchTransactions 函数**

在 `api.ts` 末尾添加：

```ts
export type Transaction = {
  id: number
  direction: 'buy' | 'sell'
  trade_date: string
  nav: string
  shares: string
  amount: string
  fee: string
  note?: string | null
  source?: string | null
  created_at: string
}

export function fetchTransactions(code: string) {
  return request<{ code: string; items: Transaction[] }>(
    `/api/funds/${code}/transactions`
  )
}
```

**Step 2: 验证 TypeScript 编译通过**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|✓"
```
Expected: `✓ built in ...`

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(api): 新增 fetchTransactions 函数和 Transaction 类型"
```

---

### Task 2: FundDetail 加载交易数据

**Files:**
- Modify: `frontend/src/pages/FundDetail.tsx`

**Step 1: 引入 fetchTransactions 和 Transaction 类型**

修改第 8 行 import：

```ts
import { fetchFundDetail, fetchNavHistory, fetchFundHoldings, fetchQuote, addFund, fetchTransactions, type Transaction } from '@/lib/api'
```

**Step 2: 新增 transactions state**

在现有 state 声明（约第 68 行）之后加：

```ts
const [transactions, setTransactions] = useState<Transaction[]>([])
```

**Step 3: 并行加载交易数据**

将 `Promise.allSettled` 扩展为 5 项：

```ts
Promise.allSettled([
  fetchFundDetail(code),
  fetchNavHistory(code, 500),
  fetchFundHoldings(code),
  fetchQuote(code),
  fetchTransactions(code),
]).then(([detailRes, navRes, holdRes, quoteRes, txRes]) => {
  if (detailRes.status === 'fulfilled') {
    setDetail(detailRes.value)
  } else {
    setNotFound(true)
  }
  if (navRes.status === 'fulfilled') setHistory(navRes.value.history)
  if (holdRes.status === 'fulfilled') setHoldings(holdRes.value.holdings)
  if (quoteRes.status === 'fulfilled') setQuote(quoteRes.value)
  if (txRes.status === 'fulfilled') setTransactions(txRes.value.items)
  setLoading(false)
})
```

**Step 4: 构建 tradeMap（日期 → 交易列表）**

在 `filteredHistory` useMemo 后面加：

```ts
const tradeMap = useMemo(() => {
  const map = new Map<string, Transaction[]>()
  for (const tx of transactions) {
    const list = map.get(tx.trade_date) ?? []
    list.push(tx)
    map.set(tx.trade_date, list)
  }
  return map
}, [transactions])
```

**Step 5: 验证编译**

```bash
npm run build 2>&1 | grep -E "error|✓"
```

**Step 6: Commit**

```bash
git add frontend/src/pages/FundDetail.tsx
git commit -m "feat(fund-detail): 加载交易数据并构建 tradeMap"
```

---

### Task 3: 图表标注买卖点

**Files:**
- Modify: `frontend/src/pages/FundDetail.tsx`

**Step 1: 引入 ReferenceDot**

修改第 5 行 recharts import，追加 `ReferenceDot`：

```ts
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceDot,
  PieChart as RechartsPieChart, Pie, Cell, Legend,
} from 'recharts'
```

**Step 2: 在 AreaChart 内加 ReferenceDot**

找到 `<Area ... />` 结束标签之后、`</AreaChart>` 之前，插入：

```tsx
{filteredHistory.flatMap((point) => {
  const txs = tradeMap.get(point.date)
  if (!txs || txs.length === 0) return []
  // 同日有买入优先显示买入色
  const hasBuy = txs.some((t) => t.direction === 'buy')
  const color = hasBuy ? '#ef4444' : '#10b981'
  return [
    <ReferenceDot
      key={point.date}
      x={point.date}
      y={point.nav}
      r={5}
      fill={color}
      stroke="#fff"
      strokeWidth={2}
    />
  ]
})}
```

**Step 3: 验证编译并目测效果**

```bash
npm run build 2>&1 | grep -E "error|✓"
# 启动开发服务器
npm run dev
```

在浏览器访问有交易记录的基金详情页，确认净值图上出现红/绿圆点。

**Step 4: Commit**

```bash
git add frontend/src/pages/FundDetail.tsx
git commit -m "feat(fund-detail): 在净值走势图标注买入/卖出圆点"
```

---

### Task 4: 底部买卖明细表格

**Files:**
- Modify: `frontend/src/pages/FundDetail.tsx`

**Step 1: 引入 formatCNY**

确认第 9 行 utils import 包含 `formatCNY`：

```ts
import { cn, formatPercent, formatCNY } from '@/lib/utils'
```

**Step 2: 在页面最底部（`</div>` 闭合 `space-y-6` 前）追加 section**

找到组件 return 最后的 `</div>`（`space-y-6` 根容器），在关闭前插入：

```tsx
{/* ---- 买卖明细 ---- */}
<div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
  <div className="flex items-center gap-2 mb-4">
    <TrendingUp className="h-5 w-5 text-slate-600" />
    <h2 className="text-lg font-semibold text-slate-800">买卖明细</h2>
    <span className="ml-auto text-xs text-slate-400">{transactions.length} 笔</span>
  </div>

  {transactions.length === 0 ? (
    <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
      暂无交易记录
    </div>
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-slate-400 border-b border-slate-100">
            <th className="text-left pb-2 font-medium">日期</th>
            <th className="text-left pb-2 font-medium">方向</th>
            <th className="text-right pb-2 font-medium">成交净值</th>
            <th className="text-right pb-2 font-medium">份额</th>
            <th className="text-right pb-2 font-medium">金额</th>
            <th className="text-right pb-2 font-medium">手续费</th>
            <th className="text-left pb-2 font-medium pl-4">备注</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {transactions.map((tx) => (
            <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
              <td className="py-2.5 text-slate-600">{tx.trade_date}</td>
              <td className="py-2.5">
                <span className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                  tx.direction === 'buy'
                    ? 'bg-red-50 text-red-600'
                    : 'bg-green-50 text-green-600',
                )}>
                  {tx.direction === 'buy' ? '买入' : '卖出'}
                </span>
              </td>
              <td className="py-2.5 text-right text-slate-700 font-mono">
                {parseFloat(tx.nav).toFixed(4)}
              </td>
              <td className="py-2.5 text-right text-slate-700">
                {parseFloat(tx.shares).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
              </td>
              <td className="py-2.5 text-right text-slate-700">
                {formatCNY(parseFloat(tx.amount))}
              </td>
              <td className="py-2.5 text-right text-slate-500">
                {parseFloat(tx.fee) > 0 ? formatCNY(parseFloat(tx.fee)) : '—'}
              </td>
              <td className="py-2.5 pl-4 text-slate-400">
                {tx.note || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )}
</div>
```

**Step 3: 验证编译**

```bash
npm run build 2>&1 | grep -E "error|✓"
```

**Step 4: 手动验证**

- 有交易记录的基金：表格正确显示，方向 badge 颜色正确，金额格式正确
- 无交易记录的基金：显示"暂无交易记录"空状态

**Step 5: Commit**

```bash
git add frontend/src/pages/FundDetail.tsx
git commit -m "feat(fund-detail): 新增底部买卖明细表格"
```

---

### Task 5: 收尾

**Step 1: 完整构建验证**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 2: Push 并更新 PR**

```bash
git push
```
