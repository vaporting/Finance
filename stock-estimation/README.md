# 00631L vs 0050 Backtest

Two independent analyses of 00631L (Yuanta Taiwan 50 Leveraged 2x) vs 0050 (Yuanta Taiwan 50), run as separate subcommands so each invocation only does one thing:

- **`backtest`** — compares two equal-capital portfolios over the same historical period:
  - **Portfolio A** — 00631L at `equity_pct` of capital, the rest held as cash. Cash is deployed in tranches whenever 00631L drops past a drawdown threshold from its running high (a "buy the dip" ladder).
  - **Portfolio B** — 0050 at 100% of capital, buy-and-hold.

  Also charts the standalone cumulative return of 00631L vs 0050 to highlight how daily 2x leverage amplifies gains and losses.
- **`drawdown-events`** — prints a table of every historical drawdown threshold crossing for 00631L (independent of cash/portfolio simulation), with the interval between events and a count/avg-interval summary per severity bucket.

## Project layout

```
stock-estimation/
├── pyproject.toml
├── uv.lock
├── src/
│   └── tw_etf_backtest/
│       ├── config.py            # BacktestConfig dataclass (all tunable parameters)
│       ├── data.py               # yfinance download + CSV caching
│       ├── strategy.py           # portfolio backtest engine
│       ├── drawdown_events.py    # standalone drawdown-event analysis
│       ├── metrics.py            # performance stats
│       ├── plot.py               # charts
│       └── cli.py                # argparse subcommands, entry point
├── data/                         # cached price CSVs (gitignored)
└── output/                       # generated chart PNGs (gitignored)
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs the project (editable) and creates the `tw-etf-backtest` command.

## Quick start

```bash
uv run tw-etf-backtest backtest
uv run tw-etf-backtest drawdown-events
```

`backtest` will:
1. Download (and cache) daily prices for `00631L.TW` and `0050.TW` from yfinance.
2. Run both portfolio simulations and print a performance comparison table.
3. Save two charts to `output/`:
   - `portfolio_value.png` — Portfolio A vs Portfolio B value over time, with dip-buy triggers marked.
   - `asset_return.png` — cumulative return of 00631L vs 0050.

`drawdown-events` will:
1. Download (and cache) daily prices for `00631L.TW` and `0050.TW` (the base ticker is still needed to correct a data quality issue in 00631L's history — see [Data source and caching](#data-source-and-caching)).
2. Print a table of every drawdown-ladder threshold crossing, plus the deepest-trough event for any crash that exceeded the largest threshold.
3. Print a count + average-interval summary per bucket. No charts are produced.

## CLI parameters

All parameters default to the values in `src/tw_etf_backtest/config.py` (`BacktestConfig`).

### Shared by both subcommands

| Flag | Default | Meaning |
|---|---|---|
| `--lang` | `en` | Language for printed output: `en` (English) or `zh` (Traditional Chinese) |
| `--lev-ticker` | `00631L.TW` | Leveraged ETF ticker |
| `--base-ticker` | `0050.TW` | Base ETF ticker (also used to correct a data discontinuity in the leveraged ticker's history) |
| `--start-date` | see `config.py` | Analysis start date |
| `--end-date` | see `config.py` | Analysis end date |
| `--dip-thresholds` | `0.15 0.25 0.40` | Drawdown ladder thresholds from the running high; each fires once per high-watermark cycle |

### `backtest` only

| Flag | Default | Meaning |
|---|---|---|
| `--total-capital` | `1000000` | Starting capital shared by both portfolios (TWD) |
| `--equity-pct` | `0.70` | Fraction of capital allocated to the leveraged ETF in Portfolio A (remainder is cash) |
| `--tranche-fraction` | `0.3333` | Fraction of the *initial* cash allocation deployed per triggered tranche. Ignored if `--tranche-amount` is set |
| `--tranche-amount` | `50000` | Fixed TWD amount deployed per triggered tranche (capped at remaining cash). Overrides `--tranche-fraction`. To use fraction-based sizing instead, set `tranche_amount=None` in `config.py` |
| `--cash-yield-annual` | `0.01` | Annual interest rate credited on idle cash |
| `--rebalance` | off | Enable periodic rebalancing of Portfolio A back to `--rebalance-target` |
| `--rebalance-freq` | `Q` | Rebalance frequency (pandas offset alias, e.g. `Q` quarterly, `Y` yearly) |
| `--rebalance-target` | `0.70` | Target equity weight when rebalancing |

Example — more aggressive dip-buying, no leverage tilt, with yearly rebalancing:

```bash
uv run tw-etf-backtest backtest --equity-pct 0.5 --dip-thresholds 0.05 0.10 0.15 --rebalance --rebalance-freq Y
```

Example — drawdown events with a custom ladder:

```bash
uv run tw-etf-backtest drawdown-events --dip-thresholds 0.1 0.2 0.3 --lang zh
```

## Strategy logic (`backtest`)

- **Drawdown ladder**: drawdown is measured against the highest 00631L price seen so far during the backtest (the running high watermark). Each threshold in `--dip-thresholds` fires independently and only once per cycle; hitting a new high resets all thresholds so the ladder can re-trigger on the next decline.
- **Tranche sizing**: two modes, selected by whether `--tranche-amount` is set.
  - *Fraction mode*: each trigger deploys `tranche_fraction * initial_cash` (capped at remaining cash), so with `1/3` and three thresholds, all initial cash is fully deployed if all three thresholds fire before cash runs out.
  - *Fixed-amount mode* (default): each trigger deploys a fixed `--tranche-amount` TWD (capped at remaining cash), regardless of how much initial cash there was. Useful for modeling "always buy NT$50,000 on each dip" rather than a percentage of the cash pool.
- **Rebalancing (optional)**: if enabled, at the end of each period (`--rebalance-freq`) Portfolio A is rebalanced back to `--rebalance-target` equity weight, buying with available cash or selling equity to raise cash.

## Drawdown events logic (`drawdown-events`)

- **Per-threshold events**: for each configured threshold, one event is recorded on the day drawdown first crosses below it within the current high-watermark cycle — same ladder semantics as `backtest`, but computed purely from price (no cash, so it isn't limited by whether tranches are still available).
- **Open-ended bucket (`>{max threshold}%`)**: any cycle whose deepest drawdown exceeds the largest configured threshold also gets one extra event, dated at that cycle's actual trough (lowest price), not at the day the largest threshold was first crossed — this captures how much further severe crashes went, and when they actually bottomed.
- **Interval column**: calendar days since the immediately preceding row in the table, regardless of bucket.
- **Summary**: per-bucket count and average interval (computed from consecutive occurrences of that same bucket), plus an overall total count and average interval across all events.

## Output

### `backtest`
- **Performance table** (printed to stdout): Total Return, CAGR, Max Drawdown, Annual Volatility, and Final Value, shown for both portfolios and for the two underlying tickers individually.
- **`output/portfolio_value.png`**: portfolio value over time for both portfolios, with red markers showing when Portfolio A's dip-buy ladder triggered.
- **`output/asset_return.png`**: cumulative return (%) of 00631L vs 0050 from the start of the backtest, illustrating leverage amplification.

### `drawdown-events`
- **Events table** (printed to stdout): date, bucket, drawdown %, and interval since the previous event.
- **Summary** (printed to stdout): count and average interval (days) per bucket, plus an overall total.

## Data source and caching

Prices are downloaded via `yfinance` and cached as CSV files under `data/` (keyed by ticker and date range), so repeated runs with the same parameters don't re-download.

`data.py` also detects and corrects a known data quality issue: 00631L has at least one undocumented price discontinuity in Yahoo Finance's historical data (not recorded as a stock split) where the leveraged ETF's daily return is wildly inconsistent with its defining 2x relationship to 0050's same-day return. Any day where this deviation exceeds a sanity threshold is treated as a discontinuity, and all prior history is automatically rescaled to splice the series back together. This is why `--base-ticker` is required by both subcommands, even `drawdown-events` which otherwise only analyzes the leveraged ticker.

## Troubleshooting

- **Network/ticker errors**: `load_prices` raises a clear error if yfinance returns no data — check the ticker symbols and your network connection.
- **Stale cache**: if you suspect cached data is out of date or corrupted, delete the relevant file(s) under `data/` and re-run.
- **CJK font warnings in charts**: chart labels are in Traditional Chinese, rendered with the `PingFang TC` / `Heiti TC` / `Arial Unicode MS` font fallback chain configured in `plot.py`. On a system without any of these fonts, labels will render as missing-glyph ("tofu") boxes — install a CJK-capable font or switch the fallback list to one available on your machine.
