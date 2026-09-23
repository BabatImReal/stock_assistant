"""Measures computed from candles: volume, trend, and context.

Doc §4 (money flow) and §5 (context).

**Volume measures (doc §4.1)** — relative volume (today ÷ 20-day average),
sustained volume (days in the last 5–7 above 1.5×), up- vs down-volume,
price–volume agreement and divergence, traded value in VND, and volume dry-up.
Volume is a first-class signal here, not decoration: a candle shape with no
volume behind it is just a drawing.

The non-negotiable rule (doc §4.3): every money-flow measure uses **matched
volume (khớp lệnh) only**. Negotiated block deals (thỏa thuận) are pre-agreed
transfers, not market demand, and a single block can fake a day of
"accumulation". Separating the two is one of the genuine advantages this tool
has over generic charting software.

**Context measures (doc §5)** — position against the 20- and 50-day moving
averages and their slopes; support and resistance zones (a level that held at
least twice in the last 60 days); market regime from the VN-Index and breadth;
sector behaviour. Context is not optional: a hammer and a hanging man are the
same shape, and only the preceding trend tells them apart.

Everything here is a rule that can be switched on or off and measured, so that
its contribution can be tested rather than assumed.
"""

from . import breadth as _breadth  # noqa: E402,F401  (registers §5.3 breadth)
from . import market as _market  # noqa: E402,F401  (registers the §5.3 measures)
from . import trend as _trend  # noqa: E402,F401  (registers the §5.1-5.2 measures)
from . import volume as _volume  # noqa: E402,F401  (registers the §4.1 measures)
from .base import (  # noqa: E402
    MARKET_REGISTRY,
    REGISTRY,
    FeatureSet,
    Measure,
    compute,
    compute_market,
    load_config,
    market_measure,
    measure,
)

__all__ = [
    "MARKET_REGISTRY",
    "REGISTRY",
    "FeatureSet",
    "Measure",
    "compute",
    "compute_market",
    "load_config",
    "market_measure",
    "measure",
]
