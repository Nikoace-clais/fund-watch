# Fund Watch 业务合理化设计

日期：2026-03-03

## 背景

交易记录功能上线后，发现以下业务逻辑问题：

1. `funds.amount` 在不同模式下含义不同（手动金额 vs 总成本 vs 前端市值），语义混乱
2. 盈亏只计算未实现部分，忽略已实现盈亏
3. CSV 重复导入会产生重复交易
4. 删除买入记录可能导致份额为负
5. 卖出手续费存了但未纳入盈亏计算
6. `percentage` 存 DB 且基于成本而非市值

## 方案 A：渐进修复（本次实施）

### 数据模型统一

**核心原则：以「份额」为唯一核心，市值 = 份额 x 净值**

| 字段 | 变更 |
|------|------|
| `funds.amount` | 废弃，不再读写 |
| `funds.amount_mode` | 废弃 |
| `funds.percentage` | 废弃，前端实时计算 |
| `funds.holding_shares` | 所有基金都用，手动基金也存份额 |

**份额规则：**
- 有交易记录 → `holding_shares` = sum(买入) - sum(卖出)，自动，不可手动编辑
- 无交易记录 → 用户直接编辑 `holding_shares`
- 旧数据不迁移，份额显示 `-`，用户手动填

**市值 & 占比：**
- 市值 = `holding_shares x latest.gsz`，纯前端计算
- 占比 = 该基金市值 / 全部市值合计，纯前端计算
- 废弃 `/api/funds/recalc-percentage` 端点

### 完整盈亏计算

```
总成本        = sum(买入金额 + 买入手续费)
持有份额      = sum(买入份额) - sum(卖出份额)
加权成本净值  = 总成本 / sum(买入份额)

已实现盈亏 = sum(卖出金额 - 卖出份额 x 加权成本净值) - sum(卖出手续费)
未实现盈亏 = 持有份额 x (当前净值 - 加权成本净值)
总盈亏     = 已实现 + 未实现
总盈亏率   = 总盈亏 / 总成本 x 100%
```

`/api/funds/{code}/pnl` 返回新增：`realized_pnl`, `total_pnl`, `total_pnl_rate`

### Bug 修复

1. **CSV 去重** — 按 `(code, direction, trade_date, nav, shares)` 判重，已存在跳过
2. **删除买入校验** — 删除前检查：删除后 holding_shares >= 0，否则拒绝
3. **卖出手续费** — 从已实现盈亏中扣除

### 前端表格

列：代码 | 名称 | 板块 | 份额 | 市值(元) | 占比% | 估算净值 | 涨跌% | 涨跌额 | 时间 | 操作

- 份额列：有交易=自动不可编辑，无交易=可点击编辑
- 市值列：份额 x 净值，纯展示
- 占比%：前端实时算

### 盈亏卡片布局

```
持有份额  成本均价  总成本   当前净值
1000.00  1.2345  ¥1234   1.5678

已实现盈亏    未实现盈亏    总盈亏       总盈亏率
+50.00       +333.30      +383.30     +31.06%
```

## 方案 C：远期迁移路线（未来实施）

当功能复杂度增长（多用户、分红、FIFO）时：

### Phase 1 — 新增 positions 表

```sql
CREATE TABLE positions (
    code TEXT PRIMARY KEY,
    shares TEXT NOT NULL,
    cost_basis TEXT NOT NULL,
    avg_nav TEXT NOT NULL,
    realized_pnl TEXT NOT NULL DEFAULT '0',
    updated_at TEXT NOT NULL
);
```

### Phase 2 — 交易更新 positions 而非 funds

`_recompute_fund_amount()` → `_update_position()`

### Phase 3 — funds 表回归纯元数据

只保留 `code, name, sector, created_at`，持仓/盈亏来自 positions

### Phase 4 — 支持 FIFO/加权平均成本法切换

positions 增加 `cost_method`，按批次追踪每笔买入

## 关键文件

- `backend/app/db.py` — holding_shares 列（已有）
- `backend/app/main.py` — _recompute_fund_amount, _compute_pnl, CRUD 端点
- `frontend/src/App.tsx` — 表格列、盈亏卡片、份额编辑
- `frontend/src/styles.css` — 盈亏卡片样式
