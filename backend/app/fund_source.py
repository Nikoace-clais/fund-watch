from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

# ── Simple in-process TTL cache for NAV history (avoids re-fetching on range changes) ──
_nav_history_cache: dict[str, tuple[float, list]] = {}  # code -> (fetched_at, data)
_NAV_CACHE_TTL = 600  # 10 minutes

import httpx

logger = logging.getLogger(__name__)

# ── Shared async HTTP client (connection pooling + keep-alive) ──────────────
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
            http2=False,  # Disable HTTP/2 to avoid connection issues
        )
        logger.info("httpx shared client initialized")
    return _client


async def close_shared_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("httpx shared client closed")


FUND_GZ_URL = "https://fundgz.1234567.com.cn/js/{code}.js"
JSONP_RE = re.compile(r"jsonpgz\((.*)\)")


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = 3,
    **kw: Any,
) -> httpx.Response:
    """GET with exponential backoff on transient network errors."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, **kw)
            resp.raise_for_status()
            return resp
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    raise last_error or Exception(f"Failed GET {url}")


async def fetch_realtime_estimate(code: str) -> dict[str, Any]:
    url = FUND_GZ_URL.format(code=code)
    t0 = time.perf_counter()
    client = _get_client()
    resp = await _get_with_retry(client, url)
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
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_info [%s] %.3fs", code, elapsed)

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
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_detail [%s] %.3fs", code, elapsed)

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

    # Manager power scores from Data_currentFundManager
    raw_managers = _extract_js_array(text, "Data_currentFundManager")
    result["manager_power_scores"] = None
    result["manager_power_categories"] = None
    if raw_managers:
        try:
            power = raw_managers[0].get("power", {})
            result["manager_power_scores"] = power.get("data")
            result["manager_power_categories"] = power.get("categories")
        except (IndexError, AttributeError):
            pass

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
    Results are cached in-process for 10 minutes (TTL) to avoid repeated fetches
    when the user switches between chart range buttons.
    """
    # I4 fix: return cached data when still fresh
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

    # Store full history in cache; callers slice by limit from here
    _nav_history_cache[code] = (time.time(), history)
    return history[-limit:] if limit < len(history) else history


LSJZ_URL = "https://api.fund.eastmoney.com/f10/lsjz"
FUND_SEARCH_URL = "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx"

# ── Market indices (Sina Finance API; eastmoney push2 was unstable) ─────────
SINA_HQ_URL = "https://hq.sinajs.cn/list={codes}"

_SINA_INDICES = {
    "sh000001": {"name": "上证指数", "code": "000001", "region": "domestic"},
    "sz399001": {"name": "深证成指", "code": "399001", "region": "domestic"},
    "sz399006": {"name": "创业板指", "code": "399006", "region": "domestic"},
    "sh000300": {"name": "沪深300", "code": "000300", "region": "domestic"},
    "sh000016": {"name": "上证50", "code": "000016", "region": "domestic"},
    "sh000905": {"name": "中证500", "code": "000905", "region": "domestic"},
    "hkHSI": {"name": "恒生指数", "code": "HSI", "region": "international"},
    "gb_$dji": {"name": "道琼斯", "code": "DJI", "region": "international"},
    "gb_$inx": {"name": "标普500", "code": "SPX", "region": "international"},
    "gb_ixic": {"name": "纳斯达克", "code": "IXIC", "region": "international"},
    "b_NKY": {"name": "日经225", "code": "N225", "region": "international"},
}

# Note: [\w$]+ because US index vars contain "$" (e.g. hq_str_gb_$dji)
_SINA_HQ_RE = re.compile(r'var hq_str_([\w$]+)="([^"]*)";')


def _parse_sina_hq_response(text: str) -> list[dict[str, Any]]:
    """Parse Sina Finance API response for market indices.

    A-share format (sh/sz prefix):
    var hq_str_sh000001="上证指数,previous_close,open,current,high,low,...";

    HK stock format (hk prefix):
    var hq_str_hkHSI="HSI,name,previous_close,open,high,low,current,change,change_percent,...";

    US index format (gb_ prefix):
    var hq_str_gb_$dji="name,current,change_percent,datetime,change,...";

    Nikkei format (b_NKY):
    var hq_str_b_NKY="name,current,change,change_percent,...";
    """
    results = []
    for code, data in _SINA_HQ_RE.findall(text):
        if not data or code not in _SINA_INDICES:
            continue

        parts = data.split(",")
        if len(parts) < 5:
            continue

        index_info = _SINA_INDICES[code]

        try:
            if code.startswith("hk"):
                # HK format: parts[2] = previous_close, parts[6] = current,
                # parts[7] = change, parts[8] = change_percent
                if len(parts) < 9:
                    continue
                current = Decimal(parts[6] or "0")
                change = Decimal(parts[7] or "0")
                change_percent = Decimal(parts[8] or "0")
            elif code.startswith("gb_"):
                # US format: parts[1] = current, parts[2] = change_percent,
                # parts[4] = change
                current = Decimal(parts[1] or "0")
                change_percent = Decimal(parts[2] or "0")
                change = Decimal(parts[4] or "0")
            elif code.startswith("b_"):
                # Nikkei format: parts[1] = current, parts[2] = change,
                # parts[3] = change_percent
                current = Decimal(parts[1] or "0")
                change = Decimal(parts[2] or "0")
                change_percent = Decimal(parts[3] or "0")
            else:
                # A-share format: parts[1] = previous_close, parts[3] = current
                previous_close = Decimal(parts[1] or "0")
                current = Decimal(parts[3] or "0")
                change = current - previous_close if previous_close else Decimal("0")
                change_percent = (
                    (change / previous_close * 100) if previous_close else Decimal("0")
                )
        except (ValueError, InvalidOperation):
            logger.warning("skip unparsable index line: %s", code)
            continue

        _cent = Decimal("0.01")
        results.append({
            "code": index_info["code"],
            "name": index_info["name"],
            "region": index_info["region"],
            "value": float(current.quantize(_cent, rounding=ROUND_HALF_UP)),
            "change": float(change.quantize(_cent, rounding=ROUND_HALF_UP)),
            "change_percent": float(change_percent.quantize(_cent, rounding=ROUND_HALF_UP)),
        })

    return results


async def fetch_market_indices() -> list[dict[str, Any]]:
    """Fetch major market indices from Sina Finance API (3 retries with backoff)."""
    codes = ",".join(_SINA_INDICES.keys())
    url = SINA_HQ_URL.format(codes=codes)
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    t0 = time.perf_counter()
    client = _get_client()
    resp = await _get_with_retry(client, url, headers=headers)
    # Response is GBK encoded
    text = resp.content.decode("gbk", errors="ignore")
    items = _parse_sina_hq_response(text)
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_market_indices %.3fs", elapsed)
    return items


async def fetch_latest_nav(code: str) -> dict[str, Any] | None:
    """Fetch the most recent NAV record. Returns {date, nav} or None."""
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
    """Fetch the NAV for a specific date (YYYY-MM-DD). Returns None if not found."""
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


RANKING_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
_RANKING_HEADERS = {
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


async def fetch_fund_ranking(
    fund_type: str = "gp", page_size: int = 200
) -> list[dict[str, Any]]:
    """Fetch fund ranking from eastmoney.

    fund_type: 'gp' (股票型), 'hh' (混合型), 'zq' (债券型)
    Returns list of dicts with code, name, one_year_return, three_year_return, fee, size.
    Sorted by 3-year return descending by the remote API.
    """
    from datetime import date, timedelta

    today = date.today()
    sd = (today - timedelta(days=3 * 365)).isoformat()
    ed = today.isoformat()

    params = {
        "op": "ph", "dt": "kf", "ft": fund_type, "rs": "", "gs": "0",
        "sc": "3yzf", "st": "desc",
        "sd": sd, "ed": ed,
        "pi": "1", "pn": str(page_size), "dx": "1",
        "qdii": "", "tabSubtype": ",,,,,",
    }
    t0 = time.perf_counter()
    client = _get_client()
    resp = await _get_with_retry(client, RANKING_URL, params=params, headers=_RANKING_HEADERS)
    text = resp.text
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_fund_ranking [ft=%s, n=%s] %.3fs", fund_type, page_size, elapsed)

    # Extract datas:[...] — each item is a comma-separated string
    m = re.search(r'datas:\[(.+?)\]', text, re.DOTALL)
    if not m:
        return []

    raw_items = re.findall(r'"([^"]+)"', m.group(1))
    results: list[dict[str, Any]] = []
    for raw in raw_items:
        fields = raw.split(",")
        if len(fields) < 20:
            continue
        code = fields[0]
        if not re.match(r"^\d{6}$", code):
            continue
        results.append({
            "code": code,
            "name": fields[1],
            "one_year_return": _to_float(fields[11]),
            "three_year_return": _to_float(fields[13]),
            "fee": fields[20] if len(fields) > 20 else None,  # 折扣申购费率
            "size": _to_float(fields[18]) if len(fields) > 18 else None,  # 规模(亿)
        })
    return results


async def search_fund_by_name(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search funds by name/keyword via eastmoney suggest API.

    Returns list of {"code": "110011", "name": "易方达优质精选混合(QDII)", "type": "QDII-混合偏股"}.
    """
    params = {"callback": "cb", "m": "1", "key": keyword}
    t0 = time.perf_counter()
    client = _get_client()
    resp = await client.get(FUND_SEARCH_URL, params=params)
    resp.raise_for_status()
    text = resp.text.strip()
    elapsed = time.perf_counter() - t0
    logger.debug("search_fund_by_name [%s] %.3fs", keyword, elapsed)

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
