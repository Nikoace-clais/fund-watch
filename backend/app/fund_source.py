from __future__ import annotations

import json
import re
from typing import Any

import httpx

FUND_GZ_URL = "https://fundgz.1234567.com.cn/js/{code}.js"
JSONP_RE = re.compile(r"jsonpgz\((.*)\)")


async def fetch_realtime_estimate(code: str) -> dict[str, Any]:
    url = FUND_GZ_URL.format(code=code)
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text.strip()

    m = JSONP_RE.search(text)
    if not m:
        raise ValueError(f"Invalid response for code {code}")

    payload = json.loads(m.group(1))
    return {
        "fundcode": payload.get("fundcode"),
        "name": payload.get("name"),
        "jzrq": payload.get("jzrq"),
        "dwjz": _to_float(payload.get("dwjz")),
        "gsz": _to_float(payload.get("gsz")),
        "gszzl": _to_float(payload.get("gszzl")),
        "gztime": payload.get("gztime"),
    }


def _to_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


PINGZHONG_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"

# Common fund sector keywords to extract from fund name
_SECTOR_KEYWORDS = [
    "白酒", "医药", "医疗", "新能源", "光伏", "半导体", "芯片", "科技",
    "消费", "食品饮料", "军工", "国防", "银行", "证券", "金融", "地产",
    "房地产", "互联网", "传媒", "农业", "煤炭", "钢铁", "有色",
    "化工", "汽车", "电力", "环保", "养老", "红利", "沪深300",
    "中证500", "中证1000", "创业板", "科创", "恒生", "港股", "纳斯达克",
    "标普", "QDII", "债", "货币",
]


def _extract_sector(name: str) -> str | None:
    """Extract sector keyword from fund name."""
    for kw in _SECTOR_KEYWORDS:
        if kw in name:
            return kw
    return None


async def fetch_fund_info(code: str) -> dict[str, Any]:
    """Fetch fund basic info (name, sector) from eastmoney pingzhongdata."""
    url = PINGZHONG_URL.format(code=code)
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    # Parse: var fS_name = "招商中证白酒指数(LOF)A";
    name_m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else None

    sector = _extract_sector(name) if name else None

    return {"name": name, "sector": sector}


HOLDINGS_URL = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={code}&topline=10"

# Parse: <td>序号</td><td>股票代码</td><td>股票名称</td>...<td>占净值比例</td>...<td>持仓市值(万元)</td>
_HOLDING_ROW_RE = re.compile(
    r"<tr><td>\d+</td>"                         # 序号
    r"<td>.*?>([\d]{6})</a></td>"                # 股票代码
    r"<td class='tol'>.*?>([^<]+)</a></td>"      # 股票名称
    r".*?"
    r"<td class='tor'>([\d.]+)%</td>"            # 占净值比例
    r"<td class='tor'>([\d,.]+)</td>"             # 持股数(万股)
    r"<td class='tor'>([\d,.]+)</td></tr>",       # 持仓市值(万元)
    re.DOTALL,
)


async def fetch_fund_holdings(code: str) -> list[dict[str, Any]]:
    """Fetch top-10 stock holdings for a fund from eastmoney."""
    url = HOLDINGS_URL.format(code=code)
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    holdings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _HOLDING_ROW_RE.finditer(text):
        stock_code, stock_name, pct_str, shares_str, value_str = m.groups()
        # Only take the first occurrence of each stock (latest quarter)
        if stock_code in seen:
            break  # Hit second quarter data, stop
        seen.add(stock_code)
        holdings.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "percentage": _to_float(pct_str),
            "shares_wan": _to_float(shares_str.replace(",", "")),
            "value_wan": _to_float(value_str.replace(",", "")),
        })
    return holdings
