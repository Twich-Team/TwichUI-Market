# Release evidence boundaries

These receipts describe the owner-authorized production release and its isolated verification. Full archives, key material, raw tokens and raw account rows remain private and are not committed. Hashes of encrypted envelopes and aggregate preservation fingerprints establish continuity without exposing those values. Application CI/source identities precede this documentation checkpoint.

`replay-clock.json` is synthetic fixed-population evidence. `replay-clock-harness.py` observes the committed `backend/tests/test_recovery_replay.py` fake transport without changing either worker. It requires the existing test dependencies, repository mounted at `/workspace`, and a **fresh disposable synthetic `market_test` database** under the test harness. It drops that test schema afterward. Never run it against production or a genuine restored archive. See the feature report for the frozen-worker identity and separate original replay. Its local CPU/allocation figures exclude PostgreSQL CPU.

`efficiency.json` is genuine forward-ledger evidence from an evolving production population. It is not an old/new policy control; errors and already-known responses remain visible. `coverage.json` defines an observed snapshot, not universal item completeness. The adjacent `production/` gallery is genuine HTTPS data; the parent gallery is explicitly synthetic.

`closing-configuration.json` validates Compose configuration only. Resolving all profiles there did not start any services. Operational commands must retain explicit service targets and `--no-deps`; see the production acceptance runbook.
