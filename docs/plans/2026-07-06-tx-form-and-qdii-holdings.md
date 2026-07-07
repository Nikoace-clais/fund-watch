# 交易表单增强 + QDII 持仓明细 Implementation Plan

> **For Claude:** 逐 Task 执行，完成即勾选并更新状态；编码实施使用最新 Sonnet 模型。

**Design:** [2026-07-06-tx-form-and-qdii-holdings-design.md](2026-07-06-tx-form-and-qdii-holdings-design.md)
**Goal:** 卖出按持仓百分比快捷选份额、买卖按金额反算份额；修复 QDII 重仓股解析为空。

---

## Tasks

### - [x] Task 1: 后端放宽持仓解析正则支持 QDII

**Files:** `backend/app/fund_source.py`（`_HOLDING_ROW_RE`）、新增 `backend/tests/unit/test_fund_holdings_parse.py`
**Steps:** 按设计文档替换正则；新增单测，用 A 股（161725 行，class `tol`/`tor`）与 QDII（270023 行，class `toc`，美股 `ASML` + 港股 `02513`）两段真实 HTML 片段断言解析出 code/name/percentage。
**Verify:** `uv run pytest tests/unit/test_fund_holdings_parse.py` + `uv run ruff check .` + `uv run mypy .`

### - [x] Task 2: 前端卖出百分比 + 金额反算

**Files:** `frontend/src/lib/api-endpoints.ts`、`frontend/src/lib/api-types.ts`、`frontend/src/components/HoldingEditModal.tsx`
**Steps:** 新增 `fetchFundPnl`；modal 打开时取 `holding_shares`，卖出方向显示可卖份额 + 25%/50%/75%/全部按钮（全部用原字符串，其余向下截断 2 位）；交易金额改为可编辑输入并与份额双向联动（onChange 互算）；手续费与提交逻辑不变。
**Verify:** `bun run lint`

### - [x] Task 3: 端到端验证

**Files:** 无
**Steps:** 启动 `./start.sh`；QDII 270023 详情页「重仓股票」显示美股/港股持仓，A 股基金无回归；买入输入金额反算份额；卖出显示可卖份额、点百分比填充、全部卖出不报 "insufficient shares"。
**Verify:** 手动流程 + 全量 `uv run pytest`

---

## 执行情况

- **完成：** Task 1-3 全部完成（2026-07-06，编码由 Sonnet subagent 执行，主会话审查 + 验证）。
- **跳过（及原因）：** 全部卖出后真实提交（避免向用户数据库写入真实卖出交易，仅验证到表单填充；后端超卖校验已有单测覆盖）。
- **遗留问题：** ETF 联接型 QDII（如 270042/000834）数据源本身只披露到 2022-2023 年旧数据，属天天基金数据现实，不修。ruff/mypy 存量报错（26/227 条）为改动前已有，与本次无关。
- **测试结果：** 后端 `uv run pytest` 全量 64 passed（含新增 `test_fund_holdings_parse.py` 2 例）；前端 `bun run lint` 通过。真实数据源验证：270023/001668（QDII，美股+港股代码）与 161725（A 股）均解析出 10 条持仓。UI 冒烟（Playwright）：QDII 详情页「重仓股票」正常展示；买入输金额 1000 反算份额 158.02、手续费自动 1.50；卖出显示「可卖 4791.67」，50% 填 2395.83（向下截断），全部填原字符串 4791.67，金额同步联动。
