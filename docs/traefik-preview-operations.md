# Production ingress and interactive preview

## Current state (2026-11-14)

- Interactive review: **https://localhost:18444**, bound only to 127.0.0.1. Modernized assets remain unapproved and separate from production.
- Existing production/local access: **https://localhost:18443**, unchanged served asset hashes (six files). Local authentication remains available.
- Intended public URL: **https://market.twich.gg**. The real Traefik route/certificate works, but Market deliberately returns **403** until a host administrator installs source restriction. Public login/authentication is **not** claimed verified.
- Private listener: **10.0.4.46:18780**, plain HTTP, bound only to that address. No PostgreSQL/API/development host ports were added.

The existing Traefik route was read at rldiamond/twichgg_traefik commit04861313. No Traefik files or unrelated services were modified. Local DNS resolves market.twich.gg through portal.server.twich.gg to 10.0.4.3. Google public DNS returned NOERROR/NODATA for an A lookup; an internet-facing DNS record is not established by this LAN test. If internet access is intended, the DNS owner must publish the appropriate A/CNAME to the existing public Traefik ingress, never to the private VM address. No DNS changes were made.

## Exact source-filter blocker and administrator action

Host TCP inspection confirms the actual Traefik peer is **10.0.4.3**. Both that connection and a direct VM HTTP request appear inside Caddy as **172.18.0.1**. RootlessKit3.3.0/Docker29.9.2 alone do not prove source preservation: this deployment's forwarding path demonstrably loses it. Caddy's immediate-peer matcher is deliberately placed before all handlers, defaults to the actual Traefik IP, and therefore rejects both paths. Forging X-Forwarded-For does not bypass it.

A host administrator can install this narrowly scoped nftables filter. These commands were **not executed** by the agent. Inspect any existing table with this name first; do not flush/replace the existing firewall or enable a new default-deny firewall that could affect AMP.

```sh
sudo nft add table inet twichui_market_guard
sudo nft 'add chain inet twichui_market_guard input { type filter hook input priority -5; policy accept; }'
sudo nft 'add rule inet twichui_market_guard input ip daddr 10.0.4.46 tcp dport 18780 ip saddr != 10.0.4.3 reject with tcp reset'
```

This rejects only non-Traefik sources to the one Market address/port, including direct VM-origin requests; all other traffic is unchanged by this chain. The administrator must integrate this rule into the host's existing firewall persistence/order before activation. Do not remove it while trusting the rootless transport. Rollback of only this new table is `sudo nft delete table inet twichui_market_guard`, **after first restoring Market's fail-closed transport setting**.

After administrator confirmation, marketdev can run:

```sh
python3 scripts/activate-traefik.py --administrator-confirmation 'non-secret-change-reference'
python3 scripts/verify-access-deployment.py --public-enabled
```

The activation script refuses while a direct non-Traefik HTTP request still reaches Caddy (even HTTP403 is insufficient). That negative check has been tested and currently refuses without changing configuration. It additionally checks trusted local TLS health, then sets only the private `.env` transport peer to the observed rootless gateway and updates the pinned production proxy. An administrator reference plus the network precheck are required; this is not an automatic proof that every external host is filtered. The final public verifier must pass after activation. Its public-enabled branch is prepared but has not been live-verified while ingress is blocked.

With that host source boundary, Caddy trusts only the exact transport plus the explicit Traefik IP on its HTTP listener, parses forwarded client addresses right-to-left, fixes the upstream Host/scheme, and authenticates internal metadata using a private random gateway token. Uvicorn still uses --no-proxy-headers. Local/preview APIs ignore arbitrary forwarded headers. The current Traefik entry point's broad forwarded-header setting was observed read-only and was not copied into Market.

If host firewall changes are unavailable, a separately planned source-preserving publisher or authenticated upstream is required. Do not broadly trust the gateway as a workaround. If private-LAN HTTP is unsuitable for the network's trust model, use an explicitly validated private HTTPS/mTLS upstream with an appropriate Traefik CA configuration; do not disable certificate verification. The configured existing route currently expects HTTP and was not changed.

## Deployment and security boundaries

Use all three production files for future updates:

```sh
python3 scripts/init-env.py
python3 scripts/pin-production-frontend.py
docker --context rootless compose -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml build migrate
docker --context rootless compose -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml run --rm --no-deps migrate
docker --context rootless compose -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml up -d --no-deps api local-api proxy
```

Generate missing secrets without printing/overwriting existing values. Back up before migrations. The approved production image is built from a captured copy of the actual running /srv, not modernized source. Its source snapshot/manifest remains ignored in .local/production-web; preserve this and the production-approved image in normal deployment backups. The production overlay removes its build directive, so --build cannot silently promote the modernized website. The collector/monitor/database are not restarted by the scoped update above.

Migration0010 adds a nullable browser-session audience only. Sessions newly issued by each API are origin-bound; device tokens/cursors/contracts are unchanged. Public origin is exactly https://market.twich.gg. The local API retains https://localhost:18443 and explicitly accepts legacy unaudienced local sessions. Preview uses https://localhost:18444, a distinct HttpOnly/Secure/SameSite=Strict market_preview_session cookie, and rejects legacy/other-origin browser sessions. No arbitrary origin allowlist or cross-origin API access was added.

Preview shares the existing database through a dedicated 256MiB/.25CPU API; it has no collector. Unsafe methods are blocked server-side except login/logout. Administration/account mutation controls are disabled, metadata-priority writes are suppressed, and attempted direct mutations return403. Authentication, security audit and login-rate-limit records still write normally. Background production collection/enrichment continues independently.

## Reviewing the preview from another computer

The preview intentionally is not exposed on the VM's LAN interface. Use an existing authorized SSH connection from the review computer:

```sh
ssh -N -L 18444:127.0.0.1:18444 marketdev@10.0.4.46
```

Open https://localhost:18444 and sign in with your existing account. The owner password was not reset. The preview has a persistent project-local CA. Obtain the **public** artifacts/access-deployment/preview-root.crt over the existing trusted SSH channel and trust it in the review browser/OS as appropriate. Its fingerprint is in the evidence JSON. No host/browser trust store was modified automatically. Browser verification imports only the exact project CAs into a disposable container NSS database; it does not ignore TLS errors. The public Traefik certificate validates using ordinary public roots.

Start/update preview:

```sh
docker --context rootless compose -f compose.item-preview.yaml up -d --build
```

Both preview containers have bounded resources/logs and restart unless stopped. The database, worker and existing production frontend remain separate. To clean up only preview services:

```sh
docker --context rootless compose -f compose.item-preview.yaml down
```

Do not add --volumes: keep its CA for a later review. Never run an unscoped Docker prune or remove the production data/Caddy volumes. Removing preview is not approval to promote its assets.

## Verification

Build the disposable trusted-CA browser image with `docker --context rootless build -f deploy/browser-verification.Dockerfile -t twichui-market-access-browser:dev .`. Run `python3 scripts/verify-access-deployment.py` for the current expected-public-blocked state. The helper creates audited temporary admin/member accounts without touching the owner, then disables them and revokes their credentials in finally; private0600 environment files are removed. Screenshots/results are ignored artifacts/access-deployment. The public-enabled mode must be used after source-filter activation.

Verified: 120 PostgreSQL regressions, 17 frontend tests, six original Chromium workflows, isolated0010 migration round trip/parity, real local/preview login/CSRF/device sync/logout, distinct-cookie/audience isolation, genuine catalogue/icons/variants/hover/focus/touch/charts, read-only admin/account, and zero axe violations. Public TLS/route/403 are verified; public login, cookies, CSRF and desktop-through-public behavior remain externally blocked and explicitly unverified. Direct signed API metadata behavior and public-style HTTPS redirects have unit coverage.

Primary networking references: [Docker rootless networking troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/), [Caddy trusted proxy/strict parsing options](https://caddyserver.com/docs/caddyfile/options#trusted_proxies), and [Caddy immediate-peer matchers](https://caddyserver.com/docs/caddyfile/matchers#remote_ip). The blocker above is based on actual kernel/Caddy observations, not a version-based assumption.
