# Stock Analysis — base/leveraged ETF backtest & drawdown analysis

Backtesting and drawdown analysis for **base/leveraged ETF pairs**, across markets. Tickers come from a small built-in registry (see [`list-tickers`](#available-tickers)), so the same tooling works for Taiwan and US pairs without code changes.

Three subcommands, each doing one thing:

- **`backtest`** — compares two equal-capital portfolios over the same historical period (needs **both** a base and a leveraged ticker):
  - **Portfolio A** — the leveraged ETF at `equity_pct` of capital, the rest held as cash. Cash is deployed in tranches whenever the leveraged ETF drops past a drawdown threshold from its running high (a "buy the dip" ladder).
  - **Portfolio B** — the base ETF at 100% of capital, buy-and-hold.

  Also charts the standalone cumulative return of the two ETFs to highlight how daily 2x leverage amplifies gains and losses.
- **`drawdown-events`** — prints a table of every historical drawdown threshold crossing for a **single** ticker (independent of cash/portfolio simulation), with the interval between events and a count/avg-interval summary per severity bucket.
- **`list-tickers`** — prints the available tickers in the registry.

## Available tickers

```bash
uv run stock-analysis list-tickers
```

| Symbol | Name | Market | Currency | Leverage | Base |
|---|---|---|---|---|---|
| `0050` | Yuanta Taiwan 50 | TW | TWD | 1x | – |
| `00631L` | Yuanta Daily Taiwan 50 Bull 2X | TW | TWD | 2x | `0050` |
| `QQQ` | Invesco QQQ Trust (Nasdaq-100) | US | USD | 1x | – |
| `QLD` | ProShares Ultra QQQ (2x Nasdaq-100) | US | USD | 2x | `QQQ` |

Tickers are selected by these short symbols (case-insensitive); the registry maps each to its yfinance symbol, market, currency, daily-leverage factor, and — for a leveraged ETF — the base ticker used to correct its price history. New tickers are added in [`src/stock_analysis/tickers.py`](src/stock_analysis/tickers.py).

## Project layout

```
stock-estimation/
├── pyproject.toml
├── uv.lock
├── src/
│   └── stock_analysis/
│       ├── tickers.py           # ticker registry + lookup helpers
│       ├── config.py            # BacktestConfig dataclass (all tunable parameters)
│       ├── data.py              # yfinance download + CSV caching
│       ├── strategy.py          # portfolio backtest engine
│       ├── drawdown_events.py   # standalone drawdown-event analysis
│       ├── metrics.py           # performance stats
│       ├── plot.py              # charts
│       └── cli.py               # argparse subcommands, entry point
├── data/                        # cached price CSVs (gitignored)
└── output/                      # generated chart PNGs (gitignored)
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs the project (editable) and creates the `stock-analysis` command.

## Quick start

```bash
uv run stock-analysis list-tickers
uv run stock-analysis backtest
uv run stock-analysis drawdown-events
```

`backtest` will:
1. Download (and cache) daily prices for the chosen leveraged + base tickers from yfinance.
2. Run both portfolio simulations and print a performance comparison table.
3. Save two charts to `output/`:
   - `portfolio_value.png` — Portfolio A vs Portfolio B value over time, with dip-buy triggers marked.
   - `asset_return.png` — cumulative return of the leveraged ETF vs the base ETF.

`drawdown-events` will:
1. Download (and cache) daily prices for `--ticker`. If it is a leveraged ticker, its base pair is also downloaded to correct a data quality issue (see [Data source and caching](#data-source-and-caching)); a base ticker needs nothing else.
2. Print a table of every drawdown-ladder threshold crossing, plus the deepest-trough event for any crash that exceeded the largest threshold.
3. Print a count + average-interval summary per bucket. No charts are produced.

## CLI parameters

All parameters default to the values in [`src/stock_analysis/config.py`](src/stock_analysis/config.py) (`BacktestConfig`).

### Shared by `backtest` and `drawdown-events`

| Flag | Default | Meaning |
|---|---|---|
| `--lang` | `en` | Language for printed output: `en` (English) or `zh` (Traditional Chinese) |
| `--start-date` | see `config.py` | Analysis start date |
| `--end-date` | see `config.py` | Analysis end date |
| `--dip-thresholds` | `0.15 0.25 0.40` | Drawdown ladder thresholds from the running high; each fires once per high-watermark cycle |

### `backtest` only

| Flag | Default | Meaning |
|---|---|---|
| `--lev-ticker` | `00631L` | Leveraged ETF held in Portfolio A (registry symbol) |
| `--base-ticker` | `0050` | Base ETF for Portfolio B, and the reference used to correct the leveraged ticker's history (registry symbol) |
| `--total-capital` | `1000000` | Starting capital shared by both portfolios (in the market's currency) |
| `--equity-pct` | `0.70` | Fraction of capital allocated to the leveraged ETF in Portfolio A (remainder is cash) |
| `--tranche-fraction` | `0.3333` | Fraction of the *initial* cash allocation deployed per triggered tranche. Ignored if `--tranche-amount` is set |
| `--tranche-amount` | `50000` | Fixed cash amount deployed per triggered tranche (capped at remaining cash). Overrides `--tranche-fraction`. To use fraction-based sizing instead, set `tranche_amount=None` in `config.py` |
| `--cash-yield-annual` | `0.01` | Annual interest rate credited on idle cash |
| `--rebalance` | off | Enable periodic rebalancing of Portfolio A back to `--rebalance-target` |
| `--rebalance-freq` | `Q` | Rebalance frequency (pandas offset alias, e.g. `Q` quarterly, `Y` yearly) |
| `--rebalance-target` | `0.70` | Target equity weight when rebalancing |

### `drawdown-events` only

| Flag | Default | Meaning |
|---|---|---|
| `--ticker` | `00631L` | Single ticker to analyze (registry symbol). A leveraged ticker auto-loads its base for discontinuity correction; a base ticker is analyzed on its own |

### `list-tickers`

| Flag | Default | Meaning |
|---|---|---|
| `--lang` | `en` | Language for the table headers |

Example — US pair, more aggressive dip-buying, with yearly rebalancing:

```bash
uv run stock-analysis backtest --base-ticker QQQ --lev-ticker QLD --equity-pct 0.5 --dip-thresholds 0.05 0.10 0.15 --rebalance --rebalance-freq Y
```

Example — drawdown events for the base ETF, with a custom ladder, in Chinese:

```bash
uv run stock-analysis drawdown-events --ticker 0050 --dip-thresholds 0.1 0.2 0.3 --lang zh
```

## Strategy logic (`backtest`)

- **Drawdown ladder**: drawdown is measured against the highest leveraged-ETF price seen so far during the backtest (the running high watermark). Each threshold in `--dip-thresholds` fires independently and only once per cycle; hitting a new high resets all thresholds so the ladder can re-trigger on the next decline.
- **Tranche sizing**: two modes, selected by whether `--tranche-amount` is set.
  - *Fraction mode*: each trigger deploys `tranche_fraction * initial_cash` (capped at remaining cash), so with `1/3` and three thresholds, all initial cash is fully deployed if all three thresholds fire before cash runs out.
  - *Fixed-amount mode* (default): each trigger deploys a fixed `--tranche-amount` (capped at remaining cash), regardless of how much initial cash there was. Useful for modeling "always buy a fixed amount on each dip" rather than a percentage of the cash pool.
- **Rebalancing (optional)**: if enabled, at the end of each period (`--rebalance-freq`) Portfolio A is rebalanced back to `--rebalance-target` equity weight, buying with available cash or selling equity to raise cash.

## Drawdown events logic (`drawdown-events`)

- **Per-threshold events**: for each configured threshold, one event is recorded on the day drawdown first crosses below it within the current high-watermark cycle — same ladder semantics as `backtest`, but computed purely from price (no cash, so it isn't limited by whether tranches are still available).
- **Open-ended bucket (`>{max threshold}%`)**: any cycle whose deepest drawdown exceeds the largest configured threshold also gets one extra event, dated at that cycle's actual trough (lowest price), not at the day the largest threshold was first crossed — this captures how much further severe crashes went, and when they actually bottomed.
- **Interval column**: calendar days since the immediately preceding row in the table, regardless of bucket.
- **Summary**: per-bucket count and average interval (computed from consecutive occurrences of that same bucket), plus an overall total count and average interval across all events.

## Output

### `backtest`
- **Performance table** (printed to stdout): Total Return, CAGR, Max Drawdown, Annual Volatility, and Final Value, shown for both portfolios and for the two underlying tickers individually.
- **`output/portfolio_value.png`**: portfolio value over time for both portfolios (y-axis labeled in the market's currency), with red markers showing when Portfolio A's dip-buy ladder triggered.
- **`output/asset_return.png`**: cumulative return (%) of the leveraged ETF vs the base ETF from the start of the backtest, illustrating leverage amplification.

### `drawdown-events`
- **Events table** (printed to stdout): date, bucket, drawdown %, and interval since the previous event.
- **Summary** (printed to stdout): count and average interval (days) per bucket, plus an overall total.

## Data source and caching

Prices are downloaded via `yfinance` (using each ticker's registered yfinance symbol) and cached as CSV files under `data/` (keyed by symbol and date range), so repeated runs with the same parameters don't re-download.

`data.py` also detects and corrects a known data quality issue with daily-leveraged ETFs. Products like `00631L` and `QLD` occasionally undergo unit consolidations that Yahoo Finance fails to record as a stock split, leaving a single-day price "cliff" in the history that isn't a real market move. Such a cliff is detected by checking whether a day's return tracks roughly `leverage × base` same-day return (the leverage factor comes from the registry); any day where this deviation exceeds a sanity threshold is treated as a discontinuity, and all prior history is automatically rescaled to splice the series back together.

This is **why a leveraged ticker needs its base pair**: the correction uses the base as a reference series. `backtest` loads both anyway, and `drawdown-events` on a leveraged ticker auto-loads its registered base for this purpose. A base ETF doesn't decay or split unrecorded in this way and has no reference to correct against, so `drawdown-events` on a base ticker loads only that one series.

## Troubleshooting

- **Network/ticker errors**: an unknown `--ticker`/`--lev-ticker`/`--base-ticker` is rejected immediately with the list of available symbols. `load_prices` raises a clear error if yfinance returns no data for a known symbol — check your network connection.
- **Stale cache**: if you suspect cached data is out of date or corrupted, delete the relevant file(s) under `data/` and re-run.
- **CJK font warnings in charts**: chart labels are in Traditional Chinese, rendered with the `PingFang TC` / `Heiti TC` / `Arial Unicode MS` font fallback chain configured in `plot.py`. On a system without any of these fonts, labels will render as missing-glyph ("tofu") boxes — install a CJK-capable font or switch the fallback list to one available on your machine.
