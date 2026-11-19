# Workshop live integration repair

Owner follow-up authorizes repairing repeated Companion sync, publishing while WoW is open, built-in AddOns grouping/icon, visible in-game consumption and actual Market history, while retaining standalone local scans. Work is isolated from the live beta.9 release and the original coordinated draft branches.

## Implementation

1. Keep one synchronization run active while retrying Workshop preparation; never restart a completed price download for a preparation response. Cancellation, account changes and authentication remain enforced.
2. Publish through the existing inactive bank/root commit and integrity checks while WoW is open. Explain that a player reload applies changed files. Reject stale/mixed lazy partitions without substituting another generation; preserve validated data.
3. Apply the existing TwichUI icon and explicit `Group: !!!TwichUI` to root and both banks, accepting exact legacy owned metadata during migration. Forever native source confirms Group must equal the parent folder and supports IconTexture.
4. Add a versioned, negotiated history delivery format using genuine daily closing observations, exact variants, observation identity and explicit gaps. Preserve v1 readers/routes, bounded work, last-good data and historical provenance. Do not manufacture chart points from reference averages or mix local scans into server curves.
5. Report in-game loaded/validated generation, record and partition coverage, source date and chart source. Missing external data leaves local scanning/research usable; research data never pretends to establish native inventory equivalence or completed sales.

## Validation and release boundary

Exercise retry/cancel, metadata migration, game-open publication/interruption/multiple generations, strict version/schema/hash identity, historical gaps/unknowns, account isolation and standalone mode. Run focused PostgreSQL/Rust/Lua/JS checks, coordinated consumer fixtures and affected simulator/Windows CI. Commit/push review checkpoints and draft PRs. Production, signed beta.9, collector, retention and backup state remain untouched during implementation. Native Forever loaded-game acceptance remains an owner check.

## Progress

- Root causes confirmed in runtime retry, explicit game-running guards, generated TOCs and hardcoded Settings collection label.
- Owner confirmed the built-in WoW AddOns list and authorized actual history plus standalone operation.

## Checkpoint evidence

- Addon [draft #62](https://github.com/Twich-Team/TwichUI/pull/62), source `c1a46a5cbfb9382eb24d49fb64bd4d65ac5f27ac`, exact tree `36d17d805c18147aee0826a98d683f222ad06f10` reconciles current main `516c6d6`. Local checkpoint commits remain on `fix/workshop-live-status-local-checkpoints`; the read-only deploy key required using the connected GitHub writer. Every uploaded blob and final tree match the committed local source. Original U1/U2 and draft history remain preserved.
- Focused PostgreSQL: 55 pass, including legacy summary and actual negotiated history, source coverage/unknowns, sync and pinned generation tests. Full native Rust workspace passes; malformed history, exact metadata migration and cancellation cases included.
- Addon focused Market: 31 pass; settings: 12 pass. Real production-reader synthetic history/UI, immutable returned data, source clarity, missing-data fallback and late bank overwrite/reload paths pass. Broad checks/CI remain in progress; the initial broad attempt had missing test prerequisites and changed source, so it is not a green full-suite receipt. Simulator is absent.
- Companion mocked-IPC browser flow/mobile/accessibility passes with Files ready/reload wording. This is not installed Windows evidence.
- Explicitly synthetic 26,342-variant / 60-day native-validated stress bundle contains 31,610,464 raw bytes in 64 parts; one selected item loads one 510-KiB partition. Initial desktop Lua run takes about 1.28 CPU seconds to validate the focused partition, with a measured callback over 9 ms; this is a limitation, not a Forever frame-time claim. Further source-qualified measurements remain pending.

No production or private signed distribution changes have occurred.
