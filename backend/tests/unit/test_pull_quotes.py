"""pull_quotes.py 的交易时段门禁与超时配置测试。"""

from __future__ import annotations

import pull_quotes


async def test_skip_on_non_trading_day(monkeypatch, capsys) -> None:
    monkeypatch.setattr(pull_quotes, "is_trading_day", lambda d: False)

    await pull_quotes.main("http://127.0.0.1:1", force=False)

    assert "非交易日" in capsys.readouterr().out


async def test_skip_outside_trading_hours(monkeypatch, capsys) -> None:
    monkeypatch.setattr(pull_quotes, "is_trading_day", lambda d: True)
    monkeypatch.setattr(pull_quotes, "in_trading_hours", lambda: False)

    await pull_quotes.main("http://127.0.0.1:1", force=False)

    assert "盘中" in capsys.readouterr().out


async def test_force_pulls_regardless(monkeypatch, httpx_mock, capsys) -> None:
    monkeypatch.setattr(pull_quotes, "is_trading_day", lambda d: False)
    httpx_mock.add_response(
        json={"inserted": 3, "codes": 5, "captured_at": "2026-01-01T02:00:00+00:00"}
    )

    await pull_quotes.main("http://127.0.0.1:8010", force=True)

    assert "inserted=3" in capsys.readouterr().out
    assert len(httpx_mock.get_requests()) == 1


async def test_pulls_during_trading_hours(monkeypatch, httpx_mock, capsys) -> None:
    monkeypatch.setattr(pull_quotes, "is_trading_day", lambda d: True)
    monkeypatch.setattr(pull_quotes, "in_trading_hours", lambda: True)
    httpx_mock.add_response(
        json={"inserted": 2, "codes": 5, "captured_at": "2026-03-04T02:00:00+00:00"}
    )

    await pull_quotes.main("http://127.0.0.1:8010", force=False)

    assert "inserted=2" in capsys.readouterr().out


def test_timeout_defaults_to_120_and_env_overrides(monkeypatch) -> None:
    assert pull_quotes._timeout() == 120.0
    monkeypatch.setenv("PULL_QUOTES_TIMEOUT", "30")
    assert pull_quotes._timeout() == 30.0
