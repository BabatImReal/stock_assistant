"""The hint logic in scripts/investigate_index_gaps.py.

The two causes of a missing index session need opposite fixes (calendar vs
index backfill), so the hint must not point the wrong way on the clear cases.
"""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "investigate_index_gaps.py"
_spec = importlib.util.spec_from_file_location("investigate_index_gaps", _PATH)
gaps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gaps)


def test_a_handful_of_stray_rows_on_a_holiday_is_a_phantom_session():
    assert gaps.classify(3, 1_450.0, 0, 0).startswith("PHANTOM-LIKELY")


def test_rows_all_moved_onto_the_date_are_phantom_however_many():
    # 214 rows is not "few", but every one was date-shifted onto this date, so
    # the exchange never reported a session here.
    assert gaps.classify(214, 1_450.0, 214, 0).startswith("PHANTOM:")
    assert gaps.classify(40, 1_450.0, 30, 10).startswith("PHANTOM:")


def test_a_normal_session_without_an_index_row_is_an_index_gap():
    assert gaps.classify(1_430, 1_450.0, 0, 0).startswith("INDEX-GAP-LIKELY")


def test_the_middle_is_not_forced_into_either_answer():
    assert gaps.classify(700, 1_450.0, 0, 0).startswith("UNCLEAR")


def test_no_neighbours_is_unclear_not_a_crash():
    assert gaps.classify(5, None, 0, 0).startswith("UNCLEAR")
    assert gaps.classify(5, 0.0, 0, 0).startswith("UNCLEAR")
