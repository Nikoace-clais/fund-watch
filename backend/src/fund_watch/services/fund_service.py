"""Fund business logic service."""
from __future__ import annotations

from typing import Any

from ..external import fetch_fund_info
from ..repositories.fund_repo import FundRepository


class FundService:
    """Fund business logic."""
    
    def __init__(self, repo: FundRepository | None = None):
        self.repo = repo or FundRepository()
    
    async def create_fund(self, code: str) -> dict[str, Any]:
        """Create fund with info from external source."""
        # Fetch fund info from eastmoney
        info = await fetch_fund_info(code)
        # Create in database
        fund = self.repo.create(code, name=info.get("name"))
        # Add sector info
        if info.get("sector"):
            fund["sector"] = info["sector"]
        return fund
    
    def get_funds(self) -> list[dict[str, Any]]:
        """Get all funds."""
        return self.repo.get_all()
    
    def get_fund(self, code: str) -> dict[str, Any] | None:
        """Get fund by code."""
        return self.repo.get_by_code(code)
    
    def delete_fund(self, code: str) -> bool:
        """Delete fund."""
        return self.repo.delete(code)
    
    def batch_create(self, codes: list[str]) -> dict[str, Any]:
        """Batch create funds."""
        return self.repo.batch_create(codes)
