# Fund Watch - Architecture

## 后端现状（重要）

**生产后端是 `backend/app/`，已完成分层拆分**（routers / services / schemas）。
历史遗留的 `backend/src/fund_watch/` 已删除（新浪指数数据源已移植到 `app/fund_source.py`）。

修改或新增接口时一律改 `backend/app/`。

## 项目结构

```
fund-watch/
├── backend/                      # Python/FastAPI 后端
│   ├── pyproject.toml           # uv 配置
│   ├── uv.lock                  # 依赖锁定
│   ├── run.py                   # 开发服务器启动（app.main:app）
│   ├── app/                     # ★ 生产后端（分层架构）
│   │   ├── main.py              # 应用装配：CORS/中间件/lifespan/路由注册
│   │   ├── core.py              # 共享常量与校验
│   │   ├── schemas.py           # Pydantic 请求模型
│   │   ├── db.py                # SQLite 初始化/连接（FUND_WATCH_DB 可覆盖）
│   │   ├── fund_source.py       # 估值/详情/搜索数据源适配
│   │   ├── ocr_service.py       # 截图 OCR（rapidocr）
│   │   ├── routers/             # API 路由（health/funds/quotes/portfolio/
│   │   │                        #   transactions/dca/ocr/market）
│   │   └── services/            # 业务逻辑（holdings/snapshots/dca）
│   └── tests/                   # pytest（unit / integration，含 app 集成测试）
│
└── frontend/                     # React/Vite 前端
    ├── package.json             # bun 配置
    ├── bun.lock                 # 依赖锁定
    ├── vite.config.ts
    ├── vitest.config.ts         # 单元测试
    ├── playwright.config.ts     # E2E 测试
    └── src/
        └── test/                # 测试文件
```

## 架构模式

### 后端 - 分层架构（`app/`）

```
┌─────────────────────────────────────┐
│  routers/      # API 端点            │
│  - HTTP 请求处理                      │
│  - 参数校验（schemas.py）             │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  services/     # 业务逻辑            │
│  - holdings: 份额重算 + P&L          │
│  - snapshots: 快照拉取 + 调度器       │
│  - dca: 定投绩效统计                  │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  db.py / fund_source.py             │
│  - SQLite 数据访问                   │
│  - 东方财富/新浪等外部数据源           │
└─────────────────────────────────────┘
```

### 路由注册顺序

字面量路由必须先于参数化路由注册（如 `POST /api/funds/batch` 先于
`POST /api/funds/{code}`），各 router 内的声明顺序已保证这一点，
新增路由时注意保持。

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

当前状态: **后端 22 个测试通过（含 19 个 app 集成测试）**

## 截图导入功能

### API 端点（生产后端 `app/`）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ocr/fund-code` | POST | 上传截图，OCR 识别基金代码/名称 |
| `/api/funds/search?q=` | GET | 按代码补全基金名称（预览阶段） |
| `/api/funds/batch` | POST | 确认导入选中的基金 |

前端封装在 `frontend/src/services/import.ts`（`previewImport` / `confirmImport`），UI 为 `/import` 页面。

### 识别策略

1. **代码提取**: OCR 识别 6 位数字基金代码（高置信度）
2. **名称回退**: 识别不到代码时提取中文基金名，调搜索接口模糊匹配（中置信度）

### 置信度机制

- **高置信度 (≥0.85)**: 直接代码匹配
- **中置信度 (0.75-0.84)**: 基金名模糊匹配
- **低置信度 (<0.75)**: 代码无法对应到基金，需要人工确认

### 前端组件

- **ImportPreview**: 上传和预览组件（拖拽上传、置信度标识、批量选择）
- **ImportPage**: 完整页面（适配 Layout、成功状态、使用提示）
- **集成位置**: 
  - 侧边栏导航（截图导入）
  - Dashboard 快捷入口按钮

### 路由配置

```tsx
{ path: 'import', Component: ImportPage }
```

### 样式适配

- 使用 slate 设计系统（与现有组件一致）
- 渐变提示卡片
- 统一的圆角和阴影

### 测试状态

| 类型 | 数量 | 状态 |
|------|------|------|
| 后端测试（含 app 集成测试） | 22 | ✅ 通过 |
| 前端单元测试 | 10 | ✅ 通过 |
| **总计** | **32** | **✅ 全部通过** |

### 开发服务器

#### 方式一：一键启动（推荐）

```bash
./start.sh
```

自动启动前后端服务，带彩色日志和优雅关闭。

#### 方式二：分别启动

```bash
# 后端
cd backend && uv run python run.py

# 前端（新终端）
cd frontend && bun run dev
```

访问 http://localhost:5173/import 使用截图导入功能

### 日志系统

#### 后端日志格式

```
13:37:42 | INFO     | 🚀 Starting Fund Watch API
13:37:42 | INFO     | ✅ Database initialized
13:37:45 | INFO     | GET    /api/health                   200    2.3ms
13:37:46 | INFO     | 📸 Starting OCR on 12543 bytes image
13:37:48 | INFO     | ✅ OCR completed in 2.15s, extracted 12 lines
13:37:48 | INFO     | ✅ Preview generated in 2.18s | Total: 5 | High conf: 3 | Need review: 1 | Avg conf: 82%
```

特点：
- 彩色级别显示（绿色 INFO、黄色 WARNING、红色 ERROR）
- HTTP 请求带耗时统计
- Emoji 图标直观标识操作类型
- 结构化业务日志（OCR、导入等）

#### 日志文件

```bash
# 实时查看日志
tail -f logs/backend.log
tail -f logs/frontend.log
```
