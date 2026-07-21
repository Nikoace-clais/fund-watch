# 代码格式化落地 Design Document

**Date:** 2026-07-09
**Status:** Approved（用户确认:落地,格式化独立 commit,CI 加门禁）
**Executor:** 主会话（纯机械改动）

## Goal

统一前后端代码格式并在 CI 设门禁,消除风格漂移。**零新依赖**:后端用 ruff 自带的 `ruff format`(与 uv/ty 同属 Astral 工具链),前端用已在 devDependencies 的 prettier。

## 方案

- **前端**:新增 `.prettierrc`(`singleQuote: true, semi: false`,依现状统计:284 处单引号 vs 0 双引号,分号仅测试文件少量存在),`prettier --write .` 一次性重排(~87 文件);package.json 加 `format:check` script。
- **后端**:`ruff format .` 一次性重排(20/52 文件),默认配置(行宽 88,与已启用的 ruff lint 规则兼容)。
- **CI**:backend job 加 `uv run ruff format --check .`,frontend job 加 `bun run format:check`。
- **CLAUDE.md**:Runbook 补 format 命令。

## 不做什么

- 不引入 Biome 等新工具(prettier 已在依赖里,复用)。
- 不给 prettier 加更多风格项(贴现状、最小 diff 即止)。

## 风险与权衡

- 一次性 ~107 文件机械 diff:独立 commit 隔离,review 按 commit 分开看。
- 与未合分支的冲突风险:本仓库单人开发,无并行分支,可忽略。
