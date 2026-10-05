"""The daily brief's wording rule and scorecard. Synthetic inputs only."""

import numpy as np
import pandas as pd

from vnstock_research.report import brief


def test_a_signal_that_lost_money_per_signal_day_is_weak_whatever_the_forward_record():
    assert brief.strength(-0.0043, 100, 5.0, 30) == "WEAK"
    assert brief.strength(float("nan"), 100, 5.0, 30) == "WEAK"


def test_a_positive_holdout_without_a_forward_record_is_unproven_not_strong():
    assert brief.strength(0.0074, 29, 3.0, 30) == "UNPROVEN"


def test_strong_needs_both_the_holdout_and_a_positive_forward_record():
    assert brief.strength(0.0074, 30, 0.2, 30) == "STRONG"
    assert brief.strength(0.0074, 30, -0.2, 30) == "WEAK"


def test_only_a_strong_signal_breaks_the_nothing_strong_headline():
    for label in (None, "WEAK", "UNPROVEN"):
        assert "NOTHING STRONG" in brief.headline("2026-10-06", label, "TAL")
    assert "NOTHING STRONG" not in brief.headline("2026-10-06", "STRONG", "TAL")


def _outcomes(rows):
    return pd.DataFrame(rows, columns=["day", "forward", "symbol", "status", "net"])


def test_the_scorecard_keeps_the_sign_and_ignores_pre_freeze_days():
    o = _outcomes(
        [
            ("2026-09-18", False, "FPT", "scored", -0.0459),
            ("2026-09-28", True, "AAA", "scored", -0.02),
            ("2026-10-02", True, "VNM", "scored", 0.01),
            ("2026-10-05", True, "TAL", "pending", np.nan),
        ]
    )
    text = "\n".join(brief.scorecard_lines(o))
    assert "FPT" not in text
    assert "AAA: net -2.00%" in text and "VNM: net +1.00%" in text
    assert "TAL: pending" in text
    assert "2 scored, -0.010 stakes" in text


def test_an_empty_forward_record_says_so():
    assert "no forward proposals yet" in brief.scorecard_lines(_outcomes([]))[0]
