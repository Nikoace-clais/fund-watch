# 实现方案 (Implementation)

1. 创建 `start.sh`，放置在项目根目录。
2. 脚本中定义 `cleanup` 函数并捕获退出信号，从而可以做到一个终端同时管理前后端的生命周期，按 `Ctrl+C` 可以同时退出两个服务。
3. 遵循用户规则，使用 `bun` 作为前端的包管理器和运行工具 (`bun run dev`)。
4. 使用 `uv` 管理后端的启动和环境 (`uv run uvicorn`)。
5. 自动检查环境，如果 `.venv` 或 `node_modules` 不存在则执行相应的 `uv venv`/`bun install` 命令。
