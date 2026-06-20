"""Price loading via yfinance with local CSV caching."""

from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import BacktestConfig
from .tickers import get_ticker

# Project root is three levels up from this file (src/stock_analysis/data.py).
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _cache_path(ticker: str, start: str, end: str) -> Path:
    safe_ticker = ticker.replace("/", "_")
    return DATA_DIR / f"{safe_ticker}_{start}_{end}.csv"


def _download_close(ticker: str, start: str, end: str) -> pd.Series:
    cache_file = _cache_path(ticker, start, end)
    if cache_file.exists():
        series = pd.read_csv(cache_file, index_col=0, parse_dates=True)["close"]
        series.name = ticker
        return series

    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError(
            f"No price data returned for {ticker} between {start} and {end}. "
            "Check the ticker symbol and your network connection."
        )
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    close.name = ticker

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    close.rename("close").to_csv(cache_file)
    return close


def _fix_leverage_discontinuities(
    lev: pd.Series, base: pd.Series, leverage: float, threshold: float = 0.3
) -> pd.Series:
    """Back-adjust undocumented price discontinuities in the leveraged ETF series.

    Daily-leveraged ETFs like 00631L or QLD occasionally undergo unit
    consolidations that Yahoo Finance fails to record as a stock split, leaving a
    single-day price cliff with no corresponding split entry. Such a cliff is
    detected by checking whether a day's return tracks roughly `leverage`x the
    base ETF's same-day return; a large unexplained deviation is treated as a
    data discontinuity, and all prior history is rescaled so the series splices
    back together.
    """
    aligned = pd.concat([lev, base], axis=1, join="inner")
    aligned.columns = ["lev", "base"]
    lev_ret = aligned["lev"].pct_change()
    base_ret = aligned["base"].pct_change()
    deviation = lev_ret - leverage * base_ret

    fixed = lev.copy()
    for date in aligned.index[deviation.abs() > threshold]:
        idx = fixed.index.get_loc(date)
        if idx == 0:
            continue
        prior_price = fixed.iloc[idx - 1]
        actual_price = fixed.iloc[idx]
        expected_price = prior_price * (1 + leverage * base_ret.loc[date])
        correction_factor = actual_price / expected_price
        fixed.iloc[:idx] *= correction_factor

    return fixed


def load_prices(config: BacktestConfig) -> pd.DataFrame:
    """Load adjusted close prices for both tickers, aligned on common trading days."""
    lev_ticker = get_ticker(config.lev_ticker)
    base_ticker = get_ticker(config.base_ticker)

    lev = _download_close(lev_ticker.yf_symbol, config.start_date, config.end_date)
    base = _download_close(base_ticker.yf_symbol, config.start_date, config.end_date)
    lev = _fix_leverage_discontinuities(lev, base, lev_ticker.leverage)

    prices = pd.concat([lev, base], axis=1, join="inner")
    prices.columns = ["lev", "base"]
    return prices.sort_index().dropna()


def load_single_price(symbol: str, start: str, end: str) -> pd.Series:
    """Load adjusted close prices for one ticker.

    If the ticker is leveraged (has a registered base), its base series is also
    downloaded and used to correct undocumented price discontinuities; a base
    ticker has no such artifact to correct and is returned as-is.
    """
    ticker = get_ticker(symbol)
    series = _download_close(ticker.yf_symbol, start, end)

    if ticker.base_symbol is not None:
        base = _download_close(get_ticker(ticker.base_symbol).yf_symbol, start, end)
        series = _fix_leverage_discontinuities(series, base, ticker.leverage)

    return series.sort_index().dropna()
