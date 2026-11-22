# Prepared-current integration and private acceptance

Continuation of game-ready-current-results.md and the 22 November private-test readiness
report. No merge, production deployment, signing or release publication is authorized.

## Automatic-sync failure and repair

Original run 45072066729 at 999b040 fails baseline automatic repeat 1 before the candidate.
The original artifact is retained under docs/evidence/prepared-integration-blockers/;
its source and SHA256 are recorded there. Instrumented Windows run 45075563739 reproduced
the failure at baseline repeat 1, attempt 19: `synchronizer` returned Network in under 1 ms,
before the next bootstrap entered ASGI. The preceding 202 headers AND body completed.
That failing repeat has zero loop exceptions and no active server requests. Completed 202s
reuse the same TCP port across five-second sleeps; other sleeps retire the connection.

The fixture's five-second preparation wait collides with Uvicorn's five-second HTTP/1
idle deadline. A connection can be selected from the native pool as the server retires it,
failing before the request reaches the app. Windows Proactor reset warnings also occur in
successful repeats and are not the cause established by this failing repeat. No 30-second
client timeout, slow projection, server crash, or test teardown produced this failure.

The deterministic closed-pool negative control reproduces a <1 ms next-bootstrap error
`hyper::Error(IncompleteMessage)` using the same reqwest constructor policy. This is an
explicit fault-injected regression, not a claim that the original stripped error contained
that diagnostic. The announced-close control passes. Both controls and the natural Windows
comparison are retained separately. Repair: the disposable server explicitly sends
`Connection: close` with 202 before intentional preparation waits, identically in both arms.
No client algorithms, waits, timeouts, request retries, economic assertions or error handling
are relaxed. Teardown now records its result and fails if the server cannot stop before
database disposal. Final repaired Windows comparison is pending.

Addon #131 includes main 1a3d9eb by feature-branch merge and now targets main; final addon
source is 1e034c025613a245f6238866fb2a57d76690c596. Required verify run 45075746137 passes
324 tests, zero failures (503.541 s); fast run 45075746046 also passes. No main PR was merged.
Chart #117 remains separate. Market diagnostic checkpoint 91e1132 passes Backend322,
Windows314 (all six jobs) and website310; the unrepaired sync run remains a preserved failure.

## Native preparation

The owner identified https://market.twich.gg/, US Normal/Horde market2/house114 and authorized
the existing device-authenticated Contract 3 source (including normal summary preparation
cache writes). No credentials were requested or read here. No production API request was
made by this task. Obtain data in the independent Windows DEV installation using that flow.

The kit removes the need for a new listening endpoint: a COPY of completed DEV cache is
validated against the actual proposed prepared API in-process using disposable SQLite and
isolated test credentials. Both layouts retain the original G and all 64 history files.
An offline private-dev native helper publishes either validated layout to the already
confirmed, explicitly marked private game, without network or discovery. This is isolated
test tooling; no production runtime/format/price calculation is changed.

The matched fabricated 60-day pair has G 9280237f3de291db51fc58d0564355e0ed6dbb58b9fd32212126ae6bf98e9137;
both native/Lua paths pass, with identical 129 current tuples and 64 historical byte hashes.
The local endpoint adapter passes 401/200/304 for both layouts and typed history/current
binding. These are fabricated ordinary-admission fixtures, not genuine Market records.
Native summary tests pass 26/26; one existing opt-in driver remains intentionally ignored
by ordinary development tests. Windows helper/paired publication and exact-source DEV
installer build remain pending. Follow [private acceptance](private-prepared-native-acceptance.md).
