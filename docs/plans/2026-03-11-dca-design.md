# 定投模块 Design Document

**Date:** 2026-03-11
**Status:** Approved

---

## Goal

基于现有交易记录，为用户提供定投计划管理和绩效分析功能。用户可以创建定投计划、记录每期执行状态（成功/失败），成功期关联 `transactions` 表中已有的买入记录。

---

## Data Model

### 新增两张表

```sql
-- 定投计划
CREATE TABLE dca_plans (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  code         TEXT NOT NULL,
  name         TEXT,                        -- 备注名，如"每月3号定投"
  amount       TEXT NOT NULL,               -- 每期金额（元）
  frequency    TEXT NOT NULL,               -- daily / weekly / biweekly / monthly
  day_of_week  INTEGER,                     -- frequency=weekly/biweekly 时生效（0=周一）
  day_of_month INTEGER,                     -- frequency=monthly 时生效（1-28）
  start_date   TEXT NOT NULL,
  end_date     TEXT,                        -- NULL = 长期执行
  is_active    INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL
)

-- 每期执行记录
CREATE TABLE dca_records (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id        INTEGER NOT NULL REFERENCES dca_plans(id),
  scheduled_date TEXT NOT NULL,             -- 预定执行日期
  status         TEXT NOT NULL CHECK(status IN ('success','failed')),
  transaction_id INTEGER REFERENCES transactions(id),  -- success 时关联
  note           TEXT,
  created_at     TEXT NOT NULL
)
```

### 关联关系

- 成功期的 `dca_records.transaction_id` → `transactions.id`（现有买入记录）
- 失败期 `transaction_id` 为 NULL
- 删除计划时级联删除 `dca_records`，但不删除 `transactions`

---

## Backend API

```
# 计划管理
POST   /api/dca/plans                    创建定投计划
GET    /api/dca/plans                    所有计划列表（含各基金）
GET    /api/dca/plans/{plan_id}          单个计划详情
PATCH  /api/dca/plans/{plan_id}          修改计划（暂停/修改金额等）
DELETE /api/dca/plans/{plan_id}          删除计划及关联记录

# 每期执行记录
GET    /api/dca/plans/{plan_id}/records  某计划的执行记录列表
POST   /api/dca/plans/{plan_id}/records  手动新增一期记录
PATCH  /api/dca/records/{record_id}      标记成功（关联 transaction_id）或失败

# 绩效分析
GET    /api/dca/plans/{plan_id}/stats    单计划绩效统计
GET    /api/dca/stats                    全部计划汇总（跨基金对比用）
```

### 绩效统计响应格式

```json
{
  "total_periods": 12,
  "success_count": 10,
  "failed_count": 2,
  "total_invested": "5000.00",
  "avg_cost": "1.2345",
  "total_shares": "4053.68",
  "current_value": "5420.00",
  "total_return": "420.00",
  "return_rate": "8.40"
}
```

绩效计算逻辑：
- `total_invested` = 成功期关联 transactions 的 amount 之和
- `total_shares` = 成功期关联 transactions 的 shares 之和
- `avg_cost` = total_invested / total_shares
- `current_value` = total_shares × 最新净值（从 fundgz 或最近 nav-history）
- `return_rate` = (current_value - total_invested) / total_invested × 100

---

## Frontend

### FundDetail 页新增「定投计划」卡片

位置：买卖明细下方，全宽卡片。

内容：
- 列出该基金的所有定投计划，每行显示：计划名、频率、每期金额、进度（成功/总期数）、总收益率
- 点击计划 → 展开执行记录列表，每期显示：预定日期、状态 badge（成功/失败）、关联买入净值和金额
- 成功期可关联已有买入记录（弹出该基金 transactions 列表供选择）
- 操作：新建计划按钮、每期标记成功/失败

### 独立「定投」页（路由 `/dca`）

- 顶部汇总卡片：所有计划总投入、总市值、总收益率
- 下方表格：每行一个计划，列：基金名、频率、执行进度、平均成本、收益率
- 点击行跳转到对应 FundDetail

### 新建计划 Modal

字段：基金代码、备注名、每期金额、频率（daily/weekly/biweekly/monthly）、起始日期
频率为 weekly/biweekly 时显示「星期几」选择，monthly 时显示「每月几号」选择。

---

## Constraints

- 不新增单独的「定投买入」，成功期必须关联已有 transactions 记录
- 失败期不产生任何交易记录
- 删除计划不影响已关联的 transactions
- 频率：daily / weekly / biweekly / monthly
