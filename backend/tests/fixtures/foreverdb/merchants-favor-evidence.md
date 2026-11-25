# ForeverDB Merchant's Favor response fixture

This minimized test fixture is derived from one authenticated, server-side, quota-accounted GET of [ForeverDB's Merchant's Favor endpoint](https://foreverdb.net/api/v1/merchants-favor) on 2026-11-25 at 05:32:59 UTC. HTTP 200 returned game build `1.60.1.71091` and body SHA-256 `0a148f0ab10e81692c6ac38cbabd83fcca3ce537c13bda8814462ace10f739b9`. The complete response contained 30 unfilled crate IDs, 96 individual material choices, and 15 sealed crate IDs. It explicitly reported an unknown Favor amount.

The fixture selects five crates across four tiers and both observed qualities, retains their complete sets of choices, and includes six sealed IDs. Three distinct sealed IDs with the same Apprentice name show why the generic transformation cannot establish an exact output ID. The fixture count reflects its reduced contents, while its selected item IDs, qualities, levels, material quantities, and transformation wording come from the response. Developer identifiers, unrelated fields, and marked prose are excluded. Results using this fixture do not establish a live price or Favor reward.

Data from [ForeverDB.net](https://foreverdb.net).
