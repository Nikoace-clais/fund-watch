# 交易表单增强 + QDII 持仓明细 Design Document

**Date:** 2026-07-06
**Status:** Approved
**Executor:** Sonnet（最新）

## Goal

1. 交易录入体验：`HoldingEditModal` 卖出时按当前持仓份额的百分比快捷选择（25%/50%/75%/全部）；买卖均可输入当天交易金额反算份额（金额 = 本金，份额 = 金额 ÷ 净值）。
2. QDII 持仓明细：基金详情页「重仓股票」对 QDII 显示"暂无持仓数据"。实测根因是 eastmoney jjcc 接口对 QDII 正常返回数据（美股字母代码如 `ASML`、港股 5 位代码如 `02513`），但 `_HOLDING_ROW_RE` 正则把股票代码写死为 6 位数字、单元格 class 写死为 `tol`/`tor`（QDII 行是 `toc`），解析为空。放宽正则即可。

## 方案

### 数据模型

无。

### Backend API

无新增/变更接口。仅修改 `backend/app/fund_source.py` 的 `_HOLDING_ROW_RE`：

```python
_HOLDING_ROW_RE = re.compile(
    r"<tr><td>\d+</td>"                     # 序号
    r"<td[^>]*>.*?>([A-Z0-9.]+)</a></td>"   # 股票代码（A股6位/港股5位/美股字母）
    r"<td[^>]*>.*?>([^<]+)</a></td>"        # 股票名称
    r".*?"
    r"<td[^>]*>([\d.]+)%</td>"              # 占净值比例
    r"<td[^>]*>([\d,.]+)</td>"              # 持股数(万股)
    r"<td[^>]*>([\d,.]+)</td></tr>",        # 持仓市值(万元)
    re.DOTALL,
)
```

复用现有接口：`GET /api/funds/{code}/pnl?portfolio_id=`（返回 `holding_shares` 字符串）供前端取可卖份额。

### Frontend

- `lib/api-endpoints.ts` 新增 `fetchFundPnl(code, portfolioId?)`，类型加到 `lib/api-types.ts`（最小字段：`has_transactions`、`holding_shares?`）。
- `components/HoldingEditModal.tsx`：
  - 打开时拉取 pnl，卖出方向显示"可卖 X 份"及 25%/50%/75%/全部快捷按钮（全部用 `holding_shares` 原字符串防精度超卖，其余向下截断 2 位）。
  - 交易金额从只读预估改为可编辑输入，与份额双向联动（onChange 互算，不用 useEffect，避免循环）。
  - 手续费自动计算、提交 payload 均不变。

## 不做什么

- 不给买入加百分比（无天然基数，已与用户确认）。
- 不改后端交易接口/表结构（amount 仍由后端按 nav×shares 计算）。
- 不处理 ETF 联接基金（270042/000834）持仓数据陈旧问题——数据源现实。
- 不给 QDII 重仓股加行情/反查链接（`TopHoldings` 本无链接；反查页仅支持 A 股 6 位码）。

## 风险与权衡

- eastmoney jjcc HTML 结构变化会使正则失效——原有风险，新正则更宽松反而更耐变。
- 百分比卖出小数处理：向下截断 + 全部用原字符串，规避后端 "insufficient shares" 报错。
