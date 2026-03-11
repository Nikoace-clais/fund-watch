# Fund Watch — 智投基金

A 股公募基金盘中估值监控 + 自选组合管理工具。

## 功能概览

- **盘中估值**：实时拉取基金估算净值、估算涨跌幅
- **基金详情**：基金经理、规模、阶段涨幅、资产配置、重仓股票
- **NAV 走势图**：支持 1 月/3 月/半年/1 年/全部时间切换
- **自选组合**：持仓管理、收益统计、持仓分布饼图
- **AI 导入**：将基金截图交给 AI 识别，按指定 JSON 格式输出后批量导入
- **基金搜索**：按名称或代码关键词搜索基金

## 数据源

| 用途 | 来源 | 备注 |
|------|------|------|
| 实时估值 | `fundgz.1234567.com.cn` | 免费 JSONP |
| 基金详情 / NAV 历史 | `fund.eastmoney.com/pingzhongdata` | 免费 |
| 基金搜索 | `fundsuggest.eastmoney.com` | 免费 |

> 估算净值 ≠ 最终成交净值，仅供盘中参考。

## 技术栈

- **后端**：FastAPI + SQLite + httpx
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS v4 + React Router v7 + Recharts
- **运行环境**：Python 3.x / Node.js 18+

## 工程结构

```text
fund-watch/
├── CLAUDE.md              # AI 编码助手指引
├── PLAN.md                # 功能规划
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── pull_quotes.py     # 定时拉取脚本
│   ├── app/
│   │   ├── main.py        # FastAPI 入口 + 所有路由
│   │   ├── db.py          # SQLite 初始化/连接
│   │   └── fund_source.py # 估值源 / 详情 / 搜索适配
│   └── data/
│       └── fund_watch.db  # SQLite（运行后生成）
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── routes.tsx       # 路由定义
        ├── styles/          # Tailwind CSS v4
        ├── lib/
        │   ├── api.ts       # API 客户端
        │   └── utils.ts     # 工具函数
        ├── components/
        │   └── Layout.tsx   # 侧边栏布局
        └── pages/
            ├── Dashboard.tsx    # 概览（市场指数 + 统计卡片 + 热门推荐）
            ├── FundExplorer.tsx # 基金市场（搜索/筛选/排序表格）
            ├── FundDetail.tsx   # 基金详情（走势图 + 涨幅 + 配置 + 重仓）
            └── Portfolio.tsx    # 自选基金（持仓明细 + 收益 + 饼图）
```

## 快速启动

详见 [docs/install.md](docs/install.md)，含 macOS / Linux 一键启动、Windows 分步启动、定时拉取配置说明。

| 服务 | 地址 |
|------|------|
| 前端页面 | http://127.0.0.1:5173 |
| API 文档 | http://127.0.0.1:8010/docs |
| 健康检查 | http://127.0.0.1:8010/api/health |

## 前端页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 概览 | 市场指数、资产统计、热门基金推荐 |
| `/funds` | 基金市场 | 搜索/类型筛选/排序表格，点击进入详情 |
| `/funds/:code` | 基金详情 | NAV 走势图、阶段涨幅、资产配置饼图、重仓股票 |
| `/portfolio` | 自选基金 | 持仓明细、收益统计、持仓分布饼图 |

## API 接口

### 基金管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/funds` | 基金池列表 |
| `POST` | `/api/funds/{code}` | 添加基金（6 位代码） |
| `POST` | `/api/funds/batch` | 批量添加 `{ "codes": ["110011","161725"] }` |
| `DELETE` | `/api/funds/{code}` | 删除基金及关联数据 |
| `GET` | `/api/funds/overview` | 基金池 + 最新估算数据 |
| `GET` | `/api/funds/search?q=关键词` | 按名称/代码搜索基金 |

### 行情与详情

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/quote/{code}` | 实时估值 |
| `GET` | `/api/funds/{code}/detail` | 基金经理、规模、阶段涨幅、资产配置 |
| `GET` | `/api/funds/{code}/nav-history?limit=365` | 历史 NAV 序列 |
| `GET` | `/api/funds/{code}/holdings` | 重仓股票 (top 10) |

### 快照与组合

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/snapshots/pull` | 批量拉取基金池估值并落库 |
| `GET` | `/api/snapshots/{code}?limit=30` | 盘中快照序列 |
| `GET` | `/api/portfolio/summary` | 组合汇总统计 |

## AI 导入基金（替代 OCR）

截图中的基金信息可能只有名称没有代码，OCR 识别率有限。推荐使用 AI（如 ChatGPT / Claude）识别截图内容，然后按以下 JSON 格式输出，再通过 `/api/funds/batch` 批量导入：

### JSON 格式

```json
{
  "codes": ["110011", "161725", "012414"]
}
```

### 使用步骤

1. 将基金持仓截图发给 AI，附带 prompt：

   > 请识别这张图中的所有基金，输出它们的 6 位基金代码，格式为 JSON：`{"codes": ["代码1", "代码2"]}`。如果只看到基金名称，请查询对应的 6 位代码。

2. 复制 AI 返回的 JSON
3. 调用批量添加接口：

   ```bash
   curl -X POST http://127.0.0.1:8010/api/funds/batch \
     -H "Content-Type: application/json" \
     -d '{"codes": ["110011", "161725"]}'
   ```

   或直接在前端基金市场页面逐个搜索添加。

## 定时拉取

```bash
cd backend
uv run python pull_quotes.py
```

可挂 cron（盘中每 30~60 秒一轮），示例：

```cron
* 9-15 * * 1-5 cd /path/to/backend && uv run python pull_quotes.py
```

## 下一步

- [ ] 前端 AI 导入页面（粘贴 JSON → 批量添加）
- [ ] 提醒规则（涨跌阈值 + 冷却时间 + 降噪）
- [ ] 定时拉取自动化 + 状态监控
- [ ] 用户维度与分享权限
