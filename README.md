# Fund Watch — 智投基金

[![CI](https://github.com/Nikoace-clais/fund-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/Nikoace-clais/fund-watch/actions/workflows/ci.yml)

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
| 大盘指数 | `hq.sinajs.cn` | 新浪行情，3 次重试退避 |

> 估算净值 ≠ 最终成交净值，仅供盘中参考。

## 技术栈

- **后端**：FastAPI + SQLite + httpx
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS v4 + React Router v7 + Recharts
- **运行环境**：Python >=3.12 / Node.js 20.19+（Vite 7 要求）/ bun

## 工程结构

```text
fund-watch/
├── Dockerfile             # 单镜像:前端构建 + 后端运行时(非 root,含 HEALTHCHECK)
├── docker-compose.yml     # 本地/NAS 部署,挂 ./data 持久化
├── start.sh / start.ps1   # 一键启动(macOS/Linux | Windows)
├── .github/               # CI(workflows/ci.yml) + dependabot
├── backend/
│   ├── pyproject.toml     # uv 配置(依赖锁定 uv.lock)
│   ├── run.py             # 开发服务器启动(app.main:app)
│   ├── pull_quotes.py     # 定时拉取脚本
│   ├── app/
│   │   ├── main.py        # 应用装配:CORS/中间件/lifespan/路由注册
│   │   ├── core.py        # 共享常量与校验
│   │   ├── schemas.py     # Pydantic 请求模型
│   │   ├── db.py          # SQLite 初始化/连接
│   │   ├── fund_source.py # 估值/详情/搜索/指数数据源适配
│   │   ├── ocr_service.py # 截图 OCR(PaddleOCR)
│   │   ├── routers/       # health/funds/quotes/portfolio/portfolios/transactions/market/stocks/ocr/ai
│   │   ├── services/      # 业务逻辑(持仓/快照调度/OCR 流水线/AI 选基)
│   │   └── repositories/  # SQL 访问层
│   ├── tests/             # pytest(unit / integration)
│   └── data/              # SQLite + 上传截图(运行后生成)
└── frontend/
    ├── package.json
    ├── bun.lock           # bun 依赖锁定
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── routes.tsx     # 路由定义
        ├── styles/        # Tailwind CSS v4
        ├── lib/           # API 封装、TanStack Query、工具函数
        ├── services/      # 跨 API 的前端流程(如截图导入)
        ├── components/    # Layout 等共享组件
        └── pages/
            ├── Dashboard.tsx    # 概览(市场指数 + 统计卡片 + 基金池当日估值)
            ├── FundDetail.tsx   # 基金详情(走势图 + 涨幅 + 配置 + 重仓)
            ├── Portfolio.tsx    # 自选基金(持仓明细 + 收益 + 饼图)
            ├── Market.tsx       # 行情数据(大盘指数)
            ├── AiSelect.tsx     # AI 选基(流式推荐)
            ├── ImportPage.tsx   # 截图导入(OCR 识别 + 确认)
            └── StockFunds.tsx   # 持仓反查(股票 → 重仓基金)
```

## 快速启动

详见 [docs/install.md](docs/install.md)，含 macOS / Linux 一键启动、Windows 分步启动、定时拉取配置说明。

| 服务 | 地址 |
|------|------|
| 前端页面 | http://127.0.0.1:5173 |
| API 文档 | http://127.0.0.1:8010/docs |
| 健康检查 | http://127.0.0.1:8010/api/health |

## Docker 部署

单镜像形态:前端静态产物打进后端镜像,uvicorn 同源服务 API + 页面,无需配置 CORS。

```bash
docker compose up -d          # 本地构建并启动
# 或直接用 CI 推送的镜像(main 分支每次合并自动构建):
docker pull ghcr.io/nikoace-clais/fund-watch:latest
```

- 访问 `http://<host>:8010`,数据(SQLite + 上传截图)持久化在 `./data` 卷
- 容器以非 root(uid 1000)运行,首次部署确保 host 目录可写:`mkdir -p data && chown 1000:1000 data`
- AI 选基 / OCR 文本抽取需要 key:在 compose 同目录放 `.env`(`ANTHROPIC_API_KEY=...`),并解开 `docker-compose.yml` 中 `env_file` 注释
- 绑定到局域网/公网时,在 `.env` 里加 `FUND_WATCH_TOKEN=...` 开启访问令牌(见下文「可选访问令牌」)
- 仅构建 linux/amd64;PaddleOCR 模型首次启动时后台自动下载,容器需要外网

## 前端页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 概览 | 市场指数、资产统计、基金池当日估值（含基金市场） |
| `/funds/:code` | 基金详情 | NAV 走势图、阶段涨幅、资产配置饼图、重仓股票 |
| `/portfolio` | 自选基金 | 多组合持仓明细、交易记录、收益统计、持仓分布饼图 |
| `/market` | 行情数据 | 大盘指数实时点位与涨跌幅 |
| `/ai-select` | AI 选基 | 描述需求，AI 流式返回推荐（需 `ANTHROPIC_API_KEY`） |
| `/import` | 截图导入 | 持仓/交易截图 OCR 识别后批量导入 |
| `/stock-funds` | 持仓反查 | 输入股票代码，反查重仓该股票的基金 |

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

### 快照

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/snapshots/pull` | 批量拉取基金池估值并落库 |
| `GET` | `/api/snapshots/{code}?limit=30` | 盘中快照序列 |
| `GET` | `/api/cron/status` | 定时拉取调度状态 |

### 组合与持仓

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET/POST/PATCH/DELETE` | `/api/portfolios`、`/api/portfolios/{id}` | 多组合管理 |
| `GET` | `/api/portfolio/summary` | 组合汇总统计 |
| `GET` | `/api/portfolio/holdings` | 组合持仓明细 |
| `GET` | `/api/portfolio/history` | 组合历史收益曲线 |

### 交易记录

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET/POST` | `/api/funds/{code}/transactions` | 买入/卖出交易记录 |
| `DELETE` | `/api/transactions/{tx_id}` | 删除交易 |
| `GET` | `/api/funds/{code}/pnl` | 单基金盈亏 |
| `POST` | `/api/transactions/csv` | 交易 CSV 导入 |

### 市场与其他

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/market/indices` | 大盘指数 |
| `GET` | `/api/stocks/{code}/funds` | 股票反查重仓基金 |
| `GET` | `/api/ocr/status` | OCR 可用性 |
| `POST` | `/api/ocr/fund-code` | 截图 OCR 识别基金代码/名称 |
| `POST` | `/api/ocr/transaction` | 截图 OCR 识别交易记录 |
| `POST` | `/api/ai/select/stream` | AI 选基(SSE 流式,需 `ANTHROPIC_API_KEY`) |
| `GET` | `/api/health` | 健康检查 |

## AI 导入基金（OCR 之外的替代方式）

截图中的基金信息可能只有名称没有代码，OCR 识别率有限。除了 `/import` 页面的内置 OCR 导入，也可以用 AI（如 ChatGPT / Claude）识别截图内容，然后按以下 JSON 格式输出后批量导入：

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

## 可选访问令牌

默认无鉴权（本机/自用场景）。设置环境变量 `FUND_WATCH_TOKEN` 后，除 `/api/health` 外的所有 `/api/*` 请求必须带请求头 `X-Fund-Token: <token>`，否则返回 401。前端在「设置」里填写令牌，存于浏览器 localStorage 并随请求发送。

**绑定到局域网/公网时务必设置**（Docker 部署写在 compose 同目录的 `.env` 里即可）。

## 定时拉取

```bash
cd backend
uv run python pull_quotes.py
```

可挂 cron（盘中每分钟一轮，cron 最小粒度为 1 分钟），示例：

```cron
* 9-15 * * 1-5 cd /path/to/backend && uv run python pull_quotes.py
```

> 后端内置交易日判断（周一至周五且不在中国法定节假日表内），节假日不触发拉取；假日表需每年初人工更新一次。

## 下一步

- [x] 前端 AI 导入页面（粘贴 JSON → 批量添加）
- [ ] 提醒规则（涨跌阈值 + 冷却时间 + 降噪）
- [ ] 定时拉取自动化 + 状态监控
- [ ] 用户维度与分享权限
