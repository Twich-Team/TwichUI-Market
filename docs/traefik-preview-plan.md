# Traefik access and interactive preview

Owner authorization: expose only 10.0.4.46:18780 to the existing Traefik route, retain localhost:18443, and expose the unapproved modernization preview only on 127.0.0.1:18444. Never promote modernized assets, duplicate the collector/database, modify Traefik or change host firewall/AMP.

1. Inspect resources, DNS/certificate, rootless source-IP behavior and existing route. Acceptance: exact trusted proxy established, old production image pinned, backup recorded.
2. Add origin-bound browser session audiences, distinct configured cookies, preview read-only enforcement and explicitly authenticated proxy metadata. Migration round-trip/legacy-local/device compatibility and security tests on isolated PostgreSQL.
3. Configure bounded public/local/preview API instances sharing existing PostgreSQL, one collector only. Public listener HTTP on private interface, remote-peer allowlist (not forwarded client IP); localhost TLS retains explicit origins and persistent project CA. No internal API/database host ports.
4. Deploy additive migration after backup, preserve old production assets, verify real public DNS/TLS/auth/CSRF/logout/device API and preview table/tooltips/charts/admin/account with trusted-CA Chromium.
5. Record actual evidence/blockers, cleanup/rollback/operator instructions, tests, commits and pushes. Modernized frontend approval remains pending.

Baseline: private interface exists; requested ports free. RootlessKit 3.3.0 / Docker29.9.2 support source-IP propagation, to be verified empirically. Traefik route read-only at rldiamond/twichgg_traefik commit04861313; public TLS trusted, current HTTP502. Its current forwardedHeaders trust is broad; Market will select the rightmost appended client address from its one trusted immediate proxy and never trust arbitrary leftmost headers. No changes to that repository.
