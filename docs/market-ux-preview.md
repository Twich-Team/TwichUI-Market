# Market UX review

The candidate runs in the `marketdev` rootless Docker context on `10.0.4.46`. The host publishes one review port, IPv4 loopback 18444. On a computer with the existing Market SSH login and LAN or VPN access, run:

```sh
ssh -o ExitOnForwardFailure=yes -N -L 127.0.0.1:18444:127.0.0.1:18444 marketdev@10.0.4.46
```

Keep the SSH session open and visit **https://localhost:18444**. Trust the review CA supplied privately with the handoff. Its SHA-256 fingerprint is `A1:17:D5:BD:4D:69:17:52:8D:F3:B1:D0:D6:C8:50:04:92:08:D5:EB:3B:FF:AD:4E:55:8C:8D:CA:24:C5:98:E5`. The certificate and the private login file are also available to the operator under `.local/review/` in the review worktree. The passwords are generated separately for the admin and member and have no configured expiration. Each website session lasts one day.

On iPhone, connect to the same LAN or VPN. Use an SSH client with a local forward on **the phone itself**. Use SSH host `10.0.4.46`, port `22`, user `marketdev`, the authorized SSH identity, local bind `127.0.0.1:18444`, and remote target `127.0.0.1:18444`. Keep forwarding active while using Safari. Install the supplied review CA profile and enable its trust in Settings → General → About → Certificate Trust Settings. Remove the review profile when finished. Open **https://localhost:18444** in Safari. An iPhone without the SSH identity, LAN/VPN reachability, or permission to trust this CA needs those prerequisites from its owner. The desktop forward remains available independently.

## What to review

1. In Explorer, select **Guild review · synthetic auctions**. Search for **sword**, expand Training Sword and compare its 40 variants. Inspect a variant and return using Back.
2. Visit all three Deal Finder modes. Open the Copper Bar listings and page through the stacks. Compare Tough Jerky’s warning with its Item Research history. Prices are asking prices per unit.
3. Sign in as the review admin. Use the grouped Administration navigation. In Storage & Backups → Backups, select a UTC calendar day, inspect an archive and try a protected selection.
4. As the ordinary member, open Desktop Companion. Check the Windows version, integrity details and PC handoff. The approved beta.12 installer defaults to production services. Review the file without installing or approving a device against production.

On a physical iPhone, also check the search field with the software keyboard visible, rotate with a price sheet open, scroll over a chart and tap a point, dismiss an archive dialog, and use Safari Back. Verify VoiceOver reads the price and focused control. The desktop-browser WebKit tests provide emulated coverage.

## Provenance and isolation

The baseline is `3836c2a19cd5fcd21c5c1793c6370fecbe0b6e7f`, the merge of Storage & Backups PR #58. Its feature tip `140e5b4` is an ancestor. The review worktree branches directly from that merge. The release checkout and its seven untracked compose overlays were preserved.

The database is a dedicated PostgreSQL 17 `market_test` on an internal network with bounded tmpfs. Only its API, the static HTTPS proxy and a small in-memory backup fixture start. The fixture exposes simulated inventory, destination readings, manifests and UTC outcomes. Archive creation, deletion, recovery and NAS writes require the genuine management service and receive a refusal in the preview. Confirmation flows and eligibility can be inspected. Repository operation tests cover the real implementation separately.

Synthetic observations enter through the regular ingestion code. Both the administered market and screenshots identify fixture data. Missing item art and unknown bonuses use the application’s fallbacks. No live collection, provider campaign, schedule or retention worker runs. The API has no production DB, queue, keyring, NAS or production storage mounts. The test session cookie is `market_ux_review_session`.

The API reads a copy of the previously approved **2.0.0-beta.12** bundle from the retained release preparation directory. Its source is `e5576c9d66e50914d4bcbbf27aad962a8c9f372f`. SHA-256 is `08200ab7f7600ebd7a005d049122d712de0b76036babaddc1307538830692096` for 4,972,080 bytes. The existing publication receipts and public trust key remain the acceptance evidence for the signed updater. Website delivery checks validate the original bytes. Native installation is outside this preview.

## Restart, stop and rollback

On the review host:

```sh
cd /home/marketdev/.codex/worktrees/market-ux-redesign/TwichUI-Market
scripts/market-ux-review.sh status
scripts/market-ux-review.sh stop
scripts/market-ux-review.sh start
```

Stop closes the review proxy and API, dumps the test DB privately and removes only the review project containers and networks. Start restores that dump or seeds a new review if the database is empty. The private credentials, copied release bundle and CA volume persist. An unexpected host restart can lose changes made after the most recent review dump. The environment has no scheduled teardown. Simulated backup records reset when their fixture process restarts.

To rebuild, check out the intended reviewed source in this isolated worktree and run `scripts/build-market-ux-review.sh` followed by `scripts/market-ux-review.sh start`. The build archives Git’s committed backend, frontend, contracts and deployment files, and pins the three review images to the full SHA. To roll back just the preview, select an already built SHA for `REVIEW_TAG` in the private review environment file, then run the start command. Stopping this review also withdraws access immediately.

## Administration visual review

Collection, Item Metadata → Coverage, and Data Sources use the same private admin login as Storage & Backups. The [matched desktop and phone screenshots](evidence/market-ux/admin-comparison/README.md) compare the previous candidate with the revised pages and Storage at each size.

The review fixture stores 54 simulated collection check receipts on the synthetic recovery market across a 14-day span. It also stores rolling request counts in the same quota buckets that the app reads. These writes send no provider requests and start no workers. Source usage ages out of its measured windows. Snapshot dates come from retained snapshots; a successful check can leave the snapshot unchanged.

In Backups, use **Remove keep flag** to inspect which protections remain on a particular archive. Manual, release and restore-verification archives stay outside scheduled rotation. Independent recovery protection and the minimum recovery-point safeguard can also keep a scheduled copy.
