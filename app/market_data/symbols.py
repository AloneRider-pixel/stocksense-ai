"""Symbol registry: which exchange/currency/provider each display symbol uses.

India-first: the default universe is the NIFTY 50 (NSE) plus the NIFTY 50
index itself as the benchmark series. NSE symbols come from Yahoo Finance
via yfinance with the ".NS" suffix; the index uses "^NSEI". A small set of
US mega-caps (Twelve Data) remains available for comparison but is not part
of the default universe.

The NIFTY 50 constituent list below is a snapshot for the demo universe;
index membership changes over time. Update _NIFTY50_NAMES to refresh it.

The registry is the single place that maps a display symbol (what the UI and
API use) to provider routing and presentation metadata (currency, exchange,
timezone).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str
    exchange: str  # "NSE", "NSE Index", or "US"
    currency: str  # "INR" or "USD"
    provider: str  # "yfinance_nse" or "twelve_data"
    provider_symbol: str  # symbol passed to the provider
    timezone: str
    is_index: bool = False
    asset_class: str = "equity"  # "equity" | "index" | "metal" | "currency"


# NIFTY 50 constituents (snapshot). Keys are the display symbols; provider
# symbols get the ".NS" suffix for Yahoo Finance.
_NIFTY50_NAMES = {
    "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports & SEZ",
    "APOLLOHOSP": "Apollo Hospitals",
    "ASIANPAINT": "Asian Paints",
    "AXISBANK": "Axis Bank",
    "BAJAJ-AUTO": "Bajaj Auto",
    "BAJFINANCE": "Bajaj Finance",
    "BAJAJFINSV": "Bajaj Finserv",
    "BEL": "Bharat Electronics",
    "BHARTIARTL": "Bharti Airtel",
    "CIPLA": "Cipla",
    "COALINDIA": "Coal India",
    "DRREDDY": "Dr. Reddy's Laboratories",
    "EICHERMOT": "Eicher Motors",
    "ETERNAL": "Eternal (Zomato)",
    "GRASIM": "Grasim Industries",
    "HCLTECH": "HCL Technologies",
    "HDFCBANK": "HDFC Bank",
    "HDFCLIFE": "HDFC Life Insurance",
    "HEROMOTOCO": "Hero MotoCorp",
    "HINDALCO": "Hindalco Industries",
    "HINDUNILVR": "Hindustan Unilever",
    "ICICIBANK": "ICICI Bank",
    "INDUSINDBK": "IndusInd Bank",
    "INFY": "Infosys",
    "ITC": "ITC",
    "JIOFIN": "Jio Financial Services",
    "JSWSTEEL": "JSW Steel",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "LT": "Larsen & Toubro",
    "M&M": "Mahindra & Mahindra",
    "MARUTI": "Maruti Suzuki",
    "NESTLEIND": "Nestle India",
    "NTPC": "NTPC",
    "ONGC": "Oil & Natural Gas Corp.",
    "POWERGRID": "Power Grid Corp.",
    "RELIANCE": "Reliance Industries",
    "SBILIFE": "SBI Life Insurance",
    "SBIN": "State Bank of India",
    "SHRIRAMFIN": "Shriram Finance",
    "SUNPHARMA": "Sun Pharmaceutical",
    "TATACONSUM": "Tata Consumer Products",
    "TATAMOTORS": "Tata Motors",
    "TATASTEEL": "Tata Steel",
    "TCS": "Tata Consultancy Services",
    "TECHM": "Tech Mahindra",
    "TITAN": "Titan Company",
    "TRENT": "Trent",
    "ULTRACEMCO": "UltraTech Cement",
    "WIPRO": "Wipro",
}

# Benchmark index (not a forecast target; used for comparison only).
_INDEX_NAMES = {
    "NIFTY50": ("NIFTY 50 Index", "^NSEI"),
}

# Precious metals (spot, USD, delayed/indicative via Yahoo Finance; these are
# NOT MCX futures and not exchange-traded Indian securities).
_METAL_NAMES = {
    "GOLD": ("Gold (spot, USD)", "XAUUSD=X"),
    "SILVER": ("Silver (spot, USD)", "XAGUSD=X"),
}

# Currency pairs vs INR (indicative interbank rates via Yahoo Finance;
# delayed, not executable prices).
_CURRENCY_NAMES = {
    "USDINR": ("US Dollar / Indian Rupee", "USDINR=X"),
    "EURINR": ("Euro / Indian Rupee", "EURINR=X"),
    "GBPINR": ("British Pound / Indian Rupee", "GBPINR=X"),
}

# Demoted: a few US mega-caps remain available via Twelve Data for
# comparison, but they are not part of the default universe or demo seeds.
_US_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
}

# Backwards-compatible alias used by older config/tests.
_NSE_NAMES = _NIFTY50_NAMES


def _us(symbol: str) -> SymbolInfo:
    return SymbolInfo(
        symbol=symbol,
        name=_US_NAMES.get(symbol, symbol),
        exchange="US",
        currency="USD",
        provider="twelve_data",
        provider_symbol=symbol,
        timezone="America/New_York",
    )


def _nse(symbol: str) -> SymbolInfo:
    return SymbolInfo(
        symbol=symbol,
        name=_NIFTY50_NAMES.get(symbol, symbol),
        exchange="NSE",
        currency="INR",
        provider="yfinance_nse",
        provider_symbol=f"{symbol}.NS",
        timezone="Asia/Kolkata",
    )


def _index(symbol: str) -> SymbolInfo:
    name, provider_symbol = _INDEX_NAMES[symbol]
    return SymbolInfo(
        symbol=symbol,
        name=name,
        exchange="NSE Index",
        currency="INR",
        provider="yfinance_nse",
        provider_symbol=provider_symbol,
        timezone="Asia/Kolkata",
        is_index=True,
        asset_class="index",
    )


def _metal(symbol: str) -> SymbolInfo:
    name, provider_symbol = _METAL_NAMES[symbol]
    return SymbolInfo(
        symbol=symbol,
        name=name,
        exchange="Spot (indicative)",
        currency="USD",
        provider="yfinance_nse",
        provider_symbol=provider_symbol,
        timezone="UTC",
        asset_class="metal",
    )


def _currency(symbol: str) -> SymbolInfo:
    name, provider_symbol = _CURRENCY_NAMES[symbol]
    return SymbolInfo(
        symbol=symbol,
        name=name,
        exchange="FX (indicative)",
        currency="INR",
        provider="yfinance_nse",
        provider_symbol=provider_symbol,
        timezone="UTC",
        asset_class="currency",
    )


def lookup_symbol(symbol: str) -> SymbolInfo | None:
    """Resolve a display symbol to its registry entry, or None if unknown."""
    normalized = symbol.strip().upper()
    if normalized in _INDEX_NAMES:
        return _index(normalized)
    if normalized in _METAL_NAMES:
        return _metal(normalized)
    if normalized in _CURRENCY_NAMES:
        return _currency(normalized)
    if normalized in _NIFTY50_NAMES:
        return _nse(normalized)
    if normalized in _US_NAMES:
        return _us(normalized)
    return None


def metal_symbols() -> list[str]:
    return sorted(_METAL_NAMES)


def currency_symbols() -> list[str]:
    return sorted(_CURRENCY_NAMES)


def describe_symbol(symbol: str) -> SymbolInfo:
    """Resolve a display symbol; unknowns fall back to the US/Twelve Data path."""
    return lookup_symbol(symbol) or _us(symbol.strip().upper())


def nifty50_symbols() -> list[str]:
    """The default Indian universe: NIFTY 50 constituents (forecast targets)."""
    return sorted(_NIFTY50_NAMES)


BENCHMARK_INDEX_SYMBOL = "NIFTY50"
