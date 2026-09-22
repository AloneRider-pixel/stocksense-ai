from app.market_data.twelve_data import TwelveDataProvider


def test_twelve_data_bar_parsing() -> None:
    bar = TwelveDataProvider._to_bar(
        "AAPL",
        {
            "datetime": "2026-09-18 00:00:00",
            "open": "243.10",
            "high": "246.20",
            "low": "242.50",
            "close": "245.80",
            "volume": "12345678",
        },
    )

    assert bar.symbol == "AAPL"
    assert bar.date == "2026-09-18"
    assert bar.close == 245.80
    assert bar.volume == 12345678
