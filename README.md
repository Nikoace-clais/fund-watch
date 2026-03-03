# Fund Watch (A股公募 · 免费数据源)

面向“估算净值实时看盘 + 低打扰提醒”的基金监控工程骨架。

## 数据源
- 实时估值：`fundgz.1234567.com.cn`（免费）
- 历史/基础：`fund.eastmoney.com/pingzhongdata`（免费）
- OCR：RapidOCR（本地离线）

## 已实现能力（后端）
- 基金池持久化（SQLite）
- 实时估值拉取接口
- 批量估值快照持久化
- OCR 识别基金代码（6位）并持久化 OCR 记录

## 工程结构

```text
fund-watch/
├── PLAN.md
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── data/
│   │   ├── fund_watch.db          # 运行后生成
│   │   └── uploads/               # OCR上传图
│   ├── app/
│   │   ├── main.py                # FastAPI 入口
│   │   ├── db.py                  # SQLite 初始化/连接
│   │   ├── fund_source.py         # 免费估值源适配
│   │   └── ocr_service.py         # OCR + 代码提取
│   └── tests/
└── frontend/
    ├── src/
    └── README.md
```

## 快速启动

### 1) 启动后端

```bash
cd /home/niko/.openclaw/workspace/fund-watch/backend
/home/linuxbrew/.linuxbrew/bin/uv venv
/home/linuxbrew/.linuxbrew/bin/uv pip install -r requirements.txt
/home/linuxbrew/.linuxbrew/bin/uv run uvicorn app.main:app --reload --port 8010
```

后端访问：
- 健康检查：`GET http://127.0.0.1:8010/api/health`
- Swagger：`http://127.0.0.1:8010/docs`

### 2) 启动前端（最小页面）

```bash
cd /home/niko/.openclaw/workspace/fund-watch/frontend
npm install
npm run dev
```

前端页面默认：`http://127.0.0.1:5173`
（前端默认请求后端 `http://127.0.0.1:8010`）

## 关键接口

- `GET /api/funds`：基金池列表
- `POST /api/funds/{code}`：添加基金（6位代码）
- `POST /api/funds/batch`：批量添加基金代码
- `GET /api/funds/overview`：基金池 + 最新估算数据
- `GET /api/quote/{code}`：拉取实时估值
- `POST /api/snapshots/pull`：批量拉取基金池估值并落库
- `GET /api/snapshots/{code}?limit=30`：查询基金快照序列
- `POST /api/ocr/fund-code`：上传图片 OCR 识别基金代码并持久化

## OCR 持久化说明

每次 OCR 会：
1. 保存上传图片到 `backend/data/uploads/`
2. 识别文本并提取 6 位基金代码
3. 写入 `ocr_records` 表（image_name/raw_text/matched_codes/created_at）

## 定时拉取（脚本）

```bash
cd /home/niko/.openclaw/workspace/fund-watch/backend
/home/linuxbrew/.linuxbrew/bin/uv run python pull_quotes.py
```

可用于后续挂 cron（每 30~60 秒一轮）。

## 下一步建议
- 趋势图替换为真正折线图组件（ECharts/Recharts）
- 加提醒规则（冷却时间 + 降噪）
- 增加用户维度与分享权限（面向多人使用）
