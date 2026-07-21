# 用 ty 替代 mypy Implementation Plan

> **For Claude:** 逐 Task 执行,完成即勾选并更新状态。

**Design:** [2026-07-09-ty-typechecker-design.md](./2026-07-09-ty-typechecker-design.md)
**Goal:** ty 0.0.57 替代 mypy,类型检查覆盖整个 backend(含 tests)。

---

## Tasks

### - [x] Task 1: 依赖与配置切换

**Files:** `backend/pyproject.toml`
**Steps:** dev extra `mypy>=1.0` → `ty==0.0.57`;删 `[tool.mypy]` 及 paddleocr override;ruff `select` 增 `ANN` 并配 per-file-ignores 使其仅作用于 `app/`。
**Verify:** `uv sync --extra dev && uv run ty check && uv run ruff check .`

### - [x] Task 2: 处置 5 个 ty 诊断

**Files:** `backend/app/ocr_service.py`、`backend/app/fund_source.py`、`backend/app/repositories/portfolios_repo.py`
**Steps:** ocr_service 改 `isinstance(block, TextBlock)`;fund_source 加 `# ty: ignore[invalid-assignment]`;portfolios_repo 的 mypy ignore 换 `# ty: ignore[invalid-return-type]`。
**Verify:** `uv run ty check` 零诊断;`uv run pytest` 全绿。

### - [x] Task 3: CI 与文档更新

**Files:** `.github/workflows/ci.yml`、`CLAUDE.md`、`README.md`(如有 mypy 字样)
**Steps:** backend job `uv run mypy app` → `uv run ty check`;Runbook 命令替换。
**Verify:** 人工核对 + 推 PR 后 CI 全绿。

---

## 执行情况

> 作业结束时填写

- **完成：** 全部 3 个 Task。实际处置与计划的偏差:portfolios_repo 未用 ty ignore 注释,改用 `assert row_id is not None` 窄化(同时满足 ty 与 IDE 的 Pyright,免堆多套 ignore)。
- **跳过（及原因）：** 无。
- **遗留问题：** ty 0.0.x 升级时需人工过一遍新诊断(版本已钉死 0.0.57)。
- **测试结果：** ty check 零诊断(app/ + tests/ 全覆盖)、ruff(含新增 ANN 规则)✅、pytest 64/64。
