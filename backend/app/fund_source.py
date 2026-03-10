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
FUND_DETAIL_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"

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


async def fetch_fund_detail(code: str) -> dict[str, Any]:
    """Fetch comprehensive fund detail from eastmoney pingzhongdata.

    Returns: name, manager, size, established_date, period returns,
    asset allocation, etc.
    """
    url = PINGZHONG_URL.format(code=code)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    result: dict[str, Any] = {"code": code}

    # Fund name
    m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    result["name"] = m.group(1) if m else None

    # Fund code (verify)
    m = re.search(r'var fS_code\s*=\s*"([^"]*)"', text)
    result["fund_code"] = m.group(1) if m else code

    # Fund type
    m = re.search(r'var fS_type\s*=\s*"([^"]*)"', text)
    result["fund_type"] = m.group(1) if m else None

    # Manager — extract name from the first manager entry
    m = re.search(r'"name":"([^"]*)"', text[text.find("Data_currentFundManager"):] if "Data_currentFundManager" in text else "")
    result["manager"] = m.group(1) if m else None

    # Fund size (亿) from fluctuation scale: series is [{y:374.98, mom:"..."}, ...]
    m = re.search(r'var Data_fluctuationScale\s*=\s*(\{.*?\});\s*var', text, re.DOTALL)
    if not m:
        m = re.search(r'var Data_fluctuationScale\s*=\s*(\{.*?\});', text, re.DOTALL)
    if m:
        try:
            scale_data = json.loads(m.group(1))
            series = scale_data.get("series", [])
            if series:
                result["size"] = series[-1].get("y")
            else:
                result["size"] = None
        except (json.JSONDecodeError, KeyError):
            result["size"] = None
    else:
        result["size"] = None

    # Established date — not always a separate var, extract from fund page if needed
    # Try fS_nkfr first, then look for 成立日期 pattern
    m = re.search(r'var fS_nkfr\s*=\s*"([^"]*)"', text)
    result["established_date"] = m.group(1) if m else None

    # Period returns: syl_1y=近1月, syl_3y=近3月, syl_6y=近6月, syl_1n=近1年
    for var_name, key in [
        ("syl_1y", "one_month_return"),
        ("syl_3y", "three_month_return"),
        ("syl_6y", "six_month_return"),
        ("syl_1n", "one_year_return"),
    ]:
        m = re.search(rf'var {var_name}\s*=\s*"([^"]*)"', text)
        if not m:
            m = re.search(rf'var {var_name}\s*=\s*([^;]*);', text)
        result[key] = _to_float(m.group(1).strip('"')) if m else None

    # Asset allocation: Data_assetAllocation
    m = re.search(r'var Data_assetAllocation\s*=\s*(\{.*?\});', text, re.DOTALL)
    if m:
        try:
            alloc_data = json.loads(m.group(1))
            categories = alloc_data.get("categories", [])
            series = alloc_data.get("series", [])
            # Build allocation: each series item is {name, data: [...]}
            # data aligns with categories (dates), take latest value
            allocation = []
            for s in series:
                name = s.get("name", "")
                if "净资产" in name:
                    continue  # Skip net asset value, not an allocation category
                data = s.get("data", [])
                if data:
                    allocation.append({"name": name, "value": data[-1]})
            result["asset_allocation"] = allocation
        except (json.JSONDecodeError, KeyError):
            result["asset_allocation"] = []
    else:
        result["asset_allocation"] = []

    result["sector"] = _extract_sector(result["name"]) if result["name"] else None

    # Subscription fee rates
    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]*)"', text)
    result["subscription_rate"] = _to_float(m.group(1)) if m else None

    m = re.search(r'var fund_Rate\s*=\s*"([^"]*)"', text)
    result["subscription_rate_discounted"] = _to_float(m.group(1)) if m else None

    return result


def _extract_js_array(text: str, var_name: str) -> list | None:
    """Extract a JS array variable from text using bracket matching."""
    idx = text.find(f"var {var_name}")
    if idx < 0:
        return None
    sub = text[idx:]
    eq_idx = sub.find("=")
    if eq_idx < 0:
        return None
    rest = sub[eq_idx + 1:].strip()
    if not rest.startswith("["):
        return None
    depth = 0
    end = 0
    for i, c in enumerate(rest):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        if depth == 0:
            end = i + 1
            break
    if end == 0:
        return None
    try:
        return json.loads(rest[:end])
    except json.JSONDecodeError:
        return None


async def fetch_nav_history(code: str, limit: int = 365) -> list[dict[str, Any]]:
    """Fetch historical NAV data from eastmoney pingzhongdata.

    Returns list of {date, nav, accNav, dailyReturn}.
    """
    url = PINGZHONG_URL.format(code=code)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    from datetime import datetime as dt

    history: list[dict[str, Any]] = []

    raw = _extract_js_array(text, "Data_netWorthTrend")
    if raw:
        for item in raw[-limit:]:
            ts = item.get("x", 0)
            date_str = dt.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else None
            history.append({
                "date": date_str,
                "nav": item.get("y"),
                "dailyReturn": item.get("equityReturn"),
            })

    # Data_ACWorthTrend = [[timestamp, accNav], ...]
    acc_map: dict[str, float] = {}
    raw_acc = _extract_js_array(text, "Data_ACWorthTrend")
    if raw_acc:
        for item in raw_acc[-limit:]:
            try:
                ts, acc = item[0], item[1]
                date_str = dt.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else None
                if date_str:
                    acc_map[date_str] = acc
            except (IndexError, TypeError):
                continue

    for h in history:
        h["accNav"] = acc_map.get(h["date"])

    return history


LSJZ_URL = "https://api.fund.eastmoney.com/f10/lsjz"
FUND_SEARCH_URL = "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx"


async def fetch_latest_nav(code: str) -> dict[str, Any] | None:
    """Fetch the most recent NAV record. Returns {date, nav} or None."""
    params = {"fundCode": code, "pageIndex": 1, "pageSize": 1}
    headers = {"Referer": "https://fund.eastmoney.com/"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(LSJZ_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    items = (data.get("Data") or {}).get("LSJZList") or []
    if items:
        return {"date": items[0].get("FSRQ"), "nav": _to_float(items[0].get("DWJZ"))}
    return None


async def fetch_nav_on_date(code: str, date: str) -> float | None:
    """Fetch the NAV for a specific date (YYYY-MM-DD). Returns None if not found."""
    params = {
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": 1,
        "startDate": date,
        "endDate": date,
    }
    headers = {"Referer": "https://fund.eastmoney.com/"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(LSJZ_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    items = (data.get("Data") or {}).get("LSJZList") or []
    if items:
        return _to_float(items[0].get("DWJZ"))
    return None


async def search_fund_by_name(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search funds by name/keyword via eastmoney suggest API.

    Returns list of {"code": "110011", "name": "易方达优质精选混合(QDII)", "type": "QDII-混合偏股"}.
    """
    params = {"callback": "cb", "m": "1", "key": keyword}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(FUND_SEARCH_URL, params=params)
        resp.raise_for_status()
        text = resp.text.strip()

    # Strip JSONP wrapper: cb({...})
    if text.startswith("cb(") and text.endswith(")"):
        text = text[3:-1]
    data = json.loads(text)

    results: list[dict[str, Any]] = []
    for item in (data.get("Datas") or [])[:limit]:
        code = item.get("CODE", "")
        if not re.match(r"^\d{6}$", code):
            continue
        entry: dict[str, Any] = {"code": code, "name": item.get("NAME", "")}
        base = item.get("FundBaseInfo") or {}
        if base.get("FTYPE"):
            entry["type"] = base["FTYPE"]
        results.append(entry)
    return results
