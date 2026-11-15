# Everyday polish evidence

Application `dfb645b8946f0d158e8da9855fef01768e382674`; [draft PR #5](https://github.com/Twich-Team/TwichUI-Market/pull/5).

Open [review.html](review.html) for 15 visual scenes. Original PNGs are under `screenshots/before` and `screenshots/after`; hashes are in [screenshots.json](screenshots.json). All screenshot data is synthetic and isolated. The baseline is the actual retained `4ddf137` frontend image; the candidate is the pinned `dfb645b` frontend/API. Denver is the main browser timezone; Auckland supplies the other date boundary.

The canonical browser fixture sequence is `web/e2e/seed.py`, `seed-admin.py`, `seed-quality.py`, `seed-private-beta.py` against a dedicated `market_test` stack, then `npm run test:e2e` in the pinned browser environment. `web/e2e/everyday-polish.spec.ts` captures the regression scenes and pagination measurements. The guarded `review-fixture.py` adds six review-only persisted outcomes and assigns the main fixture history to market 2, reproducing the actual scope mismatch; it makes no provider request and is applied only after canonical tests.

Read-only production diagnosis is reproducible through `scripts/diagnose-provider-results.py`, using the established rootless operator path. Production query receipts are separate from fixture screenshots. No production data was seeded, restored or changed.

CI source/step receipts, exact test excerpts, public asset comparisons, container preservation, local preview acceptance and bounded performance measurements are adjacent. Consult [the full report](../../everyday-market-polish-review.md) for caveats, attribution, history limits and the exact owner-review boundary. Later documentation/evidence commits do not change the frozen application tree.
