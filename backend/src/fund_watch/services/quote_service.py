"""Quote calculation service."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..external import fetch_realtime_estimate


class QuoteService:
    """Fund quote calculation service."""
    
    async def get_estimate(self, code: str) -> dict[str, Any]:
        """Get real-time estimate for a fund."""
        return await fetch_realtime_estimate(code)
    
    async def calculate_portfolio_value(
        self,
        holdings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calculate portfolio value based on holdings and current quotes."""
        total_value = Decimal("0")
        total_cost = Decimal("0")
        items = []
        
        for holding in holdings:
            code = holding["code"]
            shares = Decimal(holding.get("shares", "0"))
            cost_price = Decimal(holding.get("cost_price", "0"))
            
            # Get current quote
            quote = await self.get_estimate(code)
            current_nav = Decimal(str(quote.get("gsz", 0) or quote.get("dwjz", 0)))
            
            current_value = shares * current_nav
            cost_value = shares * cost_price
            
            total_value += current_value
            total_cost += cost_value
            
            items.append({
                "code": code,
                "name": quote.get("name"),
                "shares": str(shares),
                "current_nav": str(current_nav),
                "current_value": str(current_value),
                "cost_value": str(cost_value),
                "return": str(current_value - cost_value),
            })
        
        total_return = total_value - total_cost
        return_rate = (
            (total_return / total_cost * 100) if total_cost > 0 else Decimal("0")
        )
        
        return {
            "total_value": str(total_value),
            "total_cost": str(total_cost),
            "total_return": str(total_return),
            "return_rate": str(return_rate),
            "items": items,
        }
