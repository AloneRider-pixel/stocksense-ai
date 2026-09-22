from app.market_data.csv_provider import CSVMarketDataProvider


def test_demo_market_data_provider() -> None:
    bars = CSVMarketDataProvider().history("DEMO", limit=5)

    assert len(bars) == 5
    assert bars[-1].symbol == "DEMO"
    assert bars[-1].close > 0
    assert bars[-1].volume > 0
