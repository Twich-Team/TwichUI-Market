# Delayed Explorer navigation correction

Post-merge verification of the unrelated house-114 collector repair at
`3f0421a2221e424df751b963f5b66b445e319018` exposed an existing browser race.
The complete browser receipt and screenshot are retained privately under the
collector repair worktree's ignored diagnostic directory. Failed run
45117269059 / job 137502845474 had 48 passing ordinary browser cases and one
failure in `admin-tables.spec.ts:14`.

The trace shows the Administration button clicked at 2591 ms while the markets
request and Explorer's first canonical URL effect were settling. At 2604 ms the
page URL was back at the canonical Explorer URL. No administration chunk or API
request was issued. The unchanged frontend's delayed Explorer effect replaced a
newer navigation; this is a product race, not an auction or upstream failure.
The collector repair changes no frontend source. The identical pre-merge tree's
website checks had passed; a single evidence-based rerun of the merged-source
job is recorded separately, never substituted for the failed receipt.

The minimal correction permits Explorer canonicalization only while both the
pathname and query still match that render's input. Newer page navigation and
newer Explorer queries take precedence. Six deterministic regression assertions
exercise current, already canonical, changed-query and four other-page cases.
No timeout, retry policy or browser assertion is relaxed. The local 138-test
Vitest suite and production frontend build pass. This correction has its own
branch and PR; it does not expand the two-module collector deployment.
