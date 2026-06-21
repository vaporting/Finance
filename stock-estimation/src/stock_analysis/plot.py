"""Chart generation for portfolio comparison."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .config import BacktestConfig
from .drawdown_events import DrawdownEvent
from .strategy import BacktestResult

# Use a CJK-capable font so Traditional Chinese labels render correctly on macOS.
plt.rcParams["font.sans-serif"] = ["PingFang TC", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def plot_portfolio_value(
    result_a: BacktestResult,
    result_b: BacktestResult,
    config: BacktestConfig,
    output_path: Path,
    currency: str = "TWD",
) -> None:
    """Chart 1: portfolio value over time, with dip-buy markers on Portfolio A."""
    fig, ax = plt.subplots(figsize=(12, 6))

    label_a = f"組合 A:{config.lev_ticker} {config.equity_pct:.0%} + 現金 {config.cash_pct:.0%}"
    label_b = f"組合 B:{config.base_ticker} 100%"

    ax.plot(result_a.total_value.index, result_a.total_value.values, label=label_a, color="tab:blue")
    ax.plot(result_b.total_value.index, result_b.total_value.values, label=label_b, color="tab:orange")

    dip_trades = [t for t in result_a.trades if t.kind == "dip_buy"]
    if dip_trades:
        dates = [t.date for t in dip_trades]
        values = [result_a.total_value.loc[d] for d in dates]
        ax.scatter(dates, values, color="tab:red", zorder=5, marker="v", s=60, label="加碼觸發點")

    final_a = result_a.total_value.iloc[-1]
    final_b = result_b.total_value.iloc[-1]
    ax.set_title("組合價值比較")
    ax.set_xlabel("日期")
    ax.set_ylabel(f"組合價值 ({currency})")
    ax.legend(title=f"最終價值:A={final_a:,.0f}  B={final_b:,.0f}", loc="upper left")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


_DRAWDOWN_LABELS = {
    "en": {"title": "Drawdown Events for {ticker}", "xlabel": "Date", "ylabel": "Price", "price": "{ticker} price"},
    "zh": {"title": "{ticker} 回撤事件", "xlabel": "日期", "ylabel": "價格", "price": "{ticker} 價格"},
}


def plot_drawdown_events(
    prices: pd.Series,
    events: list[DrawdownEvent],
    ticker: str,
    output_path: Path,
    lang: str = "en",
) -> None:
    """Chart: price series with a marker and drawdown-% label at each ladder/trough event."""
    labels = _DRAWDOWN_LABELS[lang]
    # Scale width with the number of trading days so markers have room to spread out on long
    # ranges, but shrink for short ranges instead of forcing the same width as a multi-year chart.
    width = max(6, min(len(prices) * 0.15, 60))
    fig, ax = plt.subplots(figsize=(width, 6))

    ax.plot(prices.index, prices.values, color="tab:blue", label=labels["price"].format(ticker=ticker), zorder=2)

    if events:
        dates = [e.date for e in events]
        values = [prices.loc[e.date] for e in events]
        ax.scatter(dates, values, color="tab:red", zorder=5, marker="v", s=60)
        for e, value in zip(events, values):
            ax.annotate(
                f"{e.drawdown:.0%}", (e.date, value),
                textcoords="offset points", xytext=(0, -12), fontsize=8, ha="center", color="tab:red",
            )

        # One marker per distinct peak referenced by the events, with a dashed line down to
        # each trough so it's visible which high the drawdown % is measured from.
        peak_dates = sorted({e.peak_date for e in events})
        peak_values = [prices.loc[d] for d in peak_dates]
        ax.scatter(peak_dates, peak_values, color="tab:green", zorder=5, marker="^", s=60)
        for peak_date, peak_value in zip(peak_dates, peak_values):
            ax.annotate(
                "peak", (peak_date, peak_value),
                textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center", color="tab:green",
            )
        for e, value in zip(events, values):
            peak_value = prices.loc[e.peak_date]
            ax.plot([e.peak_date, e.date], [peak_value, value], color="gray", linestyle="--", linewidth=0.8, zorder=1)

    ax.set_title(labels["title"].format(ticker=ticker))
    ax.set_xlabel(labels["xlabel"])
    ax.set_ylabel(labels["ylabel"])
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()  # rotate/thin date ticks so they don't overlap on narrow charts

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_asset_returns(prices: pd.DataFrame, config: BacktestConfig, output_path: Path) -> None:
    """Chart 2: cumulative return of the leveraged ETF vs the base ETF, normalized to day 0."""
    normalized = prices / prices.iloc[0] - 1

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(normalized.index, normalized["lev"] * 100, label=f"{config.lev_ticker} 累積報酬率", color="tab:blue")
    ax.plot(normalized.index, normalized["base"] * 100, label=f"{config.base_ticker} 累積報酬率", color="tab:orange")

    ax.set_title(f"累積報酬率比較:{config.lev_ticker} vs {config.base_ticker}")
    ax.set_xlabel("日期")
    ax.set_ylabel("累積報酬率 (%)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    ax.axhline(0, color="gray", linewidth=0.8)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
