# 历史数据底座（NAV History Base）Implementation Plan

> **For Claude:** 逐 Task 执行，完成即勾选并更新状态；编码实施使用最新 Sonnet 模型。

**Design:** 无独立 design 文档（方案已在任务书中批准，见分支 `feat/nav-history` 任务描述）
**Goal:** 净值历史落库（fund_nav_history 表）+ DB 优先的读取服务 + 每日调度增量同步 + 快照分层保留，为后续指标计算提供历史数据底座。

---

## Tasks

### - [x] Task 1: Schema — fund_nav_history 表

**Files:** `backend/app/db.py`
**Steps:** 在 `init_db()` 中按 `CREATE TABLE IF NOT EXISTS` 惯例新增 `fund_nav_history(code, date, nav, acc_nav, captured_at, PRIMARY KEY(code, date))` 与索引 `idx_nav_history_date(date)`；幂等，不动 user_version 迁移机制。
**Verify:** `pytest tests/unit/test_db_migration.py` + 新 repo 测试通过。

### - [x] Task 2: Repository — nav_history_repo

**Files:** `backend/app/repositories/nav_history_repo.py`
**Steps:**
- `upsert_many(conn, code, rows)`：INSERT OR REPLACE 批量，rows 为 `fund_source.fetch_nav_history` 返回形状（`{date, nav, accNav, dailyReturn}`，只取 date/nav/accNav）。
- `list_range(conn, code, limit)`：按 date 升序返回最近 limit 条。
- `latest_date(conn, code) -> str | None`：增量锚点（MAX(date)）。
**Verify:** `pytest tests/unit/test_nav_history_repo.py`。

### - [x] Task 3: Service — nav_history + 路由切换

**Files:** `backend/app/services/nav_history.py`、`backend/app/routers/funds.py`
**Steps:**
- `get_nav_history(code, limit)`：DB 优先；DB 为空或（当前 CST 是交易日且已过 15:30 且 latest_date < 今天）→ 调 `fetch_nav_history` 拉全量 → upsert 落库 → 读 DB 返回。非交易日或盘中不强制刷新。
- `sync_pool_nav_history()`：遍历 `funds_repo.list_codes` 逐只增量同步，单只失败 `safe_await` 降级记日志不阻塞，返回 `{synced, failed}` 计数。
- 路由 `/api/funds/{code}/nav-history` 改走 service，响应形状 `{code, count, history}` 保持不变（history 项 `{date, nav, accNav}`，dailyReturn 前端类型本就是 optional）。
**Verify:** `pytest tests/unit/test_nav_history_service.py` + 端点集成测试。

### - [x] Task 4: 调度接入 + 快照分层保留

**Files:** `backend/app/services/snapshots.py`、`backend/app/repositories/snapshot_repo.py`
**Steps:**
- 每日 prune 分支：若当日是交易日且 CST >= 15:30 → `create_task(sync_pool_nav_history())` 后台跑不阻塞主循环，记日志；启动时同样检查一次（白天重启补同步）。
- `snapshot_repo.prune_older_than` 改分层：每个自然日保留 id 最大一条永久保留，其余盘中快照超 30 天才删；`date(captured_at)` 按 UTC 日界分组（可接受，注释说明）。prune 日志文案同步为分层语义。
**Verify:** `pytest tests/unit/test_snapshot_prune.py`。

### - [x] Task 5: 测试

**Files:** `backend/tests/unit/test_nav_history_repo.py`、`backend/tests/unit/test_nav_history_service.py`、`backend/tests/unit/test_snapshot_prune.py`、`backend/tests/integration/test_app_api.py`（nav-history 端点用例改为 mock service 层）
**Steps:** mock 上游不碰真网络：repo upsert 幂等/list_range 排序 limit/latest_date 空与非空；service DB 有今日数据不拉上游/DB 空拉上游落库/增量只补新日期；分层 prune（40 天×每日 3 条）；端点响应形状不变。
**Verify:** 四条门禁全绿。

---

## 执行情况

> 作业结束时填写

- **完成：** Task 1–5 全部完成。fund_nav_history 表落 db.py init_db()（幂等，未动 user_version）；nav_history_repo 三函数（upsert_many 幂等覆盖、list_range 升序 limit、latest_date 锚点）；services/nav_history.py 实现 DB 优先 + 15:30 后增量刷新 + sync_pool_nav_history 全池同步（单只失败 safe_await 降级），路由改走 service 且响应形状不变；snapshots.py 每日 prune 分支接入净值同步（create_task 后台 + 强引用防 GC），prune 改分层保留（每日 id 最大一条永留，盘中超 30 天删，UTC 日界分组已注释说明）。
- **跳过（及原因）：** 无。
- **遗留问题：**
  1. ~~DB 出数不带 dailyReturn~~ 已解决：schema 补 `daily_return` 列（源 equityReturn 落库，除息日环比推导会失真故不推导），响应恢复 {date, nav, accNav, dailyReturn}，前端风险指标不受影响（测试 138 passed 含 roundtrip 用例）。
  2. 盘中/非交易日端点不强制刷新，首次建底后 DB 为空才会拉；非交易日请求历史返回的是库内既有数据（符合方案）。
  3. GitNexus 索引需在提交后重跑 `npx gitnexus analyze` 刷新（本次未执行任何 git 提交）。
- **测试结果：** ruff check 全过；ruff format --check 67 文件全 formatted；ty check 全过；pytest 138 passed（新增 15 条：repo 7 + service 4 + prune 1 + 端点 3）。
