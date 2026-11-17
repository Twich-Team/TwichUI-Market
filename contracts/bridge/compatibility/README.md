# Reader compatibility policy v1

`v1.json` is the coordinated Market/Workshop test matrix. It documents existing wire identifiers; it does not amend frozen schema bytes or introduce another transport.

The delivery receipt's `desktop_build` identifies the actual Companion producer (`CARGO_PKG_VERSION`). It is display/provenance information, outside the immutable generation hash. Marketing versions never decide import compatibility.

Transport 1 and manifest contract 1 support generation schemas 1, 2 and 3 in the current Workshop reader. Their minimum **reader contract profiles** are respectively 1, 2 and 3; these integers are capabilities, not addon marketing versions. Receipt schema 1 remains required. A future implementation must explicitly add support and conformance fixtures before accepting a new identifier. Unknown positive versions direct players to update TwichUI; obsolete versions direct them to update the Companion and export again. Malformed/contradictory identifiers request a fresh export. Generic integrity/identity errors remain refusals too.

The new addon reader reports receipt build, transport, manifest contract, schema, reader profile and minimum profile in the existing provenance area. It validates the entire generation before atomic activation, retaining the previous compatible dataset on failure. Fixed-format bounded validation, hashes, pricing, market identity and local-history isolation are unchanged. The existing Companion remains compatible with the new reader; no release or protocol activation is required.

Verification: Python validates frozen producer generations/refuses unsupported identifiers; native Rust retains its complete bridge/sync/export suite; the separate addon PR executes this exact JSON matrix and replacement/refusal cases through the real Lua 5.1 reader. The addon fixture carries a SHA-256/source pin. Neither repository downloads or executes the other repository's code at runtime.
