"""Tests for _HOLDING_ROW_RE parsing A-share and QDII (US/HK) holding rows."""

from __future__ import annotations

from app import fund_source

_A_SHARE_ROW = (
    "<tr><td>1</td>"
    "<td><a href='//quote.eastmoney.com/unify/r/1.600519'>600519</a></td>"
    "<td class='tol'><a href='//quote.eastmoney.com/unify/r/1.600519'>贵州茅台</a></td>"
    "<td class='tor'><span data-id='dq600519'></span></td>"
    "<td class='tor'><span data-id='zd600519'></span></td>"
    "<td class='xglj'><a href='ccbdxq_161725_600519.html' class='red'>变动详情</a>"
    "<a href='//guba.eastmoney.com/interface/GetList.aspx?code=1.600519' >股吧</a>"
    "<a href='//quote.eastmoney.com/unify/r/1.600519' >行情</a></td>"
    "<td class='tor'>18.33%</td>"
    "<td class='tor'>508.34</td>"
    "<td class='tor'>737,086.62</td></tr>"
)

_QDII_ROWS = (
    "<tr><td>1</td>"
    "<td class='toc'><a href='//quote.eastmoney.com/unify/r/105.ASML' >ASML</a></td>"
    "<td class='toc' style='line-height:18px'>"
    "<a href='//quote.eastmoney.com/unify/r/105.ASML'>阿斯麦</a></td>"
    "<td class='toc' ><span data-id='dqASML'>--</span></td>"
    "<td class='toc' ><span data-id='zdASML'>--</span></td>"
    "<td class='xglj'>"
    "<a href='//guba.eastmoney.com/interface/GetList.aspx?code=105.ASML' >股吧</a>"
    "<a href='//quote.eastmoney.com/unify/r/105.ASML' >行情</a></td>"
    "<td class='toc'>5.21%</td>"
    "<td class='toc'>8.57</td>"
    "<td class='toc'>78,350.74</td></tr>"
    "<tr><td>2</td>"
    "<td class='toc'><a href='//quote.eastmoney.com/unify/r/116.02513' >02513</a></td>"
    "<td class='toc' style='line-height:18px'>"
    "<a href='//quote.eastmoney.com/unify/r/116.02513'>泡泡玛特</a></td>"
    "<td class='toc' ><span data-id='dq02513'>--</span></td>"
    "<td class='toc' ><span data-id='zd02513'>--</span></td>"
    "<td class='xglj'>"
    "<a href='//guba.eastmoney.com/interface/GetList.aspx?code=116.02513' >股吧</a>"
    "<a href='//quote.eastmoney.com/unify/r/116.02513' >行情</a></td>"
    "<td class='toc'>4.80%</td>"
    "<td class='toc'>120.00</td>"
    "<td class='toc'>65,000.00</td></tr>"
)


def test_parses_a_share_row() -> None:
    matches = list(fund_source._HOLDING_ROW_RE.finditer(_A_SHARE_ROW))
    assert len(matches) == 1
    code, name, pct, shares, value = matches[0].groups()
    assert code == "600519"
    assert name == "贵州茅台"
    assert float(pct) == 18.33


def test_parses_qdii_rows_regardless_of_class() -> None:
    matches = list(fund_source._HOLDING_ROW_RE.finditer(_QDII_ROWS))
    assert len(matches) == 2

    code, name, pct, shares, value = matches[0].groups()
    assert code == "ASML"
    assert name == "阿斯麦"
    assert float(pct) == 5.21

    code, name, pct, shares, value = matches[1].groups()
    assert code == "02513"
    assert name == "泡泡玛特"
    assert float(pct) == 4.80
