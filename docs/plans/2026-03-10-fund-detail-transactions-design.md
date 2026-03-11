# 基金详情页买卖明细设计 — 2026-03-10

## 目标

在 FundDetail 页面：
1. 在净值折线图上用彩色圆点标注买入/卖出时机
2. 页面底部新增全宽"买卖明细"表格

## 数据层

### 前端 API
新增 `fetchTransactions(code: string)` 函数，调用已有后端接口：
```
GET /api/funds/{code}/transactions
→ { code: string; items: Transaction[] }
```

```ts
type Transaction = {
  id: number
  direction: 'buy' | 'sell'
  trade_date: string       // YYYY-MM-DD
  nav: string
  shares: string
  amount: string
  fee: string
  note?: string
  source?: string
  created_at: string
}
```

### 组件 state
FundDetail 新增 `transactions: Transaction[]`，在初始 `Promise.allSettled` 并行加载。

## 图表标点

- 构建 `tradeMap: Map<string, Transaction[]>`（key = trade_date）
- 遍历 `filteredHistory`，对存在于 `tradeMap` 的日期渲染 `<ReferenceDot>`：
  - x = date，y = 该日 nav 值
  - 买入：红色（`#ef4444`）
  - 卖出：绿色（`#10b981`）
  - 同日有买有卖：优先显示买入色
  - r=5，stroke="white"，strokeWidth=2
- Recharts `<ReferenceDot>` 放在 `<Area>` 之后，确保在折线上层渲染
- 范围切换时自动过滤（只渲染当前 `filteredHistory` 日期范围内的交易）

## 底部交易明细 section

全宽卡片（`lg:col-span-3` 或独立于 grid 之外）。

### 表格结构
| 列 | 内容 |
|----|------|
| 日期 | trade_date |
| 方向 | badge：买入（红底白字）/ 卖出（绿底白字） |
| 成交净值 | parseFloat(nav).toFixed(4) |
| 份额 | parseFloat(shares).toLocaleString() |
| 金额 | formatCNY(parseFloat(amount)) |
| 手续费 | formatCNY(parseFloat(fee)) |
| 备注 | note \|\| '—' |

- 按 trade_date 倒序（后端已返回倒序）
- 无交易时显示空状态提示
- 不支持编辑（编辑入口在 Portfolio 页面）

## 文件改动清单

1. `frontend/src/lib/api.ts` — 新增 `fetchTransactions`
2. `frontend/src/pages/FundDetail.tsx` — 加载 transactions、图表 ReferenceDot、底部表格
