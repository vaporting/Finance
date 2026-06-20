"""Performance metrics for a value or price series."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass
class PerformanceStats:
    total_return: float
    cagr: float
    max_drawdown: float
    annual_volatility: float
    final_value: float


def compute_stats(series: pd.Series) -> PerformanceStats:
    """Compute performance stats for a value or price series indexed by date."""
    series = series.dropna()
    start_value = series.iloc[0]
    end_value = series.iloc[-1]

    total_return = end_value / start_value - 1

    years = (series.index[-1] - series.index[0]).days / 365.25
    cagr = (end_value / start_value) ** (1 / years) - 1 if years > 0 else float("nan")

    running_max = series.cummax()
    drawdown = series / running_max - 1
    max_drawdown = drawdown.min()

    daily_returns = series.pct_change().dropna()
    annual_volatility = daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)

    return PerformanceStats(
        total_return=total_return,
        cagr=cagr,
        max_drawdown=max_drawdown,
        annual_volatility=annual_volatility,
        final_value=end_value,
    )


ROW_LABELS = {
    "en": ["Total Return", "CAGR", "Max Drawdown", "Annual Volatility", "Final Value"],
    "zh": ["總報酬率", "年化報酬率", "最大回撤", "年化波動率", "最終價值"],
}


def format_stats_table(stats: dict[str, PerformanceStats], lang: str = "en") -> str:
    """Render a side-by-side comparison table of named performance stats."""
    names = list(stats.keys())
    labels = ROW_LABELS[lang]
    formatters = [
        lambda s: f"{s.total_return:.2%}",
        lambda s: f"{s.cagr:.2%}",
        lambda s: f"{s.max_drawdown:.2%}",
        lambda s: f"{s.annual_volatility:.2%}",
        lambda s: f"{s.final_value:,.0f}",
    ]
    rows = list(zip(labels, formatters))

    col_width = max(12, max(len(n) for n in names) + 2)
    label_width = 18

    header = " " * label_width + "".join(f"{n:>{col_width}}" for n in names)
    lines = [header]
    for label, fmt in rows:
        line = f"{label:<{label_width}}" + "".join(f"{fmt(stats[n]):>{col_width}}" for n in names)
        lines.append(line)
    return "\n".join(lines)
