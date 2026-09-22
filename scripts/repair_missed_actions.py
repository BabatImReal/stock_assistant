"""Infer the factor for corporate actions CafeF missed; exclude only what we cannot.

A price that gaps beyond the daily limit with no change in the adjustment factor
means either a real move or an unadjusted corporate action. Where the second
source disagrees with us, the event was real and CafeF missed it -- and our
adjusted series then contains a step that never happened in the market.

Excluding those windows works but is expensive: a missed action costs roughly
67 sessions of that symbol's history. So try to repair first.

The inference, and why each half is needed:

  implied factor = (1 + our move) / (1 + reference move)

  1. ROUND RATIO. Vietnamese stock dividends and splits come in round rates --
     10%, 20%, 50%, 1:1. If the implied factor lands within ~1% of 1/(1+r) for
     one of those, that is a real corporate action rather than a coincidence.
  2. VOLUME. A stock dividend multiplies the share count by (1+r), so the same
     money changing hands becomes (1+r) times as many shares. If the price
     ratio says a 1:1 bonus and the traded volume did not respond at all, the
     round number was a coincidence.

     NOTE ON THE VOLUME TEST: a single day's volume is noise -- a quiet day
     after a split can easily be smaller than a busy day before it. This
     compares the MEDIAN over 20 sessions each side, which is the same test with
     the noise taken out, and the band is deliberately loose (half to double the
     expected ratio) because it exists to reject the case where volume moved the
     WRONG way, not to measure the ratio precisely. It only really discriminates
     for large ratios; for a 10% dividend it is close to no evidence, which the
     report says per case.

Repairing means writing a NEW BUILD. A changed factor on a past day is a
restatement, and the re-adjustment policy says restatements make a new build
rather than editing history. bar_raw is never touched.

Run:  uv run python scripts/repair_missed_actions.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import checks, db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
UNIVERSE = REPO / "config" / "rules" / "universe.yaml"
PATTERNS = REPO / "config" / "rules" / "patterns.yaml"
DELAY = 1.3

# Stock-dividend and split rates seen in this market. The factor is 1/(1+rate).
ROUND_RATES = [
    0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 1 / 3, 0.40,
    0.50, 0.60, 2 / 3, 0.75, 1.00, 1.50, 2.00,
]
RATIO_TOLERANCE = 0.01  # "within ~1% of a round ratio"
VOLUME_BAND = (0.5, 2.0)  # observed / expected volume ratio must land in here
VOLUME_WINDOW = 20  # sessions each side, median

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def exclusion_window() -> tuple[int, int]:
    """(sessions before the event, sessions after) that research must skip.

    A feature computed on day D with lookback L is wrong if the bad day E falls
    in [D-L, D], i.e. for D in [E, E+L]. A forward return of F days from day D
    is wrong if E falls in [D+1, D+F], i.e. for D in [E-F, E-1]. So the whole
    contaminated span is [E-F, E+L].

    L has a floor of 60 sessions. config/rules/patterns.yaml currently tops out
    at 20, but the context measures in the doc -- the 50-day moving average
    (§5.1) and the 60-day support/resistance lookback (§5.2) -- are not in
    config yet, so 20 would be a promise the feature set does not keep.
    """
    cfg = yaml.safe_load(PATTERNS.read_text())
    lookbacks = [60]
    forwards = [1]

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, (int, float)) and "lookback" in key:
                    lookbacks.append(int(value))
                if isinstance(value, list) and key == "forward_days":
                    forwards.extend(int(v) for v in value)
                if isinstance(value, (int, float)) and key == "entry_offset_days":
                    forwards.append(int(value))
                walk(value)

    walk(cfg)
    return max(lookbacks), max(forwards) + 1


def nearest_round_factor(implied: float) -> tuple[float, float, str] | None:
    """Closest round stock-dividend factor to the implied one, if within tolerance."""
    best = None
    for rate in ROUND_RATES:
        factor = 1.0 / (1.0 + rate)
        err = abs(implied - factor) / factor
        if best is None or err < best[1]:
            best = (factor, err, f"1/(1+{rate:.4g})")
    if best and best[1] <= RATIO_TOLERANCE:
        return best
    return None


def main() -> None:
    db.load_env()
    look_back, look_fwd = exclusion_window()
    say(f"Missed-action repair   {datetime.now():%Y-%m-%d %H:%M}")
    say(f"exclusion window: {look_fwd} sessions before .. {look_back} after an event")
    say("")

    ucfg = yaml.safe_load(UNIVERSE.read_text())["liquidity"]

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT build_id FROM adjustment_build WHERE status='good' "
                "ORDER BY build_id DESC LIMIT 1"
            )
            (build,) = cur.fetchone()
            say(f"current good build: {build}")

            cur.execute(
                """
                CREATE TEMP TABLE liquid AS
                SELECT symbol FROM (
                    SELECT r.symbol, avg(r.close * r.matched_volume) v, count(*) d
                    FROM bar_raw r
                    WHERE r.trade_date >= (SELECT max(trade_date) FROM bar_raw)
                                          - make_interval(days => %s::int)
                      AND r.matched_volume > 0
                    GROUP BY 1
                ) x WHERE v >= %s AND d >= %s
                """,
                (
                    int(ucfg["lookback_days"] * 1.5),
                    ucfg["min_avg_matched_value"],
                    ucfg["min_trading_days_in_lookback"],
                ),
            )

            cur.execute(
                f"""
                WITH moves AS (
                    SELECT r.symbol, r.trade_date, r.exchange,
                           lag(r.close) OVER w AS prev_close,
                           r.close / lag(r.close) OVER w - 1 AS raw_move,
                           a.close / lag(a.close) OVER w - 1 AS adj_move,
                           lag(r.trade_date) OVER w AS prev_date,
                           f.factor, lag(f.factor) OVER w AS prev_factor,
                           row_number() OVER w AS n
                    FROM bar_raw r
                    JOIN adjustment_factor f
                      ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                     AND f.build_id = %s
                    JOIN bar_adjusted a
                      ON a.symbol = r.symbol AND a.trade_date = r.trade_date
                     AND a.build_id = %s
                    WHERE r.trade_date >= DATE '2012-01-01'
                    WINDOW w AS (PARTITION BY r.symbol ORDER BY r.trade_date)
                )
                SELECT m.symbol, m.trade_date, m.prev_close, m.adj_move,
                       ({checks.limit_sql()}) AS lim
                FROM moves m JOIN liquid l USING (symbol)
                WHERE m.raw_move IS NOT NULL AND m.prev_close >= 10
                  AND abs(m.raw_move) > ({checks.limit_sql()})
                      + ({checks.tick_sql("prev_close")}) / m.prev_close
                  AND abs(m.factor - m.prev_factor) < 0.000001
                  AND m.n > 2
                  AND m.prev_date >= m.trade_date - INTERVAL '10 days'
                ORDER BY m.symbol, m.trade_date
                """,
                (build, build),
            )
            candidates = cur.fetchall()
        say(f"candidates: {len(candidates)}")

        # --- volume around each event, from the RAW (unadjusted) series -------
        vol_ratio: dict[tuple, float] = {}
        with conn.cursor() as cur:
            for symbol, d, *_ in candidates:
                cur.execute(
                    """
                    SELECT
                      percentile_cont(0.5) WITHIN GROUP (
                        ORDER BY matched_volume) FILTER (WHERE trade_date < %s),
                      percentile_cont(0.5) WITHIN GROUP (
                        ORDER BY matched_volume) FILTER (WHERE trade_date >= %s)
                    FROM (
                        SELECT trade_date, matched_volume FROM bar_raw
                        WHERE symbol = %s
                          AND trade_date BETWEEN %s - INTERVAL '%s days'
                                             AND %s + INTERVAL '%s days'
                    ) t
                    """,
                    (d, d, symbol, d, VOLUME_WINDOW * 2, d, VOLUME_WINDOW * 2),
                )
                before, after = cur.fetchone()
                vol_ratio[(symbol, d)] = (
                    float(after) / float(before) if before and after else None
                )

        # --- the reference move ----------------------------------------------
        from vnstock import Quote

        cache: dict[tuple, pd.DataFrame] = {}
        rows = []
        for symbol, d, _prev_close, adj_move, lim in candidates:
            key = (symbol, d.year)
            if key not in cache:
                time.sleep(DELAY)
                try:
                    cache[key] = Quote(source="vci", symbol=symbol).history(
                        start=str(d - pd.Timedelta(days=25)),
                        end=str(d + pd.Timedelta(days=25)),
                        interval="1D",
                    )
                except Exception:  # noqa: BLE001
                    cache[key] = pd.DataFrame()
            ref = cache[key]
            ref_move = None
            if not ref.empty:
                r = ref.copy()
                r["d"] = pd.to_datetime(r["time"]).dt.date
                r = r.sort_values("d").reset_index(drop=True)
                idx = r.index[r["d"] == d]
                if len(idx) and idx[0] > 0:
                    i = idx[0]
                    ref_move = float(r.loc[i, "close"] / r.loc[i - 1, "close"] - 1)
            rows.append(
                {
                    "symbol": symbol,
                    "date": d,
                    "adj_move": float(adj_move),
                    "ref_move": ref_move,
                    "limit": float(lim),
                    "vol_ratio": vol_ratio.get((symbol, d)),
                }
            )

        df = pd.DataFrame(rows)
        # Real moves: the reference gapped too, so nothing was missed.
        real = df[
            df["ref_move"].notna()
            & (df["ref_move"].abs() > df["limit"] + 0.005)
        ]
        suspect = df.drop(real.index)
        say(f"  real moves (both sources gap): {len(real)}")
        say(f"  suspect (to infer or exclude): {len(suspect)}")
        say(f"    of which no reference bar:   {suspect['ref_move'].isna().sum()}")
        say("")

        # --- infer -------------------------------------------------------------
        repaired, failed = [], []
        for r in suspect.itertuples():
            # With no reference we assume the true move was ~0, which is what a
            # pure adjustment step looks like.
            implied = (1 + r.adj_move) / (1 + (r.ref_move or 0.0))
            hit = nearest_round_factor(implied)
            expected_vol = 1 / hit[0] if hit else None
            vol_ok = (
                hit is not None
                and r.vol_ratio is not None
                and VOLUME_BAND[0] <= r.vol_ratio / expected_vol <= VOLUME_BAND[1]
            )
            record = {
                "symbol": r.symbol, "date": r.date, "implied": implied,
                "round_factor": hit[0] if hit else None,
                "round_label": hit[2] if hit else None,
                "ratio_err": hit[1] if hit else None,
                "vol_ratio": r.vol_ratio, "expected_vol": expected_vol,
                "had_reference": r.ref_move is not None,
            }
            (repaired if (hit and vol_ok) else failed).append(record)

        say(f"REPAIRABLE (round ratio + volume agrees): {len(repaired)}")
        say(f"NOT REPAIRABLE (will be excluded):        {len(failed)}")
        say("")

        if repaired:
            say("repaired events:")
            say(f"  {'sym':<5}{'date':<12}{'implied':>9}{'round':>16}"
                f"{'vol obs/exp':>13}{'ref?':>6}")
            for r in sorted(repaired, key=lambda x: x["date"])[:15]:
                say(f"  {r['symbol']:<5}{str(r['date']):<12}{r['implied']:>9.4f}"
                    f"{r['round_label']:>16}"
                    f"{r['vol_ratio'] / r['expected_vol']:>13.2f}"
                    f"{'yes' if r['had_reference'] else 'no':>6}")

        # --- write a new build with the inferred factors ------------------------
        if repaired:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO adjustment_build (reason, status)
                    VALUES (%s, 'building') RETURNING build_id
                    """,
                    (f"inferred factors for {len(repaired)} missed corporate actions",),
                )
                (new_build,) = cur.fetchone()

                # Copy the current factors forward, then apply each inferred
                # action to every day BEFORE its event -- which is what an
                # adjustment is: everything earlier is restated.
                cur.execute(
                    """
                    INSERT INTO adjustment_factor
                        (symbol, trade_date, build_id, factor, source)
                    SELECT symbol, trade_date, %s, factor, source
                    FROM adjustment_factor WHERE build_id = %s
                    """,
                    (new_build, build),
                )
                for r in repaired:
                    cur.execute(
                        """
                        UPDATE adjustment_factor
                        SET factor = factor * %s, source = 'inferred'
                        WHERE build_id = %s AND symbol = %s AND trade_date < %s
                        """,
                        (r["round_factor"], new_build, r["symbol"], r["date"]),
                    )
                cur.execute(
                    """
                    INSERT INTO bar_adjusted (symbol, trade_date, build_id,
                        open, high, low, close, matched_volume, volume_is_adjustable)
                    SELECT r.symbol, r.trade_date, %s,
                           r.open * f.factor, r.high * f.factor,
                           r.low * f.factor, r.close * f.factor,
                           r.matched_volume / f.factor,
                           NOT r.is_adjusted_source
                    FROM bar_raw r
                    JOIN adjustment_factor f
                      ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                     AND f.build_id = %s
                    """,
                    (new_build, new_build),
                )
            conn.commit()
            say("")
            say(f"new build {new_build} written with inferred factors")

            # --- re-check: did the repair actually close the gap? --------------
            with conn.cursor() as cur:
                fixed = 0
                for r in repaired:
                    cur.execute(
                        """
                        WITH two AS (
                            SELECT close, lag(close) OVER (ORDER BY trade_date) AS prev
                            FROM bar_adjusted
                            WHERE build_id = %s AND symbol = %s
                              AND trade_date <= %s
                            ORDER BY trade_date DESC LIMIT 2
                        )
                        SELECT close / prev - 1 FROM two WHERE prev IS NOT NULL
                        """,
                        (new_build, r["symbol"], r["date"]),
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None and abs(float(row[0])) <= 0.16:
                        fixed += 1
                say(f"re-check: {fixed}/{len(repaired)} events now move within limits")
        else:
            new_build = build

        # --- exclude what could not be repaired ---------------------------------
        if failed:
            with conn.cursor() as cur:
                for r in failed:
                    cur.execute(
                        """
                        INSERT INTO excluded_window
                            (symbol, valid_from, valid_to, reason, event_date, detail)
                        SELECT %s,
                               (SELECT min(trade_date) FROM (
                                  SELECT trade_date FROM bar_raw WHERE symbol = %s
                                    AND trade_date <= %s
                                  ORDER BY trade_date DESC LIMIT %s) a),
                               (SELECT max(trade_date) FROM (
                                  SELECT trade_date FROM bar_raw WHERE symbol = %s
                                    AND trade_date >= %s
                                  ORDER BY trade_date LIMIT %s) b),
                               'unexplained corporate action', %s, %s::jsonb
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            r["symbol"], r["symbol"], r["date"], look_fwd,
                            r["symbol"], r["date"], look_back, r["date"],
                            # NaN is not valid JSON, and an implied factor can
                            # be NaN when the reference move is exactly -100%.
                            json.dumps(
                                {
                                    "implied": None
                                    if pd.isna(r["implied"])
                                    else round(r["implied"], 6),
                                    "had_reference": r["had_reference"],
                                }
                            ),
                        ),
                    )
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), sum(valid_to - valid_from + 1) "
                    "FROM excluded_window"
                )
                n_win, n_days = cur.fetchone()
            say("")
            say(f"excluded {n_win} windows covering ~{n_days:,} calendar days")

    REPORTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(repaired).to_csv(REPORTS / "repaired-actions.csv", index=False)
    pd.DataFrame(failed).to_csv(REPORTS / "unexplained-actions.csv", index=False)
    path = REPORTS / f"missed-action-repair-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
