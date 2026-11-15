# Explorer / Item Details implementation ledger

Owner authorization: implement fully, push a separate feature branch and open a draft PR; stop before production promotion pending final visual approval. Phase 1 is deployed at `e9c4d29`, with integration acceptance through `9ce465a`. Feature branch: `feature/explorer-item-details`; target: `integration/companion-v2-metadata-recovery`.

## Navigation foundation

Added strict supported-integer and exact lowercase 64-character variant route parsing, canonical item URLs, bounded Explorer query serialization, safe internal browsing origins and account-cleared bounded transient restoration. Added focused unit cases for valid/invalid identities, missing routes, browsing round trips, limits and unsafe redirects. This checkpoint does not yet change the existing UI. Existing deep-link inventory finds no prior persistent item route: Deals used an in-memory Explorer selection. Existing invitation, Companion authorization/download and API paths remain separate contracts.

Next: wire controlled catalogue/Explorer state and dedicated independently loaded Item Details; switch Deal Finder anchors; complete restoration, responsive/error/accessibility checks, update browser workflows for the new navigation, and produce the final ten-scene visual gallery with exact-source CI. Production image pins and collector remain untouched by Phase 2.
