"""Registry of available tickers and lookup helpers.

A single source of truth for every ticker the tool knows how to analyze. Each
entry carries the yfinance symbol, market/currency metadata, the daily leverage
factor, and (for leveraged ETFs) the base ticker used to correct undocumented
price discontinuities in the leveraged series (see data.py).
"""

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Ticker:
    symbol: str  # CLI key and registry key, e.g. "00631L", "QQQ"
    yf_symbol: str  # symbol passed to yfinance, e.g. "00631L.TW", "QQQ"
    name: str  # human-readable name
    market: str  # "TW" or "US"
    currency: str  # "TWD" or "USD"
    leverage: float  # daily leverage factor: 1.0 for a base ETF, 2.0 for a 2x leveraged ETF
    base_symbol: str | None  # for leveraged tickers, the base ticker used for discontinuity correction; None for a base ETF


# The available tickers. Leveraged entries point at their base via base_symbol so
# the leverage-discontinuity fix in data.py can resolve a reference series.
TICKERS: dict[str, Ticker] = {
    "0050": Ticker("0050", "0050.TW", "Yuanta Taiwan 50", "TW", "TWD", 1.0, None),
    "00631L": Ticker("00631L", "00631L.TW", "Yuanta Daily Taiwan 50 Bull 2X", "TW", "TWD", 2.0, "0050"),
    "QQQ": Ticker("QQQ", "QQQ", "Invesco QQQ Trust (Nasdaq-100)", "US", "USD", 1.0, None),
    "QLD": Ticker("QLD", "QLD", "ProShares Ultra QQQ (2x Nasdaq-100)", "US", "USD", 2.0, "QQQ"),
}


def available_symbols() -> list[str]:
    """Canonical ticker symbols in registry order."""
    return list(TICKERS)


def get_ticker(symbol: str) -> Ticker:
    """Resolve a ticker symbol (case-insensitive) to its registry entry.

    Raises KeyError with the list of available symbols if the symbol is unknown.
    """
    for key, ticker in TICKERS.items():
        if key.casefold() == symbol.casefold():
            return ticker
    raise KeyError(f"Unknown ticker {symbol!r}. Available tickers: {', '.join(available_symbols())}")


def list_tickers() -> list[Ticker]:
    """All registered tickers, in registry order."""
    return list(TICKERS.values())


def ticker_symbol(raw: str) -> str:
    """argparse `type=` converter: validate against the registry, return the canonical symbol.

    Rejecting unknown symbols here means the error surfaces at parse time with a
    helpful message rather than as a download failure deeper in the pipeline.
    """
    try:
        return get_ticker(raw).symbol
    except KeyError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
