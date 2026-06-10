"""Eastmoney data source adapter."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Simple in-process TTL cache for NAV history ──
_nav_history_cache: dict[str, tuple[float, list]] = {}
_NAV_CACHE_TTL = 600  # 10 minutes

# ── Shared async HTTP client ──
_client: httpx.AsyncClient | None = None

# URLs
FUND_GZ_URL = "https://fundgz.1234567.com.cn/js/{code}.js"
PINGZHONG_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
HOLDINGS_URL = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={code}&topline=10"
LSJZ_URL = "https://api.fund.eastmoney.com/f10/lsjz"
FUND_SEARCH_URL = "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx"
MARKET_INDICES_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

# Sina Finance API (backup for market indices)
SINA_HQ_URL = "https://hq.sinajs.cn/list={codes}"

# Regex patterns
JSONP_RE = re.compile(r"jsonpgz\((.*)\)")
_HOLDING_ROW_RE = re.compile(
    r"<tr><td>\d+</td>"
    r"<td>.*?>([\d]{6})</a></td>"
    r"<td class='tol'>.*?>([^<]+)</a></td>"
    r".*?"
    r"<td class='tor'>([\d.]+)%</td>"
    r"<td class='tor'>([\d,.]+)</td>"
    r"<td class='tor'>([\d,.]+)</td></tr>",
    re.DOTALL,
)

# Market indices (Eastmoney format)
_INDEX_SECIDS = [
    "1.000001",   # 上证指数
    "0.399001",   # 深证成指
    "0.399006",   # 创业板指
    "0.399300",   # 沪深300
    "1.000016",   # 上证50
    "1.000905",   # 中证500
    "100.HSI",    # 恒生指数
    "100.SPX",    # 标普500
    "100.NDX",    # 纳斯达克
    "100.DJIA",   # 道琼斯
    "100.N225",   # 日经225
]

# Sina Finance API index codes
_SINA_INDICES = {
    "sh000001": {"name": "上证指数", "code": "000001"},
    "sz399001": {"name": "深证成指", "code": "399001"},
    "sz399006": {"name": "创业板指", "code": "399006"},
    "sh000300": {"name": "沪深300", "code": "000300"},
    "sh000016": {"name": "上证50", "code": "000016"},
    "sh000905": {"name": "中证500", "code": "000905"},
    "hkHSI": {"name": "恒生指数", "code": "HSI"},
}

# Sector keywords
_SECTOR_KEYWORDS = [
    "白酒", "医药", "医疗", "新能源", "光伏", "半导体", "芯片", "科技",
    "消费", "食品饮料", "军工", "国防", "银行", "证券", "金融", "地产",
    "房地产", "互联网", "传媒", "农业", "煤炭", "钢铁", "有色",
    "化工", "汽车", "电力", "环保", "养老", "红利", "沪深300",
    "中证500", "中证1000", "创业板", "科创", "恒生", "港股", "纳斯达克",
    "标普", "QDII", "债", "货币",
]


def _get_client() -> httpx.AsyncClient:
    """Get shared HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
            http2=False,  # Disable HTTP/2 to avoid connection issues
        )
        logger.debug("🌐 HTTP client initialized")
    return _client


async def close_shared_client() -> None:
    """Close shared HTTP client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("httpx shared client closed")


def _to_float(v: Any) -> float | None:
    """Convert value to float."""
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _extract_sector(name: str) -> str | None:
    """Extract sector keyword from fund name."""
    for kw in _SECTOR_KEYWORDS:
        if kw in name:
            return kw
    return None


def _extract_js_array(text: str, var_name: str) -> list | None:
    """Extract a JS array variable from text."""
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


async def fetch_realtime_estimate(code: str) -> dict[str, Any]:
    """Fetch real-time fund estimate from fundgz."""
    url = FUND_GZ_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text.strip()
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_realtime_estimate [%s] %.3fs", code, elapsed)

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


async def fetch_fund_info(code: str) -> dict[str, Any]:
    """Fetch fund basic info from eastmoney."""
    url = PINGZHONG_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_info [%s] %.3fs", code, elapsed)

    name_m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else None
    sector = _extract_sector(name) if name else None

    return {"name": name, "sector": sector}


async def fetch_fund_holdings(code: str) -> list[dict[str, Any]]:
    """Fetch top-10 stock holdings for a fund."""
    url = HOLDINGS_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_holdings [%s] %.3fs", code, elapsed)

    holdings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _HOLDING_ROW_RE.finditer(text):
        stock_code, stock_name, pct_str, shares_str, value_str = m.groups()
        if stock_code in seen:
            break
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
    """Fetch comprehensive fund detail."""
    url = PINGZHONG_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_detail [%s] %.3fs", code, elapsed)

    result: dict[str, Any] = {"code": code}

    m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    result["name"] = m.group(1) if m else None

    m = re.search(r'var fS_code\s*=\s*"([^"]*)"', text)
    result["fund_code"] = m.group(1) if m else code

    m = re.search(r'var fS_type\s*=\s*"([^"]*)"', text)
    result["fund_type"] = m.group(1) if m else None

    m = re.search(r'"name":"([^"]*)"', text[text.find("Data_currentFundManager"):] if "Data_currentFundManager" in text else "")
    result["manager"] = m.group(1) if m else None

    m = re.search(r'var Data_fluctuationScale\s*=\s*(\{.*?\});\s*var', text, re.DOTALL)
    if not m:
        m = re.search(r'var Data_fluctuationScale\s*=\s*(\{.*?\});', text, re.DOTALL)
    if m:
        try:
            scale_data = json.loads(m.group(1))
            series = scale_data.get("series", [])
            result["size"] = series[-1].get("y") if series else None
        except (json.JSONDecodeError, KeyError):
            result["size"] = None
    else:
        result["size"] = None

    m = re.search(r'var fS_nkfr\s*=\s*"([^"]*)"', text)
    result["established_date"] = m.group(1) if m else None

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

    m = re.search(r'var Data_assetAllocation\s*=\s*(\{.*?\});', text, re.DOTALL)
    if m:
        try:
            alloc_data = json.loads(m.group(1))
            categories = alloc_data.get("categories", [])
            series = alloc_data.get("series", [])
            allocation = []
            for s in series:
                name = s.get("name", "")
                if "净资产" in name:
                    continue
                data = s.get("data", [])
                if data:
                    allocation.append({"name": name, "value": data[-1]})
            result["asset_allocation"] = allocation
        except (json.JSONDecodeError, KeyError):
            result["asset_allocation"] = []
    else:
        result["asset_allocation"] = []

    result["sector"] = _extract_sector(result["name"]) if result["name"] else None

    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]*)"', text)
    result["subscription_rate"] = _to_float(m.group(1)) if m else None

    m = re.search(r'var fund_Rate\s*=\s*"([^"]*)"', text)
    result["subscription_rate_discounted"] = _to_float(m.group(1)) if m else None

    return result


async def fetch_nav_history(code: str, limit: int = 365) -> list[dict[str, Any]]:
    """Fetch historical NAV data."""
    cached = _nav_history_cache.get(code)
    if cached:
        fetched_at, full_data = cached
        if time.time() - fetched_at < _NAV_CACHE_TTL:
            return full_data[-limit:] if limit < len(full_data) else full_data

    url = PINGZHONG_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_nav_history [%s] %.3fs", code, elapsed)

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

    _nav_history_cache[code] = (time.time(), history)
    return history[-limit:] if limit < len(history) else history


def _parse_sina_hq_response(text: str) -> list[dict[str, Any]]:
    """Parse Sina Finance API response for market indices.

    A-share format (sh/sz prefix):
    var hq_str_sh000001="上证指数,previous_close,open,current,high,low,...";

    HK stock format (hk prefix):
    var hq_str_hkHSI="HSI,name,previous_close,open,high,low,current,change,change_percent,...";
    """
    import re

    results = []
    # Pattern to match var hq_str_CODE="DATA";
    pattern = r'var hq_str_(\w+)="([^"]*)";'
    matches = re.findall(pattern, text)

    for code, data in matches:
        if not data or code not in _SINA_INDICES:
            continue

        parts = data.split(",")
        if len(parts) < 5:
            continue

        index_info = _SINA_INDICES[code]

        # Parse based on market type
        if code.startswith("hk"):
            # HK format: HSI,name,previous_close,open,high,low,current,change,change_percent,...
            # parts[0] = "HSI", parts[1] = name, parts[2] = previous_close, parts[6] = current
            # parts[7] = change, parts[8] = change_percent
            if len(parts) < 9:
                continue
            previous_close = float(parts[2]) if parts[2] else 0
            current = float(parts[6]) if parts[6] else 0
            change = float(parts[7]) if parts[7] else 0
            change_percent = float(parts[8]) if parts[8] else 0
        else:
            # A-share format: name,previous_close,open,current,high,low,...
            # parts[0] = name, parts[1] = previous_close, parts[3] = current
            previous_close = float(parts[1]) if parts[1] else 0
            current = float(parts[3]) if parts[3] else 0
            change = current - previous_close if previous_close else 0
            change_percent = (change / previous_close * 100) if previous_close else 0

        results.append({
            "code": index_info["code"],
            "name": index_info["name"],
            "value": round(current, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
        })

    return results


async def fetch_market_indices() -> list[dict[str, Any]]:
    """Fetch major market indices from Sina Finance API."""
    codes = ",".join(_SINA_INDICES.keys())
    url = SINA_HQ_URL.format(codes=codes)
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    t0 = time.perf_counter()
    client = _get_client()

    max_retries = 3
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            # Response is GBK encoded
            text = resp.content.decode("gbk", errors="ignore")
            items = _parse_sina_hq_response(text)
            elapsed = time.perf_counter() - t0
            logger.debug("fetch_market_indices %.3fs (attempt %d)", elapsed, attempt + 1)
            return items

        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
            logger.warning("fetch_market_indices attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue
        except Exception as e:
            logger.error("fetch_market_indices unexpected error: %s", e)
            raise

    logger.error("fetch_market_indices all %d attempts failed", max_retries)
    raise last_error or Exception("Failed to fetch market indices")


async def fetch_latest_nav(code: str) -> dict[str, Any] | None:
    """Fetch the most recent NAV record."""
    params = {"fundCode": code, "pageIndex": 1, "pageSize": 1}
    headers = {"Referer": "https://fund.eastmoney.com/"}
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(LSJZ_URL, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_latest_nav [%s] %.3fs", code, elapsed)
    items = (data.get("Data") or {}).get("LSJZList") or []
    if items:
        return {"date": items[0].get("FSRQ"), "nav": _to_float(items[0].get("DWJZ"))}
    return None


async def fetch_nav_on_date(code: str, date: str) -> float | None:
    """Fetch NAV for a specific date."""
    params = {
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": 1,
        "startDate": date,
        "endDate": date,
    }
    headers = {"Referer": "https://fund.eastmoney.com/"}
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(LSJZ_URL, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_nav_on_date [%s@%s] %.3fs", code, date, elapsed)
    items = (data.get("Data") or {}).get("LSJZList") or []
    if items:
        return _to_float(items[0].get("DWJZ"))
    return None


async def search_fund_by_name(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search funds by name/keyword."""
    params = {"callback": "cb", "m": "1", "key": keyword}
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(FUND_SEARCH_URL, params=params)
    resp.raise_for_status()
    text = resp.text.strip()
    elapsed = time.perf_counter() - t0
    logger.debug("search_fund_by_name [%s] %.3fs", keyword, elapsed)

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
