# 用 ty 替代 mypy Design Document

**Date:** 2026-07-09
**Status:** Approved（用户指示:搜索评估 ty,可行则先写文档再切换）
**Executor:** 主会话（Sonnet 会话额度受限;改动小,主会话直接执行）

## Goal

用 Astral 的 ty(Rust 实现的类型检查器,ruff/uv 同门)替代 mypy,统一 Astral 工具链并把类型检查扩展到 `tests/` 目录。

## 评估结论(实测 ty 0.0.57)

| 维度 | 结果 |
|---|---|
| 覆盖范围 | `ty check .` 含 tests/ 仅 5 个诊断(mypy strict 在 tests/ 有 84 个存量错误,只能检查 app/) |
| 速度 | 0.2s vs mypy 1.4s(本仓库规模下两者都够快,非主要动机) |
| 成熟度 | beta(0.0.x),官方目标 2026 内 1.0;版本间可能有破坏性变更 → **钉死版本** |
| 第三方库 | Pydantic/FastAPI 一等支持仍在路线图上;本仓库实测仅 cachetools 存根触发 1 个误报 |

5 个诊断的处置:
1. `ocr_service.py:97` 根因——ty 不支持 `hasattr()` 窄化,`raw` 推成 `object`(连带 129/131 共 3 个报错)。改用 `isinstance(block, TextBlock)`,类型上也更严谨,根治。
2. `fund_source.py:116` — cachetools 存根重载推断误报,`# ty: ignore[invalid-assignment]` 压制。
3. `portfolios_repo.py:40` — `lastrowid` 确为 `int | None`,mypy 时代已 ignore,换 `# ty: ignore[invalid-return-type]`(ty 不识别 mypy 的错误码 ignore)。

## 方案

- `pyproject.toml`:dev extra 中 `mypy>=1.0` → `ty==0.0.57`(钉死);删除 `[tool.mypy]` 与 paddleocr override(ty 对惰性 import 的 paddleocr 无诊断,无需配置)。
- **补偿 mypy strict 的强制标注约束**:ruff 增开 `ANN` 规则(flake8-annotations)仅作用于 `app/`(app 已全标注,应零新增报错;tests 不启用)。
- 按上节处置 5 个诊断。
- CI(`.github/workflows/ci.yml` backend job):`uv run mypy app` → `uv run ty check`(覆盖整个 backend 含 tests)。
- 文档:CLAUDE.md Runbook 与 README 中 `uv run mypy .` 相应替换。

## 不做什么

- 不给 tests/ 补类型标注(ty 渐进式检查天然容忍,无需动存量测试)。
- 不引入 `[tool.ty]` 配置段(默认行为已满足;有需求再加)。
- 不保留 mypy 双跑(替代就是替代,双跑维护两套 ignore 注释不值)。

## 风险与权衡

- **beta churn**:ty 0.0.x 升级可能引入新诊断;版本钉死 + 升级时人工过一遍 diff,可接受。
- **强制标注约束弱化**:ty 无 mypy strict 等价模式,未标注函数只推断不报错;由 ruff ANN(仅 app/)承接该约束。
- **回退路径**:`[tool.mypy]` 配置在 git 历史里,恢复成本≈一次 revert。
