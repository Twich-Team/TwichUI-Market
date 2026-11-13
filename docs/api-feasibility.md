# Forever API feasibility — incomplete

No successful authenticated requests have been observed by this project. No captured live fixtures exist. All current test payloads are synthetic.

Research on 2026-11-13: [firsthand community probe report on Blizzard forums](https://us.forums.blizzard.com/en/blizzard/t/wow-forever-api-what-works-so-far-plus-a-ts-client/60334) describes dynamic-forever regional namespaces, rulesets rather than realms, a trailing-slash auction index, house-scoped commodities, large responses and duplicated listings across rulesets. This is provisional third-party evidence, not an official contract or our live verification. Official developer guides redirected to community.developer.battle.net and could not be read through the research tool.

## Repeatable procedure

Supply BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET in the environment, never command arguments. From backend run `python -m market.probe --region eu --ruleset 2 --house 113`. Configure actual intended region/ruleset/house; example values are hypotheses. Output is JSON Lines containing HTTP status, selected cache headers, retrieval time, payload bytes, SHA-256 and structural counts. Access tokens and response bodies are never emitted. Limit is 32 MiB per response, timeout 45 seconds and one sequential request per second. Stop on authorization, throttling or upstream server failures.

Repeat across intended regions and discovered rulesets/houses; record mapping and compare hashes without combining market identities. Repeat at spaced intervals for at least several upstream updates. Establish Last-Modified/ETag behavior, refresh cadence, empty-house semantics, auction/bid/buyout/unit-price meaning, item variants, commodities boundaries and cross-ruleset equality. Compare conditional requests before enabling collection. Do not infer sales from disappearing listings.

Live verification remains blocked until credentials are available. OAuth client-credentials request is implemented but not yet verified with Blizzard. No refresh interval, mapping, payload size or timestamp guarantee has been established.
