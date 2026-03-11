# 安装手顺

## 前置依赖

| 工具 | 版本 | 安装方式 |
|------|------|----------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| uv | 最新 | 见下方 |
| Bun | 最新 | 见下方 |

**安装 uv：**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**安装 Bun：**

```bash
# macOS / Linux
curl -fsSL https://bun.sh/install | bash

# Windows（PowerShell）
powershell -c "irm bun.sh/install.ps1 | iex"
```

---

## 方式一：一键启动

**macOS / Linux**

```bash
cd fund-watch
bash start.sh
```

**Windows（PowerShell）**

```powershell
cd fund-watch
# 首次运行需要先解除脚本执行限制（仅对当前会话生效）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```

两个脚本均会自动创建虚拟环境、安装依赖、在后台启动前后端，并实时转发日志。Ctrl+C 可同时停止所有服务。

---

## 方式二：分步启动（跨平台）

### 后端

```bash
cd fund-watch/backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8010
```

### 前端（新开一个终端）

```bash
cd fund-watch/frontend
bun install
bun run dev
```

> 如果没有安装 Bun，可以用 `npm install && npm run dev` 代替。

---

## 验证服务正常

| 服务 | 地址 |
|------|------|
| 前端页面 | http://127.0.0.1:5173 |
| API 文档 | http://127.0.0.1:8010/docs |
| 健康检查 | http://127.0.0.1:8010/api/health |

---

## 定时拉取（可选）

`pull_quotes.py` 通过 API 触发一次快照拉取，可配合系统定时任务在盘中自动运行。

### macOS / Linux — cron

```bash
crontab -e
```

添加以下行（工作日 9–15 点，每分钟执行一次）：

```cron
* 9-15 * * 1-5 cd /path/to/fund-watch/backend && uv run python pull_quotes.py
```

### Windows — 任务计划程序

1. 打开「任务计划程序」→「创建基本任务」
2. 触发器：每天，重复间隔 1 分钟，持续时间 6 小时（09:00–15:00）
3. 操作：启动程序

```
程序：C:\Users\你的用户名\.local\bin\uv.exe
参数：run python pull_quotes.py
起始位置：C:\path\to\fund-watch\backend
```

也可以用 PowerShell 脚本代替：

```powershell
# pull_quotes.ps1
Set-Location "C:\path\to\fund-watch\backend"
& uv run python pull_quotes.py
```

---

## Windows 注意事项

| 事项 | 说明 |
|------|------|
| `start.sh` | 不适用于 Windows，请用方式二分步启动 |
| 路径分隔符 | 代码内部全用 `pathlib.Path`，无需手动处理 |
| cron | 用 Windows 任务计划程序替代 |
| 端口占用 | 如 8010 / 5173 被占用，修改启动命令中的 `--port` 参数及 `vite.config.ts` 中的端口 |
