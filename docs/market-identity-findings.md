# Forever player-facing market identities — 2026-11-14

**Normal — Horde remains unresolved. No collection scope change is safe on the evidence obtained.** The existing verified US Alliance house110 remains the only scheduled feed, and its history is preserved. Friendly selectors expose desired Region / Ruleset / Faction but block unresolved choices.

## Sources and confidence

- Direct authenticated Blizzard US index at 14:06UTC: HTTP200, namespace dynamic-forever-us. Ruleset2 is named Normal; its auction index lists all fifteen house IDs, with Horde names on113/114/115/120/124. This verifies **faction identity only**, not which house serves Normal. Index response2359bytes, SHA256 84226f6daaa9cca42890729a9fcf006943c9ada3bc7021de47c278f6d120c6ed. Additional current feed/alias observations are recorded in [probe evidence](evidence/market-identity-probes.json).
- [Forever Mastery prices](https://forevermastery.com/en/prices) and its [US Normal Horde page](https://forevermastery.com/en/prices/us-normal-horde), accessed2026-11-14: the publisher reports deriving Normal from an in-game scan and PvP by comparison with Korea/Taiwan. It explicitly leaves RP versus RPPvP groups4/5 unresolved. This is useful independent player-associated evidence, but the rendered public pages obtained do **not identify the numeric Blizzard house ID** behind each friendly slug. Confidence: publisher-reported derivation; insufficient numeric correspondence for activation.
- [Forever Mastery author/editorial policy](https://forevermastery.com/en/about) identifies Yuki Requiem and describes client/build and player-scan sources. No first-hand character-associated numeric mapping receipt was obtained here.
- [Original API investigator's notes](https://mhuijskens.com/WoWForever/Api/) and [their Blizzard developer forum report](https://us.forums.blizzard.com/en/blizzard/t/wow-forever-api-what-works-so-far-plus-a-ts-client/60334) corroborate duplicate house listings across rulesets and independently successful Horde113 alias responses. They explicitly treat the ruleset/group correspondence as uncertain.

The execution host resolves forevermastery.com to0.0.0.0 and direct HTTPS requests fail. Public pages were inspected with the research browser; no DNS, host configuration, routing or access restrictions were changed to retrieve scripts or undocumented endpoints. No private messages were sent to providers.

## Safe transition preparation

The registry stores independently evidenced region/ruleset/faction/house mapping, upstream transport ID, confidence, evidence hash, source URL, receipt and verification time. It starts empty; no Normal/Horde row is fabricated. Guided creation resolves only a verified record. Fresh live feed verification remains separate. Existing technical API clients retain disabled-market creation, with canonical region/house/source alias duplication rejected regardless of requested ruleset number.

Activation requires both verified player identity and a fresh intact live receipt. A global transaction lock prevents concurrent activation races and blocks a second scheduled feed. The confirmed transition endpoint disables the old schedule and enables its verified replacement atomically; markets, snapshots and observations remain intact. The legacy active feed may continue or have its interval edited without retroactively inventing player identity. Disabling it remains possible.

To unblock US Normal Horde, obtain the publisher's numeric house mapping with the scan/character evidence that established it, or an actual in-game/character-associated listing observation that can be matched to one Blizzard feed. Record and validate that receipt first, then obtain owner confirmation of the proposed switch. A ruleset2 URL alone is insufficient. No transition or additional feed was enabled during this milestone.
