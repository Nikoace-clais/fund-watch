# Fund Watch — Windows 启动脚本
# 用法：右键 → 「用 PowerShell 运行」，或在 PowerShell 中执行：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\start.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── 清理函数 ─────────────────────────────────────────────────────────────────
function Stop-Services {
    Write-Host "`n[Info] 正在停止服务..." -ForegroundColor Yellow
    if ($script:BackendJob) { Stop-Job $script:BackendJob; Remove-Job $script:BackendJob -Force }
    if ($script:FrontendJob) { Stop-Job $script:FrontendJob; Remove-Job $script:FrontendJob -Force }
}

# 捕获 Ctrl+C
[Console]::TreatControlCAsInput = $false
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-Services }

# ── 后端 ─────────────────────────────────────────────────────────────────────
Write-Host "[Info] 准备启动后端..." -ForegroundColor Cyan
Set-Location "$ROOT\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "[Info] 正在创建虚拟环境并安装依赖..." -ForegroundColor Cyan
    uv venv
    uv pip install -r requirements.txt
}

Write-Host "[Info] 启动后端服务 (http://127.0.0.1:8010)..." -ForegroundColor Cyan
$script:BackendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    uv run uvicorn app.main:app --reload --port 8010
} -ArgumentList "$ROOT\backend"

# ── 前端 ─────────────────────────────────────────────────────────────────────
Write-Host "----------------------------------------"
Write-Host "[Info] 准备启动前端..." -ForegroundColor Cyan
Set-Location "$ROOT\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "[Info] 正在安装前端依赖..." -ForegroundColor Cyan
    if (Get-Command bun -ErrorAction SilentlyContinue) {
        bun install
    } else {
        npm install
    }
}

Write-Host "[Info] 启动前端服务 (http://127.0.0.1:5173)..." -ForegroundColor Cyan
$script:FrontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    if (Get-Command bun -ErrorAction SilentlyContinue) {
        bun run dev
    } else {
        npm run dev
    }
} -ArgumentList "$ROOT\frontend"

Set-Location $ROOT

# ── 提示 ─────────────────────────────────────────────────────────────────────
Write-Host "----------------------------------------"
Write-Host "[Success] API/Dashboard: http://127.0.0.1:8010/docs" -ForegroundColor Green
Write-Host "[Success] Frontend App:  http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "[Info] 按 Ctrl+C 停止所有服务"
Write-Host "----------------------------------------"

# ── 实时输出日志并等待 ────────────────────────────────────────────────────────
try {
    while ($true) {
        # 转发后端日志
        $backendOutput = Receive-Job $script:BackendJob 2>&1
        if ($backendOutput) { $backendOutput | ForEach-Object { Write-Host "[backend] $_" } }

        # 转发前端日志
        $frontendOutput = Receive-Job $script:FrontendJob 2>&1
        if ($frontendOutput) { $frontendOutput | ForEach-Object { Write-Host "[frontend] $_" } }

        # 检查任务是否意外退出
        if ($script:BackendJob.State -eq "Failed") {
            Write-Host "[Error] 后端进程已退出" -ForegroundColor Red
            break
        }
        if ($script:FrontendJob.State -eq "Failed") {
            Write-Host "[Error] 前端进程已退出" -ForegroundColor Red
            break
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    Stop-Services
}
