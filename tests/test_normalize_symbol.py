from app.market_data.symbols import lookup_symbol, normalize_symbol


def test_ns_suffix_dropped_only_for_registered_nse_equities():
    assert normalize_symbol(" reliance.ns ") == "RELIANCE"
    assert normalize_symbol("RELIANCE") == "RELIANCE"
    assert normalize_symbol("AAPL") == "AAPL"
    # unregistered input is not guessed into another market
    assert normalize_symbol("FOOBAR.NS") == "FOOBAR.NS"
    assert normalize_symbol(None) == ""


def test_lookup_resolves_ns_input_to_the_nse_entry_not_us():
    info = lookup_symbol("RELIANCE.NS")
    assert info is not None and info.exchange == "NSE" and info.symbol == "RELIANCE"
    assert lookup_symbol("FOOBAR.NS") is None


def test_unsupported_exchange_suffixes_are_refused_not_routed_to_us():
    import pytest

    from app.market_data.symbols import UnsupportedSymbolError, describe_symbol, has_unsupported_exchange_suffix

    for bad in ["RELIANCE.BO", "VOD.L", "SHOP.TO", "FOOBAR.NS", "xyz.hk"]:
        assert has_unsupported_exchange_suffix(bad), bad
        with pytest.raises(UnsupportedSymbolError):
            describe_symbol(bad)
    for ok in ["RELIANCE.NS", "RELIANCE", "AAPL", "BRK.B", "TSLA"]:
        assert not has_unsupported_exchange_suffix(ok), ok
    assert describe_symbol("TSLA").exchange == "US"  # plain unregistered tickers keep the existing US path


def test_one_unsupported_stored_symbol_does_not_abort_screener_or_report(monkeypatch):
    from app.services.screener import screen_universe

    bars = [{"date": f"2026-10-{i + 1:02d}", "close": 100.0 + i, "volume": 1000} for i in range(25)]
    rows = screen_universe({"VOD.L": bars, "RELIANCE": bars, "AAPL": bars})
    assert sorted(r["symbol"] for r in rows) == ["AAPL", "RELIANCE"]
