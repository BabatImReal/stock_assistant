"""Occurrence rates and distributions for the feature measures (§4.1, §5.1-5.2).

Not a statistic about the market yet -- hit-rate-against-base-rate needs the
return generator, which is the backtest step (open-questions B2). This answers
the question that comes first: do these measures fire at a believable rate, and
how much of the data does each one decline to score?

The NaN share matters as much as the values. A measure that is NaN on a third
of its rows is not broken; it is telling us how much of the history sits behind
a trading gap, an excluded window or an unadjustable volume span.

Run:  uv run python scripts/report_volume_features.py [n_symbols]
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402
from vnstock_research.features import bars, compute, load_config, market  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    cfg = load_config()
    say(f"Feature measures (doc §4.1, §5.1-5.2)   {datetime.now():%Y-%m-%d %H:%M}")
    say(f"enabled measures: {', '.join(k for k, v in cfg.items() if v['enabled'])}")
    say("")

    with db.connect() as conn:
        build = bars.current_build(conn)
        symbols = bars.liquid_symbols(conn, limit=n)
        say(f"build {build}; {len(symbols)} liquid symbols, 2012-01-01 onward")

        index = market.load_default(conn)
        missing = market.missing_sessions(conn)
        say(f"index frame: {len(index):,} sessions; "
            f"sessions the market traded and the index lacks: {missing}")

        frames, fs = [], None
        for symbol, frame in bars.load_many(conn, symbols):
            if frame.empty:
                continue
            values, fs = compute(frame, market=index)
            values["symbol"] = symbol
            frames.append(values)

    if not frames:
        say("no data")
        return
    df = pd.concat(frames, ignore_index=True)
    say(f"stock-days scored: {len(df):,}")
    say(f"feature set fingerprint: {fs.fingerprint}")
    say("")

    say(f"{'measure':<26}{'scored':>10}{'NaN':>8}{'fires':>9}{'rate':>8}"
        f"{'median':>12}{'p95':>12}")
    for name in fs.measures:
        col = df[name]
        scored = int(col.notna().sum())
        nan_share = 1 - scored / len(col)
        kind = "boolean" if set(col.dropna().unique()) <= {0.0, 1.0} else "numeric"
        if kind == "boolean":
            fires = int(col.fillna(0).sum())
            rate = fires / scored if scored else 0.0
            say(f"{name:<26}{scored:>10,}{nan_share:>7.1%}{fires:>9,}{rate:>8.2%}"
                f"{'-':>12}{'-':>12}")
        else:
            say(f"{name:<26}{scored:>10,}{nan_share:>7.1%}{'-':>9}{'-':>8}"
                f"{col.median():>12,.3f}{col.quantile(0.95):>12,.3f}")

    say("")
    say("why rows are unscored (the NaN share above):")
    say("  a window spanning a trading gap, touching an excluded window, or")
    say("  covering a backfilled span where volume cannot be adjusted -- plus")
    say("  the warm-up rows at the start of each symbol's history.")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"features-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
