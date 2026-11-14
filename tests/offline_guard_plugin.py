"""Use only for local application suites, not provider-specific unit suites."""
import pytest
@pytest.fixture(autouse=True)
def no_real_market_providers(monkeypatch):
 from app.market_data.yfinance_provider import YFinanceNSEProvider
 from app.market_data.twelve_data import TwelveDataProvider
 def blocked(*a,**kw):pytest.fail('Unmocked market provider invocation prohibited in offline application tests')
 monkeypatch.setattr(YFinanceNSEProvider,'history',blocked)
 monkeypatch.setattr(TwelveDataProvider,'history',blocked)
