from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import httpx
from cachetools import TTLCache

from .core import CST, is_valid_code

_NAV_CACHE_TTL = 600  # 10 minutes
# In-process TTL cache for NAV history (avoids re-fetching on range changes);
# TTLCache evicts both on expiry and once maxsize is hit, unlike a plain dict.
_nav_history_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
    maxsize=500, ttl=_NAV_CACHE_TTL
)

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
    """GET with exponential backoff on transient network errors and 5xx responses."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, **kw)
            resp.raise_for_status()
            return resp
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # 4xx 是请求方问题,重试无意义
            last_error = e
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
    raise last_error or Exception(f"Failed GET {url}")


async def _fetch(url: str, **kw: Any) -> httpx.Response:
    """Shared-client GET with retry — the default path for all outbound requests."""
    return await _get_with_retry(_get_client(), url, **kw)


async def fetch_realtime_estimate(code: str) -> dict[str, Any]:
    url = FUND_GZ_URL.format(code=code)
    t0 = time.perf_counter()
    resp = await _fetch(url)
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

# Raw pingzhongdata text is shared by fetch_fund_info/fetch_fund_detail/
# fetch_nav_history — a short TTL coalesces the near-simultaneous calls a
# fund-detail page load triggers into a single download.
# ty: cachetools 存根的 __init__ 重载让 ty 0.0.57 推断出错误的泛型参数,误报
_pingzhong_cache: TTLCache[str, str] = TTLCache(maxsize=200, ttl=60)  # ty: ignore[invalid-assignment]
# per-code 单飞锁改用有界 TTLCache(原来用普通 dict 只增不减);
# TTLCache 本身非线程安全,访问时统一加 threading.Lock 守护
_pingzhong_locks: TTLCache[str, asyncio.Lock] = TTLCache(maxsize=256, ttl=86400)
_pingzhong_locks_mu = threading.Lock()


def _get_pingzhong_lock(code: str) -> asyncio.Lock:
    """取(或建)某个基金代码的单飞锁。"""
    with _pingzhong_locks_mu:
        lock = _pingzhong_locks.get(code)
        if lock is None:
            lock = asyncio.Lock()
            _pingzhong_locks[code] = lock
        return lock


async def _fetch_pingzhongdata_text(code: str) -> str:
    cached = _pingzhong_cache.get(code)
    if cached is not None:
        return cached
    # Single-flight per code: without this lock, concurrent callers (a
    # fund-detail page firing info/detail/nav-history at once) would all
    # cache-miss and each download, defeating the point of this cache.
    lock = _get_pingzhong_lock(code)
    async with lock:
        cached = _pingzhong_cache.get(code)
        if cached is not None:
            return cached
        t0 = time.perf_counter()
        resp = await _fetch(PINGZHONG_URL.format(code=code))
        text = resp.text
        logger.debug(
            "_fetch_pingzhongdata_text [%s] %.3fs", code, time.perf_counter() - t0
        )
        _pingzhong_cache[code] = text
        return text


# Common fund sector keywords to extract from fund name
_SECTOR_KEYWORDS = [
    "白酒",
    "医药",
    "医疗",
    "新能源",
    "光伏",
    "半导体",
    "芯片",
    "科技",
    "消费",
    "食品饮料",
    "军工",
    "国防",
    "银行",
    "证券",
    "金融",
    "地产",
    "房地产",
    "互联网",
    "传媒",
    "农业",
    "煤炭",
    "钢铁",
    "有色",
    "化工",
    "汽车",
    "电力",
    "环保",
    "养老",
    "红利",
    "沪深300",
    "中证500",
    "中证1000",
    "创业板",
    "科创",
    "恒生",
    "港股",
    "纳斯达克",
    "标普",
    "QDII",
    "债",
    "货币",
]


def _extract_sector(name: str) -> str | None:
    """Extract sector keyword from fund name."""
    for kw in _SECTOR_KEYWORDS:
        if kw in name:
            return kw
    return None


async def fetch_fund_info(code: str) -> dict[str, Any]:
    """Fetch fund basic info (name, sector) from eastmoney pingzhongdata."""
    text = await _fetch_pingzhongdata_text(code)

    # Parse: var fS_name = "招商中证白酒指数(LOF)A";
    name_m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else None

    sector = _extract_sector(name) if name else None

    return {"name": name, "sector": sector}


HOLDINGS_URL = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={code}&topline=10"
# fundf10 接口无 Referer 直接返回 404
_F10_HEADERS = {"Referer": "https://fundf10.eastmoney.com/"}

# Parse: 序号 / 股票代码 / 股票名称 / 占净值比例 / 持股数 / 持仓市值
# A股行用 tol/tor class，QDII 行全部是 toc class，故 class 无关匹配；
# 代码支持 A股6位数字 / 港股5位数字 / 美股字母（如 AAPL、BRK.B）
_HOLDING_ROW_RE = re.compile(
    r"<tr><td>\d+</td>"  # 序号
    r"<td[^>]*>.*?>([A-Z0-9.]+)</a></td>"  # 股票代码
    r"<td[^>]*>.*?>([^<]+)</a></td>"  # 股票名称
    r".*?"
    r"<td[^>]*>([\d.]+)%</td>"  # 占净值比例
    r"<td[^>]*>([\d,.]+)</td>"  # 持股数(万股)
    r"<td[^>]*>([\d,.]+)</td></tr>",  # 持仓市值(万元)
    re.DOTALL,
)


async def fetch_fund_holdings(code: str) -> list[dict[str, Any]]:
    """Fetch top-10 stock holdings for a fund from eastmoney."""
    t0 = time.perf_counter()
    resp = await _fetch(HOLDINGS_URL.format(code=code), headers=_F10_HEADERS)
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
        holdings.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "percentage": _to_float(pct_str),
                "shares_wan": _to_float(shares_str.replace(",", "")),
                "value_wan": _to_float(value_str.replace(",", "")),
            }
        )
    return holdings


def _parse_fund_size(text: str) -> float | None:
    """Fund size (亿) from fluctuation scale: series is [{y:374.98, mom:"..."}, ...]."""
    m = re.search(r"var Data_fluctuationScale\s*=\s*(\{.*?\});", text, re.DOTALL)
    if not m:
        return None
    try:
        series = json.loads(m.group(1)).get("series", [])
        return series[-1].get("y") if series else None
    except (json.JSONDecodeError, KeyError):
        return None


def _parse_period_returns(text: str) -> dict[str, float | None]:
    """syl_1y=近1月, syl_3y=近3月, syl_6y=近6月, syl_1n=近1年."""
    returns: dict[str, float | None] = {}
    for var_name, key in [
        ("syl_1y", "one_month_return"),
        ("syl_3y", "three_month_return"),
        ("syl_6y", "six_month_return"),
        ("syl_1n", "one_year_return"),
    ]:
        m = re.search(rf'var {var_name}\s*=\s*"([^"]*)"', text)
        if not m:
            m = re.search(rf"var {var_name}\s*=\s*([^;]*);", text)
        returns[key] = _to_float(m.group(1).strip('"')) if m else None
    return returns


def _parse_asset_allocation(text: str) -> list[dict[str, Any]]:
    """Data_assetAllocation: series items are {name, data:[...]}, aligned to dates."""
    m = re.search(r"var Data_assetAllocation\s*=\s*(\{.*?\});", text, re.DOTALL)
    if not m:
        return []
    try:
        series = json.loads(m.group(1)).get("series", [])
        allocation = []
        for s in series:
            name = s.get("name", "")
            if "净资产" in name:
                continue  # net asset value is not an allocation category
            data = s.get("data", [])
            if data:
                allocation.append({"name": name, "value": data[-1]})
        return allocation
    except (json.JSONDecodeError, KeyError):
        return []


def _parse_manager_power(
    text: str, code: str
) -> tuple[list[Any] | None, list[Any] | None]:
    """Manager power scores/categories from the first Data_currentFundManager entry."""
    raw_managers = _extract_js_array(text, "Data_currentFundManager")
    if not raw_managers:
        return None, None
    try:
        power = raw_managers[0].get("power", {})
        return power.get("data"), power.get("categories")
    except AttributeError as e:
        logger.debug("manager_power parse failed for %s: %s", code, e)
        return None, None


async def fetch_fund_detail(code: str) -> dict[str, Any]:
    """Fetch comprehensive fund detail from eastmoney pingzhongdata.

    Returns: name, manager, size, established_date, period returns,
    asset allocation, etc.
    """
    text = await _fetch_pingzhongdata_text(code)

    result: dict[str, Any] = {"code": code}

    m = re.search(r'var fS_name\s*=\s*"([^"]*)"', text)
    result["name"] = m.group(1) if m else None

    m = re.search(r'var fS_code\s*=\s*"([^"]*)"', text)
    result["fund_code"] = m.group(1) if m else code

    m = re.search(r'var fS_type\s*=\s*"([^"]*)"', text)
    result["fund_type"] = m.group(1) if m else None

    # Manager — extract name from the first manager entry
    m = re.search(
        r'"name":"([^"]*)"',
        text[text.find("Data_currentFundManager") :]
        if "Data_currentFundManager" in text
        else "",
    )
    result["manager"] = m.group(1) if m else None

    result["size"] = _parse_fund_size(text)

    # Established date — not always a separate var, extract from fund page if needed
    m = re.search(r'var fS_nkfr\s*=\s*"([^"]*)"', text)
    result["established_date"] = m.group(1) if m else None

    result.update(_parse_period_returns(text))
    result["asset_allocation"] = _parse_asset_allocation(text)
    result["sector"] = _extract_sector(result["name"]) if result["name"] else None

    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]*)"', text)
    result["subscription_rate"] = _to_float(m.group(1)) if m else None

    m = re.search(r'var fund_Rate\s*=\s*"([^"]*)"', text)
    result["subscription_rate_discounted"] = _to_float(m.group(1)) if m else None

    scores, categories = _parse_manager_power(text, code)
    result["manager_power_scores"] = scores
    result["manager_power_categories"] = categories

    return result


def _extract_js_array(text: str, var_name: str) -> list[Any] | None:
    """Extract a JS array variable from text using bracket matching."""
    idx = text.find(f"var {var_name}")
    if idx < 0:
        return None
    sub = text[idx:]
    eq_idx = sub.find("=")
    if eq_idx < 0:
        return None
    rest = sub[eq_idx + 1 :].strip()
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
        parsed: list[Any] = json.loads(rest[:end])
        return parsed
    except json.JSONDecodeError:
        return None


async def fetch_nav_history(code: str, limit: int = 365) -> list[dict[str, Any]]:
    """Fetch historical NAV data from eastmoney pingzhongdata.

    Returns list of {date, nav, accNav, dailyReturn}.
    Results are cached in-process for 10 minutes (TTL) to avoid repeated fetches
    when the user switches between chart range buttons.
    """
    full_data = _nav_history_cache.get(code)
    if full_data is not None:
        return full_data[-limit:] if limit < len(full_data) else full_data

    text = await _fetch_pingzhongdata_text(code)

    from datetime import datetime as dt

    history: list[dict[str, Any]] = []

    # eastmoney 的时间戳是北京时间零点,必须带时区解析;
    # naive fromtimestamp 在 UTC 部署环境下会把日期解析偏早一天
    raw = _extract_js_array(text, "Data_netWorthTrend")
    if raw:
        for item in raw:
            ts = item.get("x", 0)
            date_str = (
                dt.fromtimestamp(ts / 1000, tz=CST).strftime("%Y-%m-%d") if ts else None
            )
            history.append(
                {
                    "date": date_str,
                    "nav": item.get("y"),
                    "dailyReturn": item.get("equityReturn"),
                }
            )

    # Data_ACWorthTrend = [[timestamp, accNav], ...]
    acc_map: dict[str, float] = {}
    raw_acc = _extract_js_array(text, "Data_ACWorthTrend")
    if raw_acc:
        for item in raw_acc:
            try:
                ts, acc = item[0], item[1]
                date_str = (
                    dt.fromtimestamp(ts / 1000, tz=CST).strftime("%Y-%m-%d")
                    if ts
                    else None
                )
                if date_str:
                    acc_map[date_str] = acc
            except (IndexError, TypeError):
                continue

    for h in history:
        h["accNav"] = acc_map.get(h["date"])

    # Store full history in cache; callers slice by limit from here
    _nav_history_cache[code] = history
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
    var hq_str_hkHSI="HSI,name,prev_close,open,high,low,current,change,change_pct,...";

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
        results.append(
            {
                "code": index_info["code"],
                "name": index_info["name"],
                "region": index_info["region"],
                "value": float(current.quantize(_cent, rounding=ROUND_HALF_UP)),
                "change": float(change.quantize(_cent, rounding=ROUND_HALF_UP)),
                "change_percent": float(
                    change_percent.quantize(_cent, rounding=ROUND_HALF_UP)
                ),
            }
        )

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


_LSJZ_HEADERS = {"Referer": "https://fund.eastmoney.com/"}


async def fetch_latest_nav(code: str) -> dict[str, Any] | None:
    """Fetch the most recent NAV record. Returns {date, nav} or None."""
    params = {"fundCode": code, "pageIndex": 1, "pageSize": 1}
    t0 = time.perf_counter()
    resp = await _fetch(LSJZ_URL, params=params, headers=_LSJZ_HEADERS)
    data = resp.json()
    logger.debug("fetch_latest_nav [%s] %.3fs", code, time.perf_counter() - t0)
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
    t0 = time.perf_counter()
    resp = await _fetch(LSJZ_URL, params=params, headers=_LSJZ_HEADERS)
    data = resp.json()
    elapsed = time.perf_counter() - t0
    logger.debug("fetch_nav_on_date [%s@%s] %.3fs", code, date, elapsed)
    items = (data.get("Data") or {}).get("LSJZList") or []
    if items:
        return _to_float(items[0].get("DWJZ"))
    return None


RANKING_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
_MOBILE_RANKING_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNRank"
_MOBILE_RANKING_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/91.0",
}
# mobile API 不支持按类型过滤，对特殊板块做名称兜底
_MOBILE_TYPE_KW = {"qdii": "QDII", "zq": "债", "hb": "货币"}
_RANKING_HEADERS = {
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/javascript, application/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

# rankhandler.aspx comma-separated field positions (undocumented, order-dependent)
_RANK_IDX_CODE = 0
_RANK_IDX_NAME = 1
_RANK_IDX_ONE_YEAR = 11
_RANK_IDX_THREE_YEAR = 13
_RANK_IDX_SIZE = 18
_RANK_IDX_FEE = 20
_RANK_MIN_FIELDS = 20  # below this, the row is missing fields we rely on


async def _fetch_ranking_mobile(fund_type: str, page_size: int) -> list[dict[str, Any]]:
    """Fallback ranking via eastmoney mobile API (FundMNRank).

    Limitations vs primary source:
    - Returns at most ~30 results regardless of page_size (API cap).
    - Does not support fund_type filtering; for qdii/zq/hb we filter by name,
      which may return 0 if none appear in the top results.
    - fee field is not available (None).
    - size is derived from ENDNAV (元 ÷ 1e8 → 亿).
    """
    params = {
        "pageIndex": "1",
        "pageSize": str(page_size),
        "plat": "Android",
        "appType": "ttjj",
        "product": "EFund",
        "Version": "6.3.8",
        "deviceid": "fwefwef123",
        "SortColumn": "SYL_1N",
        "Sort": "desc",
    }
    t0 = time.perf_counter()
    resp = await _fetch(
        _MOBILE_RANKING_URL, params=params, headers=_MOBILE_RANKING_HEADERS
    )
    data = resp.json()
    elapsed = time.perf_counter() - t0
    logger.debug(
        "_fetch_ranking_mobile [ft=%s, n=%s] %.3fs", fund_type, page_size, elapsed
    )

    datas: list[dict[str, Any]] = data.get("Datas") or []
    kw = _MOBILE_TYPE_KW.get(fund_type)
    if kw:
        datas = [f for f in datas if kw in f.get("SHORTNAME", "")]

    results: list[dict[str, Any]] = []
    for f in datas:
        code = f.get("FCODE", "")
        if not is_valid_code(code):
            continue
        end_nav = _to_float(f.get("ENDNAV"))
        results.append(
            {
                "code": code,
                "name": f.get("SHORTNAME", ""),
                "one_year_return": _to_float(f.get("SYL_1N")),
                "three_year_return": _to_float(f.get("SYL_3N")),
                "fee": None,
                "size": end_nav / 1e8 if end_nav else None,
            }
        )
    return results


async def fetch_fund_ranking(
    fund_type: str = "gp", page_size: int = 200
) -> list[dict[str, Any]]:
    """Fetch fund ranking from eastmoney.

    fund_type: 'gp' (股票型), 'hh' (混合型), 'zq' (债券型)
    Returns list of dicts: code, name, one_year_return, three_year_return, fee, size.
    Falls back to mobile API if primary source returns -999 or empty.
    """
    from datetime import date, timedelta

    today = date.today()
    sd = (today - timedelta(days=3 * 365)).isoformat()
    ed = today.isoformat()

    params = {
        "op": "ph",
        "dt": "kf",
        "ft": fund_type,
        "rs": "",
        "gs": "0",
        "sc": "3yzf",
        "st": "desc",
        "sd": sd,
        "ed": ed,
        "pi": "1",
        "pn": str(page_size),
        "dx": "1",
        "qdii": "",
        "tabSubtype": ",,,,,",
    }
    try:
        t0 = time.perf_counter()
        resp = await _fetch(RANKING_URL, params=params, headers=_RANKING_HEADERS)
        text = resp.text
        elapsed = time.perf_counter() - t0
        logger.debug(
            "fetch_fund_ranking [ft=%s, n=%s] %.3fs", fund_type, page_size, elapsed
        )

        if "ErrCode:-999" in text or "无访问权限" in text:
            raise ValueError("rankhandler returned -999")

        m = re.search(r"datas:\[(.+?)\]", text, re.DOTALL)
        if not m:
            raise ValueError("rankhandler: datas block not found")

        raw_items = re.findall(r'"([^"]+)"', m.group(1))
        results: list[dict[str, Any]] = []
        for raw in raw_items:
            fields = raw.split(",")
            if len(fields) < _RANK_MIN_FIELDS:
                continue
            code = fields[_RANK_IDX_CODE]
            if not is_valid_code(code):
                continue
            results.append(
                {
                    "code": code,
                    "name": fields[_RANK_IDX_NAME],
                    "one_year_return": _to_float(fields[_RANK_IDX_ONE_YEAR]),
                    "three_year_return": _to_float(fields[_RANK_IDX_THREE_YEAR]),
                    "fee": (
                        fields[_RANK_IDX_FEE] if len(fields) > _RANK_IDX_FEE else None
                    ),
                    "size": (
                        _to_float(fields[_RANK_IDX_SIZE])
                        if len(fields) > _RANK_IDX_SIZE
                        else None
                    ),
                }
            )
        if results:
            return results
        raise ValueError("rankhandler: parsed 0 results")

    except Exception as exc:
        logger.warning(
            "fetch_fund_ranking primary failed (%s), falling back to mobile", exc
        )
        return await _fetch_ranking_mobile(fund_type, page_size)


_EASTMONEY_DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_DC_HEADERS = {"Referer": "https://data.eastmoney.com/"}


def _recent_quarter_ends(n: int = 4) -> list[str]:
    """Return last n quarter-end dates (YYYY-MM-DD) from newest to oldest."""
    # ponytail: 最多试 n 个季度,避免硬编码报告期
    today = date.today()
    ends = []
    # Enumerate candidate quarter ends backwards from today
    y, m = today.year, today.month
    for _ in range(n * 2):  # extra headroom; break when we have n
        if m > 9:
            qend = date(y, 12, 31)
        elif m > 6:
            qend = date(y, 9, 30)
        elif m > 3:
            qend = date(y, 6, 30)
        else:
            qend = date(y, 3, 31)
        if qend < today and qend.strftime("%Y-%m-%d") not in ends:
            ends.append(qend.strftime("%Y-%m-%d"))
        # step back one quarter
        if m <= 3:
            y -= 1
            m = 12
        elif m <= 6:
            m = 3
        elif m <= 9:
            m = 6
        else:
            m = 9
        if len(ends) >= n:
            break
    return ends


async def fetch_funds_holding_stock(stock_code: str, limit: int = 50) -> dict[str, Any]:
    """Return public funds holding *stock_code*, sorted by position value desc.

    Queries eastmoney datacenter (RPT_MAINDATA_MAIN_POSITIONDETAILS) with
    ORG_TYPE_CODE=1 (公募基金 only).  Tries recent quarter-ends newest-first;
    falls back to the previous quarter when data is not yet published.

    Returns:
        {stock_code, stock_name, report_date, count, items[]}
        Each item: {code, name, hold_market_cap, shares, netasset_ratio, company}
    """
    client = _get_client()
    quarters = _recent_quarter_ends(4)
    for qdate in quarters:
        params = {
            "sortColumns": "HOLD_MARKET_CAP",
            "sortTypes": "-1",
            "pageSize": str(limit),
            "pageNumber": "1",
            "reportName": "RPT_MAINDATA_MAIN_POSITIONDETAILS",
            "columns": (
                "SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,"
                "HOLDER_CODE,HOLDER_NAME,HOLD_MARKET_CAP,"
                "TOTAL_SHARES,NETASSET_RATIO,PARENT_ORG_NAME"
            ),
            "filter": (
                f'(SECURITY_CODE="{stock_code}")'
                f"(REPORT_DATE='{qdate}')"
                '(ORG_TYPE_CODE="1")'
            ),
            "source": "WEB",
            "client": "WEB",
        }
        t0 = time.perf_counter()
        resp = await _get_with_retry(
            client, _EASTMONEY_DC, params=params, headers=_DC_HEADERS
        )
        elapsed = time.perf_counter() - t0
        logger.debug(
            "fetch_funds_holding_stock [%s] %s %.3fs", stock_code, qdate, elapsed
        )
        data = resp.json()
        result = data.get("result") or {}
        if not result.get("count"):
            continue  # try previous quarter

        stock_name = None
        items = []
        for row in result.get("data") or []:
            if stock_name is None:
                stock_name = row.get("SECURITY_NAME_ABBR")
            items.append(
                {
                    "code": row.get("HOLDER_CODE", ""),
                    "name": row.get("HOLDER_NAME", ""),
                    "hold_market_cap": row.get("HOLD_MARKET_CAP"),
                    "shares": row.get("TOTAL_SHARES"),
                    "netasset_ratio": row.get("NETASSET_RATIO"),
                    "company": row.get("PARENT_ORG_NAME"),
                }
            )
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "report_date": qdate,
            "count": result["count"],
            "items": items,
        }

    # All quarters returned empty
    return {
        "stock_code": stock_code,
        "stock_name": None,
        "report_date": None,
        "count": 0,
        "items": [],
    }


async def search_fund_by_name(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search funds by name/keyword via eastmoney suggest API.

    Returns list of {"code": "110011", "name": "易方达优质精选(QDII)", "type": "QDII"}.
    """
    params = {"callback": "cb", "m": "1", "key": keyword}
    t0 = time.perf_counter()
    resp = await _fetch(FUND_SEARCH_URL, params=params)
    text = resp.text.strip()
    logger.debug("search_fund_by_name [%s] %.3fs", keyword, time.perf_counter() - t0)

    # Strip JSONP wrapper: cb({...})
    if text.startswith("cb(") and text.endswith(")"):
        text = text[3:-1]
    data = json.loads(text)

    results: list[dict[str, Any]] = []
    for item in data.get("Datas") or []:
        if len(results) >= limit:
            break
        code = item.get("CODE", "")
        if not is_valid_code(code):
            continue
        # ponytail: CATEGORY==700 = 基金; 100=股票,600=指数 — 过滤掉非基金防污染
        if item.get("CATEGORY") != 700:
            continue
        entry: dict[str, Any] = {"code": code, "name": item.get("NAME", "")}
        base = item.get("FundBaseInfo") or {}
        if base.get("FTYPE"):
            entry["type"] = base["FTYPE"]
        results.append(entry)
    return results


# ── Stock industry enrichment ─────────────────────────────────────────────────
# ponytail: 行业基本不变，落表持久化；要纠正分类改库行，要强制刷新删行重拉

_STOCK_INDUSTRY_URL = "https://push2.eastmoney.com/api/qt/stock/get"


def _secid(stock_code: str) -> str:
    """Eastmoney secid prefix: 1 for Shanghai (6x/9x), 0 for Shenzhen/Beijing."""
    return "1" if stock_code[0] in "69" else "0"


async def fetch_stock_industries_from_source(
    codes: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    """Query eastmoney for {code: (stock_name, industry)}. No caching, no DB —
    persistence and the local-table short-circuit live in
    services.stock_industry_service so this adapter only ever returns data.
    """
    sem = asyncio.Semaphore(8)

    async def _one(code: str) -> tuple[str, str | None, str | None]:
        if not re.match(r"^\d{6}$", code):  # skip non-A-share codes (e.g. HK 5-digit)
            return code, None, None
        async with sem:
            try:
                resp = await _fetch(
                    f"{_STOCK_INDUSTRY_URL}?secid={_secid(code)}.{code}"
                    "&fields=f57,f58,f127"
                )
                data = resp.json().get("data") or {}
                return code, data.get("f58"), data.get("f127")
            except Exception:
                logger.debug("fetch_stock_industries_from_source: failed for %s", code)
                return code, None, None

    fetched = await asyncio.gather(*[_one(c) for c in codes])
    return {code: (name, industry) for code, name, industry in fetched}
