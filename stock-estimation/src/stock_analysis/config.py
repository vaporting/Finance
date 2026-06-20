"""Backtest configuration."""

from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    # Capital shared by both portfolios at the start of the backtest.
    total_capital: float = 1_000_000.0

    # Registry ticker symbols (see tickers.py), resolved to yfinance symbols in data.py.
    lev_ticker: str = "00631L"
    base_ticker: str = "0050"

    # Backtest window. Default covers 00631L's listing date through today.
    start_date: str = "2018-01-01"
    end_date: str = "2026-06-20"

    # Portfolio A initial allocation: equity_pct into lev_ticker, rest held as cash.
    equity_pct: float = 0.70
    cash_pct: float = 0.30

    # Drawdown ladder, measured from the running high watermark of lev_ticker.
    # Each threshold fires once per new high-watermark cycle, in ascending order.
    dip_thresholds: list[float] = field(default_factory=lambda: [0.15, 0.25, 0.40])

    # Fraction of the *initial* cash allocation deployed per triggered tranche.
    # Ignored if tranche_amount is set.
    tranche_fraction: float = 1 / 3

    # Fixed cash amount (in the market's currency) deployed per triggered tranche,
    # capped at remaining cash. Takes priority over tranche_fraction when set (not None).
    tranche_amount: float | None = 50_000.0

    # Annual interest rate credited on idle cash (simple daily accrual).
    cash_yield_annual: float = 0.01

    # Optional periodic rebalancing of Portfolio A back to rebalance_target.
    rebalance_enabled: bool = False
    rebalance_freq: str = "Q"  # pandas offset alias: "Q" quarterly, "Y" yearly
    rebalance_target: float = 0.70
