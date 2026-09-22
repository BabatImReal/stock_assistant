# Project (doc §1)

**What it is.** A daily pattern-research tool for the Vietnamese stock market
(HOSE, HNX, UPCoM). Every day it looks at every listed code, describes how the
last few days of price and volume behaved, finds what historically followed
similar behaviour, and proposes **one** stock with the evidence — or says
"nothing strong today".

**Who it is for.** Ben, alone. He is the decision-maker; the tool never buys.
That also keeps it outside Vietnamese investment-advisory licensing, since no
third party is being advised.

**Three framings that shape every design choice (doc §1):**

1. *Research, not prediction.* The output is a statement about history
   ("this shape with this volume on this stock was followed by a rise X% of the
   time"), which can be checked, not a claim about the future.
2. *Ben decides.* The tool proposes and shows its working.
3. *"Good", not "correct".* A good recommendation has enough evidence to be
   worth considering **plus** a clear statement of what would prove it wrong.

**Horizon.** Setups form over 3–5 trading days; the question is what happens
over the following few days. Weekly/monthly timeframes are context, not the
main signal. This horizon also happens to fit Vietnam's T+2 settlement
(doc §5.6) — a 1-day edge would not be tradeable.

**Where the edge comes from.** Not the patterns — those are public. It comes
from measuring them honestly *on Vietnamese data, per stock, with Vietnamese
rules and costs*, and from encoding the judgement of Ben's broker friend, who
has studied VN price data since ~2010 (doc §6.4, §11.1).

**Scope discipline.** Research phase first. No live trading, no automation of
execution, no real-time streaming until the end-of-day research core works
(doc §11.5).

Related: [[patterns]] [[funnel-and-scale]] [[validation]] [[open-questions]]
