# Fund-Watch 代码评审报告（2026-03-03）

## 评审结论（摘要）
- 项目整体结构清晰，后端+前端主流程可读性较好。
- 前端构建通过（Vite build 成功）。
- 发现 **2 个高优先级契约问题**（会直接影响功能正确性）。
- 发现若干中低优先级改进项（稳定性/一致性/上线体验）。

---

## 已执行检查

1. 基线与分支
- 分支：`review/fund-watch-v1`
- 代码来源：`origin/main`

2. 可运行性
- Backend：依赖安装后可导入 `Fund Watch API 0.2.0`
- Frontend：`npm run build` 成功

3. 关键文件审阅
- `backend/app/main.py`
- `backend/app/db.py`
- `backend/app/fund_source.py`
- `backend/app/ocr_service.py`
- `frontend/src/App.tsx`

---

## 问题清单

### P1-01 前后端契约不一致：金额编辑无法保存

**现象**
- 前端 `saveAmount()` 调用：`PATCH /api/funds/{code}`，body 为 `{ amount }`
- 后端 `UpdateFundPayload` 只接受 `holding_shares`、`sector`，不处理 `amount`
- 结果：请求返回 `400: nothing to update`，页面“金额可编辑”功能实际失效

**影响**
- 用户无法在 UI 中修改持仓金额（核心交互受损）

**建议修复**
- 在 `UpdateFundPayload` 中加入 `amount: float | None`
- `update_fund` 支持 `amount` 更新，并与 `recalc-percentage` 联动

---

### P1-02 前后端契约不一致：PnL 字段命名不匹配

**现象**
- 前端 `PnlData` 使用字段：`pnl`、`pnl_rate`
- 后端 `/api/funds/{code}/pnl` 返回字段：`total_pnl`、`total_pnl_rate`（以及 realized/unrealized）

**影响**
- PnL 卡片可能显示为空或错误（字段读取不到）

**建议修复（二选一）**
1. 后端兼容返回：补充 `pnl=total_pnl`、`pnl_rate=total_pnl_rate`
2. 前端统一改字段：全面使用 `total_pnl`、`total_pnl_rate`

> 推荐后端兼容一段时间，减少前端破坏性改动。

---

### P2-01 CSV 导入可写入“未在基金池中的 code”

**现象**
- `/api/transactions/csv` 导入时没有确保 `funds` 中存在对应 code
- 会出现 transactions 有记录但 funds 无该基金（孤儿交易）

**影响**
- 数据一致性下降；某些页面/统计会出现隐式遗漏

**建议修复**
- 导入前校验基金是否存在；不存在则：
  - 方案A：自动创建基金（推荐，用户体验更好）
  - 方案B：记入 errors 并跳过（更严格）

---

### P2-02 OCR 金额正则偏严，可能漏识别整数金额

**现象**
- `AMOUNT_RE` 目前只匹配 `1234.56` 这类带小数格式
- `¥1200` 或 `1200元` 可能识别不到

**建议修复**
- 正则改为同时支持整数与小数（例如 `\d+[\d,]*(?:\.\d{1,2})?`）

---

### P3-01 前端包体偏大（560KB+）

**现象**
- Vite 构建提示 chunk > 500k

**影响**
- 首屏加载可再优化

**建议修复**
- 图表区动态加载（`import()`）
- 交易/OCR模块可拆分路由级代码分割

---

## 建议修复顺序

1. **先修 P1-01 / P1-02**（保证主流程正确）
2. 修 **P2-01**（数据一致性）
3. 修 **P2-02**（OCR 识别覆盖率）
4. 最后做 **P3-01**（性能优化）

---

## 可发布性判断

- 现阶段可用于内部演示/联调。
- 若要对外试用，建议先完成 P1 两项修复后再开放。
