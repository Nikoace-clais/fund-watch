# Fund Watch - Architecture

## 项目结构

```
fund-watch/
├── backend/                      # Python/FastAPI 后端
│   ├── pyproject.toml           # uv 配置
│   ├── uv.lock                  # 依赖锁定
│   ├── run.py                   # 开发服务器启动
│   └── src/fund_watch/          # 源代码
│       ├── main.py              # FastAPI 入口
│       ├── models/              # Pydantic 模型
│       │   └── schemas.py
│       ├── repositories/        # 数据访问层
│       │   └── fund_repo.py
│       ├── services/            # 业务逻辑层
│       │   ├── fund_service.py
│       │   └── quote_service.py
│       ├── routers/             # API 路由
│       │   ├── funds.py
│       │   └── health.py
│       └── external/            # 外部 API
│           └── eastmoney.py
│
├── frontend/                     # React/Vite 前端
│   ├── package.json             # bun 配置
│   ├── bun.lock                 # 依赖锁定
│   ├── vite.config.ts
│   ├── vitest.config.ts         # 单元测试
│   ├── playwright.config.ts     # E2E 测试
│   └── src/
│       └── test/                # 测试文件
│
└── tests/                        # 测试目录
    ├── unit/                    # 单元测试
    ├── integration/             # 集成测试
    └── e2e/                     # E2E 测试
```

## 架构模式

### 后端 - 分层架构

```
┌─────────────────────────────────────┐
│  routers/      # API 端点            │
│  - HTTP 请求处理                      │
│  - 参数校验                          │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  services/     # 业务逻辑            │
│  - 业务规则处理                       │
│  - 数据编排                          │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  repositories/ # 数据访问            │
│  - 数据库操作                        │
│  - 数据持久化                        │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  external/     # 外部服务            │
│  - 东方财富 API                      │
│  - 第三方数据源                      │
└─────────────────────────────────────┘
```

### 前端

- **bun**: 包管理器
- **Vite**: 构建工具
- **vitest**: 单元测试
- **Playwright**: E2E 测试
- **React + TypeScript + Tailwind**

## 开发命令

### 后端

```bash
cd backend

# 安装依赖
uv sync

# 运行测试
uv run pytest

# 启动开发服务器
uv run python run.py

# 代码格式化
uv run ruff check .
uv run ruff format .
```

### 前端

```bash
cd frontend

# 安装依赖
bun install

# 运行测试
bun test

# 启动开发服务器
bun run dev

# E2E 测试
bun run test:e2e
```

### 测试策略

- **单元测试**: 测试单个函数/类
- **集成测试**: 测试 API 端点
- **E2E 测试**: 测试完整用户流程

当前状态: **23 个测试通过**

## 截图导入功能

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/import/preview` | POST | 上传截图，返回识别预览 |
| `/api/import/confirm` | POST | 确认导入选中的基金 |
| `/api/import/ai` | POST | AI辅助识别（预留接口） |

### 识别策略

1. **代码提取**: 识别 6 位数字基金代码
2. **表格解析**: 从表格结构中提取基金信息
3. **模糊匹配**: 使用 rapidfuzz 匹配基金名称

### 置信度机制

- **高置信度 (≥0.85)**: 直接代码匹配
- **中置信度 (0.75-0.84)**: 表格或模糊匹配
- **低置信度 (<0.75)**: 需要人工确认

### 前端组件

- **ImportPreview**: 上传和预览组件
- **ImportPage**: 完整页面（包含成功状态）

### 测试状态

| 类型 | 数量 | 状态 |
|------|------|------|
| 后端单元测试 | 23 | ✅ 通过 |
| 前端单元测试 | 10 | ✅ 通过 |
| **总计** | **33** | **✅ 全部通过** |
