"""Development server entry point."""
import logging
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import uvicorn

# Configure logging before uvicorn starts
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

if __name__ == "__main__":
    print("\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print("\033[32m  Fund Watch API 开发服务器\033[0m")
    print("\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print()
    print("\033[36m📡 API 地址: http://127.0.0.1:8010\033[0m")
    print("\033[36m📚 文档地址: http://127.0.0.1:8010/docs\033[0m")
    print()
    print("\033[33m按 Ctrl+C 停止服务\033[0m")
    print()

    uvicorn.run(
        "fund_watch.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
        log_level="info",
        access_log=True,
    )
