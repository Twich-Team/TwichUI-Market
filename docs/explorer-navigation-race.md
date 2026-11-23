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


The separate correction's first Windows run45119365339/job137509349688 fails
the unchanged native approval-heading assertion at `companion-native.cjs:42`
(5-second deadline). Backend, website, picker and signed updater pass; this branch
is not merged or deployed. The original artifact is preserved with SHA256
91670c94a64a60277b9e10aa50fa32b8792380e1b9da46a6c40da3b27f15f3f1.
It contains only a pre-input welcome screenshot and no rejected approval page
or request display name, so the failure's precise cause cannot be inferred.

A test-only diagnostic now retains the actual failed page's safe headings,
alerts, pathname and synthetic request display fields and screenshot before
rethrowing the exact original assertion. It excludes authorization URL queries
and consent tokens. No deadline, retry, assertion or native input path changes.
The hypothesis is an unexpected approval-page/display-name state, rather than
the unrelated collector or Explorer canonicalization helper. A new source run
with this observation is warranted; a favorable rerun alone cannot prove a cause.
