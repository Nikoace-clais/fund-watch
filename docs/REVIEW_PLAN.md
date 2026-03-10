# Fund-Watch 代码评审执行计划

## 目标
对 `origin/main` 最新代码做一轮可执行评审，重点确认：
1. 接口契约与前端调用是否一致
2. OCR 与持久化链路是否完整可靠
3. 持仓/交易/PnL 计算逻辑是否正确
4. 是否存在会阻塞上线的高优先级问题

## 范围
- Backend: `backend/app/*.py`
- Frontend: `frontend/src/App.tsx`, `frontend/src/styles.css`
- 文档与依赖: `README.md`, `package.json`, `requirements.txt`

## 执行步骤

### Step 1 — 基线确认
- 校验分支与提交历史
- 读取主要代码文件，梳理模块边界

### Step 2 — 可运行性检查
- Backend 依赖安装与应用导入检查
- Frontend 构建检查

### Step 3 — 契约一致性检查
- 核对前端请求的 API 与后端实际 schema
- 重点检查 PATCH/POST body 字段、返回字段命名、错误处理

### Step 4 — 业务逻辑检查
- 交易记录增删改与持仓份额回算
- PnL 字段定义与前端展示一致性
- OCR 金额/代码提取边界行为

### Step 5 — 输出评审结果
- 按严重度分类（P0/P1/P2）
- 给出最小修复建议和修复顺序
- 标注可立即执行的修复项

## 交付物
- `docs/REVIEW_REPORT.md`：评审结论、问题列表、建议修复顺序
