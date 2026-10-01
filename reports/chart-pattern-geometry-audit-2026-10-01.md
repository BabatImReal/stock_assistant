# Outcome-blind chart geometry audit

The first chart pilot's event table was audited **without using event-level forward returns to select or judge cases**. The investigator had already seen the v1 aggregate descriptive table, so this is a geometry/causality audit, not a fresh efficacy test. `scripts/audit_chart_patterns.py` (commit `e8e4ff5`) deterministically selects, by SHA-256 of `episode_id`, two confirmed up-breaks and two confirmed down-breaks for each of the five registered variants, plus one rejected `late_or_unobservable` event per variant. Only events dated through 2023-12-31 are sampled. Selection reads event metadata; chart rendering reads adjusted bars but displays prices only through each candidate/signal date. The audit script opened no returns table or displayed post-signal prices. The 25-row sample CSV has SHA-256 `b0c894269eaf059a2f381aa8852b3c22acff7148f931f38e735bcc11da2a5b05`; plots and sample are under git-ignored `data/reports/chart_audit_v1/`.

All 25 selected episodes reappeared with the same candidate and signal dates when detection was rerun on bars **truncated at the event date**. This checks causal replay; it does not prove that the geometry is a useful market signal.

The visual sheets exposed a material definition problem. A triangle is constructed from confirmed pivot anchors, but v1 checks for a boundary excursion only from its *last anchor* to candidate confirmation. Some prices between the first and last anchors already lay beyond the eventual boundary. Applying the existing 1% triangle touch tolerance and 1.5% repeated-level tolerance as diagnostic bands, 3 of 20 sampled confirmed events breach their formation boundary: VAT (symmetric, maximum 13.46% excursion), NAB (symmetric, 2.10%), and DVP (descending, 1.56%). The other 17 confirmed cases stayed within their respective bands. This is a **fixed-sample finding**, not a whole-market defect rate. Two of five already rejected late cases also breached. The repeated-level sample had no confirmed excursion above its 1.5% level tolerance, but some cases resemble a broad trading range more than a clean two-turn reversal (for example DCT and DPS). That ambiguity needs human/broker review; it is not fixed by changing a threshold after viewing returns.

| Variant | Confirmed sampled | Formation-boundary breaches | Sample examples |
|---|---:|---:|---|
| Double top | 4 | 0 | DCT and LGL look range-like |
| Double bottom | 4 | 0 | DPS looks range-like; VGT is a clearer turn |
| Symmetric triangle | 4 | 2 | VAT, NAB exceed the eventual wall |
| Ascending triangle | 4 | 0 | All remain within the 1% diagnostic band |
| Descending triangle | 4 | 1 | DVP exceeds the eventual wall |

Do not reuse the v1 effect table as validation of a corrected detector. Any containment requirement changes the event population and must be registered as a new version before its outcomes are inspected. Likewise, observed up/down break is known at the signal close and can be a separate **long-only conditional hypothesis**, but its two sides are not automatically bullish/bearish recommendations. All such comparisons remain exploratory on previously seen history and require prospective confirmation.
