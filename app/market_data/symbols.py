"""Symbol registry: which exchange/currency/provider each display symbol uses.

US symbols come from Twelve Data; NSE (India) symbols come from Yahoo Finance
via yfinance with the ".NS" suffix. The registry is the single place that
maps a display symbol (what the UI and API use) to provider routing and
presentation metadata (currency, exchange, timezone).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str
    exchange: str  # "NASDAQ"/"NYSE" or "NSE"
    currency: str  # "USD" or "INR"
    provider: str  # "twelve_data" or "yfinance_nse"
    provider_symbol: str  # symbol passed to the provider
    timezone: str


_US_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
}

_NSE_NAMES = {
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "INFY": "Infosys",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "ITC": "ITC",
    "LT": "Larsen & Toubro",
    "BHARTIARTL": "Bharti Airtel",
    "ADANIENT": "Adani Enterprises",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "AXISBANK": "Axis Bank",
    "HINDUNILVR": "Hindustan Unilever",
    "BAJFINANCE": "Bajaj Finance",
    "MARUTI": "Maruti Suzuki",
    "TITAN": "Titan Company",
    "TATASTEEL": "Tata Steel",
    "WIPRO": "Wipro",
    "NTPC": "NTPC",
    "POWERGRID": "Power Grid Corp.",
}


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
        name=_NSE_NAMES.get(symbol, symbol),
        exchange="NSE",
        currency="INR",
        provider="yfinance_nse",
        provider_symbol=f"{symbol}.NS",
        timezone="Asia/Kolkata",
    )


def lookup_symbol(symbol: str) -> SymbolInfo | None:
    """Resolve a display symbol to its registry entry, or None if unknown."""
    normalized = symbol.strip().upper()
    if normalized in _US_NAMES:
        return _us(normalized)
    if normalized in _NSE_NAMES:
        return _nse(normalized)
    return None


def describe_symbol(symbol: str) -> SymbolInfo:
    """Resolve a display symbol, defaulting unknowns to the US/Twelve Data path."""
    return lookup_symbol(symbol) or _us(symbol.strip().upper())
