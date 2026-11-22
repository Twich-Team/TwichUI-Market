# Prepared-current integration and private acceptance

Continuation of game-ready-current-results.md and the 22 November private-test readiness
report. No merge, production deployment, signing or release publication is authorized.

## In progress: automatic-sync failure

Original run 45072066729 at 999b040 fails baseline automatic repeat 1 before the candidate.
The original artifact is retained under docs/evidence/prepared-integration-blockers/;
its source and SHA256 are recorded there. Eight 202 responses and Windows Proactor resets
do not yet establish the cause. The first checkpoint adds bounded, header/body-free ASGI
wire evidence and native example stage duration, shared with the unchanged frozen baseline.
No client algorithms, waits, request retries, assertions or error handling are relaxed.

Next: use exact Windows evidence to isolate the failure; repair and regress its actual
cause, then run complete integrated workflows. Reconcile addon main on the feature branch
and retarget #131 to main for required verify; do not merge #127/#131 or chart #117.

Native acceptance preparation must use isolated DEV credentials/storage, disabled updates,
a disposable VM/private game installation, and a same-source-generation 16/32 pair with
64 unchanged histories. A missing real-source endpoint/artifact must remain an explicit
blocker; no synthetic fixture is real-market acceptance.
