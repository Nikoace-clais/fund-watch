# Fund Watch 使用手册

智投基金（Fund Watch）是一个 A 股公募基金盘中估值监控 + 自选组合管理工具。本手册面向使用者，覆盖安装启动、各页面功能、API 使用和常见问题。

> ⚠️ 全站显示的「估算净值 / 估算涨跌幅」为盘中估算，**不等于**当日最终成交净值，仅供参考。

---

## 1. 安装与启动

### 前置依赖

- Python 3.12+（后端，用 [uv](https://docs.astral.sh/uv/) 管理）
- Bun（前端；没有 Bun 时 npm 也可）

详细安装步骤（含 Windows）见 [docs/install.md](install.md)。

### 一键启动（推荐）

```bash
cd fund-watch
./start.sh          # Windows 用 .\start.ps1
```

脚本自动装依赖、后台启动前后端并转发日志，Ctrl+C 一并停止。

### 分步启动

```bash
# 后端
cd backend && uv sync && uv run python run.py

# 前端（新终端）
cd frontend && bun install && bun run dev
```

### Docker 启动

```bash
docker compose up -d
```

数据（SQLite + 上传截图）持久化在宿主机 `./data` 目录。容器以非 root（uid 1000）运行，首次部署请执行 `mkdir -p data && chown 1000:1000 data` 确保可写。需要 AI 选基时在同目录放 `.env` 写入 `ANTHROPIC_API_KEY`，并解开 `docker-compose.yml` 里的 `env_file` 注释。

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://127.0.0.1:5173 （Docker 方式为 http://127.0.0.1:8010） |
| API 文档（Swagger） | http://127.0.0.1:8010/docs |
| 健康检查 | http://127.0.0.1:8010/api/health |

### 环境变量

| 变量 | 作用 | 默认 |
|------|------|------|
| `FUND_WATCH_DB` | SQLite 数据库路径 | `backend/data/fund_watch.db` |
| `ANTHROPIC_API_KEY` | AI 选基 / OCR 文本抽取所需 | 无（不配则相关功能不可用） |
| `FUND_WATCH_TOKEN` | 可选访问令牌；设置后除 `/api/health` 外的 `/api/*` 请求需带请求头 `X-Fund-Token`，前端在「设置」里填写 | 无（不设置则无鉴权；绑定局域网/公网时务必设置） |

---

## 2. 页面功能指南

左侧导航共 6 个页面：

### 概览（`/`）

打开应用的首页。展示大盘指数（上证、深成等，来自新浪行情）、自选基金池的整体统计卡片和各基金当日估算涨跌。这里是盘中「看一眼」的入口。

### 自选基金（`/portfolio`）

核心页面，管理你的基金池和持仓：

- **添加基金**：搜索框按名称或 6 位代码搜索，点击加入基金池
- **多组合**：可创建多个组合（如「养老」「打新底仓」），持仓和盈亏按组合分别统计
- **持仓与交易**：为基金录入买入/卖出交易（支持按金额录入、卖出比例快捷键），系统计算持仓成本、市值和 P&L
- **拉取快照**：手动触发一次全池估值拉取并落库，用于走势和收益历史
- **收益统计**：组合汇总、持仓分布饼图、历史收益曲线

点击任意基金进入**基金详情**（`/funds/:code`）：估算净值实时刷新、NAV 走势图（1 月/3 月/半年/1 年/全部）、阶段涨幅、基金经理与规模、资产配置饼图、前十大重仓股。

### 行情数据（`/market`）

大盘指数行情页，展示主要指数的实时点位与涨跌幅。数据源不稳定时会降级显示空数据而非报错。

### AI 选基（`/ai-select`）

输入你的选基需求（如「低回撤的红利指数基金」），AI 流式返回推荐基金及理由，可一键加入基金池。**需要后端配置 `ANTHROPIC_API_KEY`。**

### 截图导入（`/import`）

把支付宝/天天基金等 App 的持仓截图批量导入：

1. 上传截图 → OCR（PaddleOCR，本地运行）识别基金代码；识别不到代码时按基金名称模糊搜索
2. 系统搜索补全基金名称，列出候选
3. 勾选确认 → 批量加入基金池

也支持交易记录截图识别（自动填充交易表单）。OCR 可用性可通过 `GET /api/ocr/status` 查看。

### 持仓反查（`/stock-funds`）

输入 6 位股票代码，反查哪些基金重仓了这只股票——用于「我想押某只股票，哪些基金帮我持有它」的场景。

---

## 3. API 使用

完整接口清单以 Swagger（http://127.0.0.1:8010/docs）为准。常用接口速查：

| 用途 | 接口 |
|------|------|
| 基金池列表 / 概览 | `GET /api/funds`、`GET /api/funds/overview` |
| 添加 / 批量添加 / 删除 | `POST /api/funds/{code}`、`POST /api/funds/batch`、`DELETE /api/funds/{code}` |
| 搜索基金 | `GET /api/funds/search?q=关键词` |
| 实时估值 | `GET /api/quote/{code}` |
| 基金详情 / NAV 历史 / 重仓股 | `GET /api/funds/{code}/detail`、`/nav-history`、`/holdings` |
| 拉取快照落库 | `POST /api/snapshots/pull` |
| 快照序列 | `GET /api/snapshots/{code}?limit=30` |
| 组合管理 | `GET/POST/PATCH/DELETE /api/portfolios` |
| 组合汇总 / 持仓 / 历史 | `GET /api/portfolio/summary`、`/holdings`、`/history` |
| 交易记录 / 盈亏 | `GET/POST /api/funds/{code}/transactions`、`GET /api/funds/{code}/pnl` |
| 交易 CSV 导入 | `POST /api/transactions/csv` |
| 股票反查基金 | `GET /api/stocks/{code}/funds` |
| 大盘指数 | `GET /api/market/indices` |

批量导入示例：

```bash
curl -X POST http://127.0.0.1:8010/api/funds/batch \
  -H "Content-Type: application/json" \
  -d '{"codes": ["110011", "161725"]}'
```

约定：基金/股票代码一律为 6 位数字字符串；行情类接口在数据源失败时返回空数据 + `error` 字段而非 502。

---

## 4. 数据源与数据存储

| 用途 | 来源 | 备注 |
|------|------|------|
| 实时估值 | `fundgz.1234567.com.cn` | 免费 JSONP，非交易时段无估值 |
| 基金详情 / NAV 历史 | `fund.eastmoney.com/pingzhongdata` | 免费 |
| 基金搜索 | `fundsuggest.eastmoney.com` | 免费 |
| 大盘指数 | `hq.sinajs.cn` | 新浪行情，3 次重试退避 |

免费源不保证稳定，接口层已内置重试与降级。所有本地数据存于单个 SQLite 文件（默认 `backend/data/fund_watch.db`），**备份/迁移只需拷贝这个文件**（Docker 方式为宿主机 `./data` 目录）。

---

## 5. 定时拉取快照

盘中自动拉估值，供走势与收益历史使用：

```bash
cd backend && uv run python pull_quotes.py   # 手动触发一次
```

挂 cron（工作日盘中每分钟）：

```cron
* 9-15 * * 1-5 cd /path/to/fund-watch/backend && uv run python pull_quotes.py
```

Windows 用任务计划程序，配置见 [docs/install.md](install.md)。拉取状态可通过 `GET /api/cron/status` 查看。

---

## 6. 常见问题

**估值和 App 里显示的净值不一样？**
盘中估值是根据持仓股票实时价格推算的，收盘后基金公司公布的最终净值才是准确值。

**非交易时段页面没有涨跌数据？**
正常。估值源只在交易时段返回数据。

**AI 选基提示不可用？**
后端未配置 `ANTHROPIC_API_KEY`。在启动环境（或 Docker `.env`）中设置后重启后端。

**截图识别不到基金代码？**
截图里往往只有基金名称。系统会按名称模糊搜索给出候选，勾选确认即可；也可以直接在自选页面手动搜索添加。

**端口冲突？**
后端改启动命令的 `--port`，前端改 `frontend/vite.config.ts` 中的端口。

**想清空所有数据重来？**
停止服务后删除 `backend/data/fund_watch.db`，重启即重建空库。

---

## 7. 更多文档

| 文档 | 内容 |
|------|------|
| [docs/install.md](install.md) | 详细安装步骤（含 Windows） |
| [docs/ROADMAP.md](ROADMAP.md) | 路线图与不做清单 |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 代码架构 |
| Swagger `/docs` | 活的 API 文档 |
