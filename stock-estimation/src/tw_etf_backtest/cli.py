"""CLI entry point: backtest comparison and drawdown-events analysis, as separate subcommands."""

import argparse
from pathlib import Path

from .config import BacktestConfig
from .data import load_prices
from .drawdown_events import compute_drawdown_events, format_drawdown_events_table
from .metrics import compute_stats, format_stats_table
from .plot import plot_asset_returns, plot_portfolio_value
from .strategy import run_portfolio_a, run_portfolio_b

# Project root is three levels up from this file (src/tw_etf_backtest/cli.py).
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

# Print-output text in English and Traditional Chinese, selected via --lang.
MESSAGES = {
    "en": {
        "loading": "Loading prices for {lev} and {base} from {start} to {end}...",
        "loaded": "Loaded {n} trading days.",
        "portfolio_header": "\n=== Portfolio Performance (equal starting capital) ===",
        "portfolio_a": "Portfolio A: {lev} {equity_pct:.0%} + cash {cash_pct:.0%}, dip-buy ladder at drawdowns {thresholds}",
        "portfolio_b": "Portfolio B: {base} 100%, buy-and-hold",
        "asset_header": "\n=== Underlying Asset Performance ===",
        "dip_header": "\nDip-buy triggers for Portfolio A: {n}",
        "dip_row": "  {date}  price={price:.2f}  drawdown={drawdown:.1%}  invested={amount:,.0f}",
        "charts_saved": "\nCharts saved to {dir}/",
        "drawdown_events_header": "\n=== Drawdown Events for {lev} ===",
    },
    "zh": {
        "loading": "正在下載 {lev} 與 {base} 的價格資料,期間 {start} 至 {end}...",
        "loaded": "已載入 {n} 個交易日的資料。",
        "portfolio_header": "\n=== 組合績效比較(相同起始資金) ===",
        "portfolio_a": "組合 A:{lev} {equity_pct:.0%} + 現金 {cash_pct:.0%},回撤加碼門檻 {thresholds}",
        "portfolio_b": "組合 B:{base} 100%,買進並持有",
        "asset_header": "\n=== 標的本身績效表現 ===",
        "dip_header": "\n組合 A 加碼觸發次數:{n}",
        "dip_row": "  {date}  價格={price:.2f}  回撤={drawdown:.1%}  投入金額={amount:,.0f}",
        "charts_saved": "\n圖表已存至 {dir}/",
        "drawdown_events_header": "\n=== {lev} 回撤事件 ===",
    },
}


def _build_common_parser() -> argparse.ArgumentParser:
    """Flags shared by both subcommands: ticker selection, date range, ladder thresholds, language."""
    defaults = BacktestConfig()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--lang", choices=["en", "zh"], default="en",
        help="Language for print output: English (en) or Traditional Chinese (zh)",
    )
    common.add_argument("--lev-ticker", default=defaults.lev_ticker)
    common.add_argument("--base-ticker", default=defaults.base_ticker)
    common.add_argument("--start-date", default=defaults.start_date)
    common.add_argument("--end-date", default=defaults.end_date)
    common.add_argument(
        "--dip-thresholds", type=float, nargs="+", default=defaults.dip_thresholds,
        help="Drawdown ladder thresholds from the running high, e.g. 0.15 0.25 0.40",
    )
    return common


def parse_args() -> argparse.Namespace:
    defaults = BacktestConfig()
    common = _build_common_parser()
    parser = argparse.ArgumentParser(description="Compare 00631L+cash vs 0050 buy-and-hold")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser(
        "backtest", parents=[common],
        help="Run the two-portfolio backtest, print performance tables, and save two charts",
    )
    backtest_parser.add_argument("--total-capital", type=float, default=defaults.total_capital)
    backtest_parser.add_argument(
        "--equity-pct", type=float, default=defaults.equity_pct,
        help="Fraction of capital allocated to the leveraged ETF in Portfolio A",
    )
    backtest_parser.add_argument(
        "--tranche-fraction", type=float, default=defaults.tranche_fraction,
        help="Fraction of initial cash deployed per triggered dip-buy tranche",
    )
    backtest_parser.add_argument(
        "--tranche-amount", type=float, default=defaults.tranche_amount,
        help="Fixed TWD amount deployed per triggered dip-buy tranche (overrides --tranche-fraction)",
    )
    backtest_parser.add_argument("--cash-yield-annual", type=float, default=defaults.cash_yield_annual)
    backtest_parser.add_argument(
        "--rebalance", action="store_true", default=defaults.rebalance_enabled,
        help="Enable periodic rebalancing of Portfolio A back to --rebalance-target",
    )
    backtest_parser.add_argument(
        "--rebalance-freq", default=defaults.rebalance_freq,
        help="Pandas offset alias for rebalance frequency, e.g. 'Q' or 'Y'",
    )
    backtest_parser.add_argument("--rebalance-target", type=float, default=defaults.rebalance_target)

    subparsers.add_parser(
        "drawdown-events", parents=[common],
        help="Print a table of historical drawdown threshold crossings for the leveraged ETF",
    )

    return parser.parse_args()


def run_backtest(args: argparse.Namespace) -> None:
    """Run the two-portfolio backtest: print performance tables and save two charts."""
    lang = args.lang
    msg = MESSAGES[lang]

    config = BacktestConfig(
        total_capital=args.total_capital,
        lev_ticker=args.lev_ticker,
        base_ticker=args.base_ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        equity_pct=args.equity_pct,
        cash_pct=1 - args.equity_pct,
        dip_thresholds=list(args.dip_thresholds),
        tranche_fraction=args.tranche_fraction,
        tranche_amount=args.tranche_amount,
        cash_yield_annual=args.cash_yield_annual,
        rebalance_enabled=args.rebalance,
        rebalance_freq=args.rebalance_freq,
        rebalance_target=args.rebalance_target,
    )

    print(msg["loading"].format(
        lev=config.lev_ticker, base=config.base_ticker,
        start=config.start_date, end=config.end_date,
    ))
    prices = load_prices(config)
    print(msg["loaded"].format(n=len(prices)))

    result_a = run_portfolio_a(prices, config)
    result_b = run_portfolio_b(prices, config)

    portfolio_names = {"en": ("Portfolio A", "Portfolio B"), "zh": ("組合 A", "組合 B")}[lang]
    portfolio_stats = {
        portfolio_names[0]: compute_stats(result_a.total_value),
        portfolio_names[1]: compute_stats(result_b.total_value),
    }
    asset_stats = {
        config.lev_ticker: compute_stats(prices["lev"]),
        config.base_ticker: compute_stats(prices["base"]),
    }

    print(msg["portfolio_header"])
    print(msg["portfolio_a"].format(
        lev=config.lev_ticker, equity_pct=config.equity_pct,
        cash_pct=config.cash_pct, thresholds=config.dip_thresholds,
    ))
    print(msg["portfolio_b"].format(base=config.base_ticker))
    print(format_stats_table(portfolio_stats, lang=lang))

    print(msg["asset_header"])
    print(format_stats_table(asset_stats, lang=lang))

    dip_trades = [t for t in result_a.trades if t.kind == "dip_buy"]
    print(msg["dip_header"].format(n=len(dip_trades)))
    for t in dip_trades:
        print(msg["dip_row"].format(
            date=t.date.date(), price=t.price, drawdown=t.drawdown, amount=t.amount,
        ))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_portfolio_value(result_a, result_b, config, OUTPUT_DIR / "portfolio_value.png")
    plot_asset_returns(prices, config, OUTPUT_DIR / "asset_return.png")
    print(msg["charts_saved"].format(dir=OUTPUT_DIR))


def run_drawdown_events(args: argparse.Namespace) -> None:
    """Print a standalone table of historical drawdown threshold crossings. No charts, no portfolio simulation."""
    lang = args.lang
    msg = MESSAGES[lang]

    # The leverage-discontinuity fix in load_prices needs the base ticker, so a
    # full BacktestConfig is built even though portfolio-specific fields are unused here.
    config = BacktestConfig(
        lev_ticker=args.lev_ticker,
        base_ticker=args.base_ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        dip_thresholds=list(args.dip_thresholds),
    )

    print(msg["loading"].format(
        lev=config.lev_ticker, base=config.base_ticker,
        start=config.start_date, end=config.end_date,
    ))
    prices = load_prices(config)
    print(msg["loaded"].format(n=len(prices)))

    events = compute_drawdown_events(prices["lev"], config.dip_thresholds)
    print(msg["drawdown_events_header"].format(lev=config.lev_ticker))
    print(format_drawdown_events_table(events, config.dip_thresholds, lang=lang))


def main() -> None:
    args = parse_args()
    if args.command == "backtest":
        run_backtest(args)
    elif args.command == "drawdown-events":
        run_drawdown_events(args)


if __name__ == "__main__":
    main()
