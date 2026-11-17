# Approved usability deployment and Companion beta.4

Owner explicitly approves PR #17 implementation/visuals and authorizes controlled integration, additive migration/deployment and a new free-Tauri-signed Windows Companion release. Earlier review-only holds are superseded for this exact scope. No addon modification/publication, destructive pruning/permanent identity cleanup, collector changes, quota increases or unrelated infrastructure.

Baseline: approved application df4d974bec1adb157fbca8b0eabb99f5190c6286, review ea90a98138221bc569d882577a1720fba1298457. Integration stayed 6cef35797f28d562c7ee3db3aa290cfe876f418d, preserving L2; approved PR merged as 6d573c49d929dc63e2cb2115cb9f312787d086fe. Separate release worktree `.worktrees/usability-release`, branch `release/usability-companion-beta4`; original worktrees/untracked files untouched. No team agent or release process uses this checkout/resources.

Actual production: API/frontend/enrichment 6bb71a61fa3493da3f418288c3af1841fabfb0fc, schema fdb_20261116, house 114 alone/300 seconds/zero failures. 97 users, 252 credentials, five Companion devices, 824 observations, 74 snapshots at inspection. Published private signed Companion beta.3, source bd656f19b68f10418e966c8a6418fb3aeaff045e, installer SHA256 d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183, 4,515,855 bytes. Next explicit version beta.4. Compiled updater key remains unchanged. Stable channel remains unpublished.

Resource preflight: rootless context, 11 GiB available RAM and 2.9 GiB disk. Existing 3 GiB backup budget is nearly full; preserve archives and create a separate bounded release archive under ignored owner-only artifacts rather than rotate/delete or increase backup policy. Restore in isolated market_test only, bounded CPU/memory/tmpfs, no collector/provider workers.

Necessary release plumbing: explicit approved visual commit input replaces the signing-stage helper's hardcoded historical visual receipt (strict visual comparison retained); preservation CLI recognizes the two additive schema revisions. No product algorithms/transport/UI redesign.

Pending: exact beta.4 source CI, fresh checked archive/isolated migration/fingerprints, pinned application/rollback images, public production acceptance, exact signed Windows artifact SDK acceptance and private immutable publication. Real Windows toast/tray actions remain owner-PC checks; addon PR #42 stays untouched and is not required for compatibility.
