"""The dated market-holiday list (config/rules/holidays.yaml) and its checks.

The list is data a human maintains once a year, so the cheapest guard is on the
file itself: a weekend date or a date filed under the wrong year is a typo that
would silently weaken the check.
"""

from vnstock_research.data import checks


def test_every_listed_holiday_is_a_weekday_in_its_own_year():
    days = checks.holiday_list()
    assert len(days) >= 121
    for year, day in days:
        assert day.weekday() < 5, f"{day} is a weekend; the weekend check covers it"
        assert day.year == year, f"{day} is filed under {year}"
    assert len({d for _, d in days}) == len(days), "a date is listed twice"


def test_statutory_anchors_are_present():
    # Spot-check one date of each kind, so a regenerated file cannot drop one.
    listed = {d.isoformat() for _, d in checks.holiday_list()}
    for day in (
        "2024-02-12",  # Tet lunar 1/3
        "2025-04-07",  # Hung Kings, lunar 10/3
        "2019-04-15",  # in lieu of Hung Kings on a Sunday
        "2025-05-02",
    ):  # the 2025 swap day
        assert day in listed
