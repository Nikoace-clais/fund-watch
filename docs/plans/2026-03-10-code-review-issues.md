# 代码审查问题清单 — 2026-03-10

审查范围：`81b8aa1..470d353`（portfolio history、CRON 调度、导入基金每日收益）

---

## Critical（必须修）

### C1 · 历史走势今日点：导入基金用成本价而非市值
**文件** `backend/app/main.py:921-926`

历史各日期点 = `implied_shares × nav`（市场价），但今日点直接 `+= holding_amount`（原始成本/导入金额）。两套计算口径不一致，图表在最后一天出现断层跳跃。

**修复方案**：今日点改为 `implied_shares[code] × gsz_map[code]`，与历史点保持一致；若 gsz 不可用则 fallback 到 `holding_amount`。

---

### C2 · 今日估算点覆盖已确认净值
**文件** `backend/app/main.py:928`

```python
date_totals[today] = today_total  # 直接覆盖
```

若当日净值已通过历史数据写入（例如下午 3 点后运行），实时 gsz 会替换掉更准确的确认值。

**修复方案**：改为 `date_totals.setdefault(today, today_total)`，仅在该日期无数据时才插入。

---

### C3 · 卖出时买入份额为 0 导致 P&L 静默错误
**文件** `backend/app/main.py:229-234`

`buy_shares == 0` 时 `avg_cost_nav = 0`，卖出 P&L = `sell_amount - sell_fee`，结果虚高。不会报错，但数据错误。

**修复方案**：当 `buy_shares == 0` 时拒绝卖出交易，或在 `_compute_pnl` 内标记该笔为异常并返回 None。

---

### C4 · CORS 全开放
**文件** `backend/app/main.py:108-113`

```python
allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
```

所有写入端点对任意来源可访问。MVP 阶段本地风险低，但后续暴露到 LAN/公网会有安全隐患。

**修复方案**：限制为 `["http://127.0.0.1:5173", "http://localhost:5173"]`，或从环境变量读取白名单。

---

## Important（应修）

### I1 · 总收益率被导入基金拉高
**文件** `backend/app/main.py:764-770`

导入基金有 `current_value` 但 `total_cost = None`（不计入分母）。导入基金占比越高，`total_return_rate` 虚高越明显；若全部为导入基金则返回 0（分母为 0）——数据无意义。

**修复方案**：`total_return_rate` 仅在 `total_cost > 0` 时计算；混合组合可标注 "部分基金无成本数据"。

---

### I2 · asyncio.gather 内部 N+1 DB 连接
**文件** `backend/app/main.py:675`（`portfolio_summary`），`main.py:500`（`funds_overview`）

每个基金在 gather 内部各自 `get_conn()`，20 只基金同时开 20 个 SQLite 连接。WAL 模式可缓解，但仍不是设计意图。

**修复方案**：在 gather 前批量查询所有 PnL 数据（一次 `conn.execute` + IN 子句），gather 只做 HTTP 请求。

---

### I3 · fund_snapshots 无限增长 + 缺复合索引
**文件** `backend/app/db.py`

- 无数据修剪：25 只基金 × 100 次/天 × 250 交易日 ≈ 625,000 行/年
- `ORDER BY id DESC LIMIT 1` 走 `idx_snapshots_code` 单列索引，需扫描该 code 的全部快照

**修复方案**：
1. 添加复合索引 `CREATE INDEX idx_snapshots_code_id ON fund_snapshots(code, id DESC)`
2. 定期清理旧快照，如保留最近 30 天（可在 CRON 调度器里每天跑一次）

---

### I4 · 历史 NAV 无缓存，每次切换范围都重拉
**文件** `backend/app/main.py:857`

用户点击 1月/3月/6月/1年 按钮，前端重新请求 `/api/portfolio/history?limit=N`，后端对每只基金都重新发起外部 HTTP 请求拉历史 NAV。10 只基金 × 4 个范围 = 40 次外部调用。

**修复方案**：在 `fund_source.py` 添加进程内 LRU 缓存（`functools.lru_cache` 或 `cachetools.TTLCache`），TTL = 10 分钟。

---

### I5 · api.ts 类型与后端实际返回不一致
**文件** `frontend/src/lib/api.ts:71-75`

`fetchPortfolioSummary` 返回类型里 `shares`、`nav`、`total_cost`、`return_rate` 标为非空 `string`，但导入基金对应字段后端返回 `null`。`Portfolio.tsx` 本地类型已加 `| null`，但 api.ts 的类型声明不准确，TypeScript 无法在调用侧给出警告。

**修复方案**：将这些字段改为 `string | null`，与 `Portfolio.tsx` 本地类型对齐。

---

### I6 · 导入基金 NAV 拉取失败时静默排除
**文件** `backend/app/main.py:882-886`

`nav_dict` 为空时 `implied_shares` 不写入该 code，该基金在历史图中消失，无任何错误提示或日志。

**修复方案**：记录 warning 日志；API 响应可附带 `excluded_codes` 字段，前端提示用户。

---

## Suggestion（优化项）

### S1 · `getColorForReturn` 是死代码
**文件** `frontend/src/lib/utils.ts:16-20`

所有页面已改用 `useColor().colorFor`，旧函数未删除，混淆后来者。

---

### S2 · Dashboard "市场热度" 卡片硬编码
**文件** `frontend/src/pages/Dashboard.tsx:141`

```tsx
<p className="text-2xl font-bold text-orange-500">适中</p>
```

是未删除的占位符，应接入真实指数数据或整张卡片先隐藏。

---

### S3 · `bestFund` 用 `parseFloat('-Infinity')` 返回 NaN
**文件** `frontend/src/pages/Portfolio.tsx:265-268`

```typescript
parseFloat('-Infinity')  // → NaN，不是负无穷
```

所有导入基金 `return_rate === null` 时，`bestFund` 会错误地返回第一个元素。

**修复方案**：sentinel 改为 `Number.NEGATIVE_INFINITY`（直接用数字比较，不经过 `parseFloat`）。

---

### S4 · HoldingEditModal 读原始费率而非优惠费率
**文件** `frontend/src/components/HoldingEditModal.tsx:43`

注释说"优先读优惠费率"，但代码读的是 `subscription_rate`（原始），自动算出的手续费偏高。

**修复方案**：改为 `d.subscription_rate_discounted ?? d.subscription_rate ?? null`。

---

### S5 · 搜索词无长度限制
**文件** `backend/app/main.py:961`

`q` 参数直接透传到外部 API，无最大长度保护。

**修复方案**：`if len(q) > 50: raise HTTPException(400, "搜索词过长")`

---

## 优先级建议

| 优先级 | 编号 | 预计改动量 |
|--------|------|-----------|
| 本次修复 | C1、C2、S3、S4 | 小，各 1-5 行 |
| 下个迭代 | C3、C4、I1、I5 | 中 |
| 技术债排期 | I2、I3、I4、I6、S1、S2、S5 | 中大 |
