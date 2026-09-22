# Data sources (doc §7.5)

**Nothing below has been verified against a live API yet.** Everything is read
from SSI's published docs via the knowledge document. Phase 3 (the probe) exists
precisely to replace this file's guesses with facts. Honesty rule: when the
probe disagrees with this file, the probe is right.

## SSI FastConnect Data — endpoints (from the published docs)
| Endpoint | Useful fields | Notes |
| --- | --- | --- |
| **DailyStockPrice** (main history source) | open, high, low, close, average price, **adjusted close**, reference/ceiling/floor, **matched volume & value**, **negotiated (deal) volume & value**, **foreign buy/sell volume & value**, foreign room, total traded incl. odd lots | symbol is *optional* → one request can return the whole market for a date range; paging up to 10 pages × 1,000 rows |
| DailyOhlc | OHLC + matched volume/value only | older spec limits each request to a 30-day range; lacks deal and foreign data |
| DailyIndex | VN-Index etc.: value, advances/declines, ceiling/floor counts, matched vs deal volume | gives market regime and breadth ([[context-vietnam]] §5.3) |
| SecuritiesDetails | listed shares, first/last trading date | helps with listing dates; delisted coverage unconfirmed |

Auth: AccessToken from consumer ID + secret. Credentials live in `.env` only,
never in code or memory files.

## Why DailyStockPrice is the target
It carries almost everything the research needs in one call: the **matched vs
negotiated split** ([[money-flow]] §4.3) and **foreign flow** (§4.4). It also
returns an adjusted close — the ratio *adjusted close ÷ close* can be applied
to open/high/low to adjust the whole candle for stock dividends and rights
([[funnel-and-scale]]).

## CONFIRMED
- Nothing yet. Phase 3 probe not run; Ben must register with SSI in person for
  credentials (doc §11.4 step 2).

## NOT CONFIRMED — what the probe must answer
- How far back the history actually goes (the doc does not say).
- Whether **delisted** stocks are included (survivorship bias — [[validation]]).
- Rate limits, page behaviour, date-range limits per request.
- Whether matched/deal split, foreign flow and adjusted close are populated in
  the **older years** (fields can exist but be empty/zero pre-20xx).
- Actual field names in real payloads — docs and payloads often differ, so the
  probe assumes nothing.
- Whether a whole-market request with no symbol really works and how it pages.

## Size of the download
~3,650 trading days, a few requests per day for the whole market. Even at a
polite ~1 req/sec this is an overnight job, not weeks.

## Backup
Other VN data providers and open-source libraries aggregating broker data
exist. Any of them needs the same three checks before use: depth, price
adjustment, matched-vs-deal split.

Related: [[funnel-and-scale]] [[money-flow]] [[open-questions]]
