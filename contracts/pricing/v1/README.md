# TwichUI pricing v1 research fixtures

Status: M0.5 proposal for owner approval. Algorithm identifier `twichui-pricing-v1` is reserved here; no production consumer selects it. The reference checker is offline research tooling and is not imported by the server, desktop, addon or release package.

The authoritative specification is [Unified pricing specification](../../../docs/unified-pricing-m05.md). [Research and evidence](../../../docs/unified-pricing-m05-research.md) describes the genuine excerpts, synthetic comparisons and source-execution limits. [Migration plan](../../../docs/unified-pricing-m05-migration.md) defines adoption and rollback.

## Fixture files

| File | Contents |
|---|---|
| `snapshots.json` | 23 price/distribution cases: four captured live listing excerpts and 19 explicitly synthetic scenarios |
| `temporal.json` | Eight synthetic calendars, with independent expectations for existing Market, Workshop and proposed canonical references |
| `boundaries.json` | 30 quality, selling-safeguard, purchase, variant and validation cases |
| `fixture.schema.json` | Closed JSON Schema 2020-12 for the three files |
| `SHA256SUMS.json` | Immutable checksums of those four files |
| `verify.py` | Fraction-based independent arithmetic/schema checker; optional comparison against existing source functions |
| `research-results.json` | Captured research outcomes and source hashes; not a runtime fixture or a replacement for rerunning verification |

Expected numbers are authored constants with arithmetic derivations. The checker must never regenerate them from a product implementation. Every money input/output is a decimal string or null; integers are used for counts, never monetary values.

The four real cases preserve auction ID, full upstream item descriptor and its canonical hash, original retrieval time, namespace, house, source URL context through the source path, source commit/file hash and full-payload hash. Each is an excerpt, not complete variant coverage. The recorded original listing count is the full response count, not the excerpt's size. `scope_complete=false` prevents an excerpt from qualifying production advice. `origin=captured_excerpt` denotes historical captured data; it never claims this research contacted Blizzard or captured a new live observation.

Synthetic temporal points are fixture scenarios, not historical auction evidence. Their prices use identical one-tier inputs under all three formulas, isolating sampling and temporal weighting from snapshot-price differences. The incomplete case supplies an input flag Market does not expose; its Market number is a formula counterfactual, not proof that the server accepts partial imports.

## Verification

With Python 3 and the repository's JSON Schema test dependency available:

```sh
python3 contracts/pricing/v1/verify.py
```

To compare the pinned existing source implementations, with Lua 5.1 on PATH:

```sh
python3 contracts/pricing/v1/verify.py \
  --market-source /path/to/isolated/TwichUI-Market \
  --workshop-source /path/to/isolated/TwichUI
```

The checker extracts only the existing pure Python `summarize` and `rounded` functions using Python AST, without importing database modules. It loads the existing Lua Dist/Valuation modules into a disposable arithmetic harness. No network, database, SavedVariables or fixture writes occur. It does not exercise the DB-backed temporal query, the full Workshop Market API, client execution or Advisor integration. Ordinary verification requires only the JSON fixtures, not either source checkout.

The source-comparison harness generates trusted numeric test calls in a temporary Lua file. That offline test technique is not an import mechanism and is never available to addon users.

## Consumer requirements

- Python: validate the closed schema and semantic invariants, parse copper with bounded integers, use independent exact arithmetic and compare literals. Include DB-backed daily-winner and retention tests in a later implementation PR.
- Rust: consume these exact JSON bytes through strict serde records; retain copper strings at the boundary, use checked `u128` intermediates in the supported domain, and compare expected literals. Add tests to the desktop core after approval; Rust execution is not claimed by M0.5.
- Lua: never turn unsupported copper into a double. Apply `W.Finite`/`W.Int` in range, validate arithmetic bounds before calculation, and compare the same expectations. A future exact wide-integer path needs its own tests; an unsafe computation must return `numeric_range`, not an approximate canonical result. Run domain/decoder tests in plain Lua and later in Test Lab.
- Reject malformed decimal forms, future algorithms, future observations and unknown required fields. Preserve zero as raw source data, but never admit zero as a positive canonical listing price.
- Compare expected presence/reasons and provenance as well as numbers. Do not treat null as zero or an absent day as an unobserved day.

The addon mirror must contain byte-identical JSON, schema and checksum files, pinned to one Market commit. Expected changes require reviewing both mirrors and the specification together. Research tooling and result reports are not product runtime code.
