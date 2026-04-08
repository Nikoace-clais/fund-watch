"""Development server entry point."""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "fund_watch.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
    )
