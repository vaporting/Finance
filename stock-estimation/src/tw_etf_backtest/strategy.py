"""Daily backtest engine for both portfolios."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import BacktestConfig


@dataclass
class Trade:
    date: pd.Timestamp
    kind: str  # "dip_buy", "rebalance_buy", or "rebalance_sell"
    price: float
    amount: float  # cash deployed (positive) or raised (negative)
    drawdown: float | None = None  # drawdown at trigger, for dip buys only


@dataclass
class BacktestResult:
    total_value: pd.Series
    trades: list[Trade] = field(default_factory=list)


def run_portfolio_b(prices: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
    """0050 100% buy-and-hold."""
    base = prices["base"]
    shares = config.total_capital / base.iloc[0]
    total_value = shares * base
    total_value.name = "portfolio_b"
    return BacktestResult(total_value=total_value, trades=[])


def _rebalance_trigger_dates(dates: pd.DatetimeIndex, freq: str) -> set[pd.Timestamp]:
    """Last trading day of each calendar period (e.g. quarter/year) in the index."""
    periods = np.asarray(dates.to_period(freq))
    is_period_end = np.concatenate([periods[:-1] != periods[1:], [True]])
    return set(dates[is_period_end])


def run_portfolio_a(prices: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
    """00631L equity_pct + cash, with drawdown-ladder dip buying and optional rebalancing."""
    lev = prices["lev"]
    dates = prices.index

    shares = (config.total_capital * config.equity_pct) / lev.iloc[0]
    cash = config.total_capital * config.cash_pct
    initial_cash = cash

    daily_rate = (1 + config.cash_yield_annual) ** (1 / 365) - 1

    thresholds = sorted(config.dip_thresholds)
    triggered: set[float] = set()
    peak = lev.iloc[0]

    rebalance_dates: set[pd.Timestamp] = set()
    if config.rebalance_enabled:
        rebalance_dates = _rebalance_trigger_dates(dates, config.rebalance_freq)

    trades: list[Trade] = []
    values = []

    for date in dates:
        price = lev.loc[date]

        # A new high watermark resets the drawdown ladder.
        if price > peak:
            peak = price
            triggered = set()

        drawdown = price / peak - 1

        for thr in thresholds:
            if thr in triggered:
                continue
            if drawdown <= -thr:
                triggered.add(thr)
                if config.tranche_amount is not None:
                    tranche = min(config.tranche_amount, cash)
                else:
                    tranche = min(initial_cash * config.tranche_fraction, cash)
                if tranche > 0:
                    shares += tranche / price
                    cash -= tranche
                    trades.append(
                        Trade(date=date, kind="dip_buy", price=price, amount=tranche, drawdown=drawdown)
                    )

        cash *= 1 + daily_rate

        if config.rebalance_enabled and date in rebalance_dates:
            equity_value = shares * price
            portfolio_value = equity_value + cash
            target_equity_value = portfolio_value * config.rebalance_target
            diff = target_equity_value - equity_value

            if diff > 0:
                buy = min(diff, cash)
                if buy > 0:
                    shares += buy / price
                    cash -= buy
                    trades.append(Trade(date=date, kind="rebalance_buy", price=price, amount=buy))
            elif diff < 0:
                sell_value = min(-diff, equity_value)
                sell_shares = sell_value / price
                shares -= sell_shares
                cash += sell_value
                trades.append(Trade(date=date, kind="rebalance_sell", price=price, amount=-sell_value))

        values.append(shares * price + cash)

    total_value = pd.Series(values, index=dates, name="portfolio_a")
    return BacktestResult(total_value=total_value, trades=trades)
