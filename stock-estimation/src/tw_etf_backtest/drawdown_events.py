"""Drawdown-event analysis for a price series, independent of cash/portfolio simulation."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class DrawdownEvent:
    date: pd.Timestamp
    bucket: str  # e.g. "15%", "25%", "40%", ">40%"
    drawdown: float  # negative fraction, e.g. -0.182
    interval_days: int | None = None  # calendar days since the previous row in the full table


def compute_drawdown_events(prices: pd.Series, thresholds: list[float]) -> list[DrawdownEvent]:
    """Scan a price series for drawdown-ladder threshold crossings plus deep-crash troughs.

    Uses the same running-high-watermark / per-cycle-reset semantics as the
    dip-buy ladder in strategy.py, but is independent of cash availability.
    Each threshold fires once per cycle (the period between one new high and
    the next), on the day drawdown first crosses below it. Cycles whose
    deepest drawdown exceeds the largest configured threshold also get one
    extra event dated at the cycle's trough (its lowest price), distinct
    from the day the largest threshold was first crossed.
    """
    thresholds = sorted(thresholds)
    max_threshold = thresholds[-1]
    open_bucket = f">{max_threshold:.0%}"

    dates = prices.index
    peak = prices.iloc[0]
    triggered: set[float] = set()
    cycle_min_price = prices.iloc[0]
    cycle_min_date = dates[0]

    raw_events: list[tuple[pd.Timestamp, str, float]] = []

    def close_cycle() -> None:
        cycle_drawdown = cycle_min_price / peak - 1
        if cycle_drawdown <= -max_threshold:
            raw_events.append((cycle_min_date, open_bucket, cycle_drawdown))

    for date in dates:
        price = prices.loc[date]

        if price > peak:
            close_cycle()
            peak = price
            triggered = set()
            cycle_min_price = price
            cycle_min_date = date
        elif price < cycle_min_price:
            cycle_min_price = price
            cycle_min_date = date

        drawdown = price / peak - 1
        for thr in thresholds:
            if thr not in triggered and drawdown <= -thr:
                triggered.add(thr)
                raw_events.append((date, f"{thr:.0%}", drawdown))

    close_cycle()  # finalize whatever cycle is still in progress at the end of the series

    raw_events.sort(key=lambda e: e[0])

    events: list[DrawdownEvent] = []
    previous_date: pd.Timestamp | None = None
    for date, bucket, drawdown in raw_events:
        interval_days = (date - previous_date).days if previous_date is not None else None
        events.append(DrawdownEvent(date=date, bucket=bucket, drawdown=drawdown, interval_days=interval_days))
        previous_date = date

    return events


HEADERS = {
    "en": {
        "date": "Date", "bucket": "Bucket", "drawdown": "Drawdown", "interval": "Interval (days)",
        "summary_header": "\nSummary", "bucket_label": "Bucket", "count": "Count",
        "avg_interval": "Avg Interval (days)", "overall": "Overall",
    },
    "zh": {
        "date": "日期", "bucket": "門檻", "drawdown": "回撤幅度", "interval": "間隔天數",
        "summary_header": "\n統計摘要", "bucket_label": "門檻", "count": "次數",
        "avg_interval": "平均間隔(天)", "overall": "合計",
    },
}


def format_drawdown_events_table(events: list[DrawdownEvent], thresholds: list[float], lang: str = "en") -> str:
    """Render the drawdown-events table, plus a per-bucket and overall count/avg-interval summary."""
    h = HEADERS[lang]
    bucket_order = [f"{t:.0%}" for t in sorted(thresholds)] + [f">{max(thresholds):.0%}"]

    lines = [f"{h['date']:<12}{h['bucket']:>8}{h['drawdown']:>12}{h['interval']:>18}"]
    for e in events:
        interval_str = str(e.interval_days) if e.interval_days is not None else "-"
        lines.append(f"{str(e.date.date()):<12}{e.bucket:>8}{e.drawdown:>12.1%}{interval_str:>18}")

    bucket_dates: dict[str, list[pd.Timestamp]] = {b: [] for b in bucket_order}
    for e in events:
        bucket_dates[e.bucket].append(e.date)

    label_width = 10
    lines.append(h["summary_header"])
    lines.append(f"{h['bucket_label']:<{label_width}}{h['count']:>8}{h['avg_interval']:>22}")
    for bucket in bucket_order:
        bucket_dates_sorted = sorted(bucket_dates[bucket])
        count = len(bucket_dates_sorted)
        if count > 1:
            gaps = [(b - a).days for a, b in zip(bucket_dates_sorted, bucket_dates_sorted[1:])]
            avg_str = f"{sum(gaps) / len(gaps):.0f}"
        else:
            avg_str = "-"
        lines.append(f"{bucket:<{label_width}}{count:>8}{avg_str:>22}")

    overall_intervals = [e.interval_days for e in events if e.interval_days is not None]
    overall_avg = f"{sum(overall_intervals) / len(overall_intervals):.0f}" if overall_intervals else "-"
    lines.append(f"{h['overall']:<{label_width}}{len(events):>8}{overall_avg:>22}")

    return "\n".join(lines)
