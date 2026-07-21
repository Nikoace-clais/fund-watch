# 代码格式化落地 Implementation Plan

> **For Claude:** 逐 Task 执行,完成即勾选并更新状态。

**Design:** [2026-07-09-format-tooling-design.md](./2026-07-09-format-tooling-design.md)
**Goal:** ruff format + prettier 统一格式,CI 门禁,独立 commit。

---

## Tasks

### - [x] Task 1: 配置与一次性重排

**Files:** `frontend/.prettierrc`、`frontend/package.json`、全量源码(机械)
**Steps:** 写 .prettierrc;加 `format:check` script;`prettier --write .`;backend `uv run ruff format .`。
**Verify:** `ruff format --check` / `prettier --check` 零告警;pytest、ty、ruff check、tsc、vitest、vite build 全绿。

### - [x] Task 2: CI 门禁与文档

**Files:** `.github/workflows/ci.yml`、`CLAUDE.md`
**Steps:** 两个 job 各加 format check 一步;Runbook 补命令。
**Verify:** 推 PR 后 CI 全绿。

---

## 执行情况

> 作业结束时填写

- **完成：** 全部 2 个 Task。计划外补充:`.prettierignore`(排除 dist/,否则 format:check 扫构建产物)。
- **跳过（及原因）：** 无。
- **遗留问题：** 无。
- **测试结果：** ruff format --check 52/52 ✅、prettier --check ✅、ruff check ✅、ty ✅、pytest 64/64、tsc ✅、vitest 16/16、vite build ✅。
