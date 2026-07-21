"""可选令牌鉴权。

设置环境变量 FUND_WATCH_TOKEN 后，所有 /api/ 请求必须携带请求头
``X-Fund-Token: <token>``；未设置时与无鉴权行为完全一致（本地自用默认）。
唯一例外是 /api/health —— Docker 健康检查依赖它无鉴权可达。
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

_TOKEN_ENV = "FUND_WATCH_TOKEN"
_HEADER_NAME = "x-fund-token"
_PUBLIC_PATHS = frozenset({"/api/health"})


async def token_auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # 每次请求读取环境变量：改 token 不必重建 app（测试也依赖这一点）
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        return await call_next(request)
    path = request.url.path
    # OPTIONS 预检不会携带自定义头，必须放行给 CORSMiddleware 处理，
    # 否则浏览器跨域请求（Vite dev server）会被预检 401 卡死
    if (
        request.method == "OPTIONS"
        or not path.startswith("/api/")
        or path in _PUBLIC_PATHS
    ):
        return await call_next(request)
    provided = request.headers.get(_HEADER_NAME, "")
    if not hmac.compare_digest(provided, token):
        return JSONResponse(
            status_code=401,
            content={"detail": "未授权：缺少或无效的访问令牌"},
        )
    return await call_next(request)
