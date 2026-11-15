# Combined Companion v2 / metadata release operations

The owner's attached integration request authorizes this deployment and exact signed beta2 publication. Frozen inputs remain Companion `d9d5ae3` / review `75c6f38`, installer source `c7bad2f`, and metadata PR #2 `b18927a`. Original evidence and installer bytes are retained. The application merge is `f31050c`; release operations and complete signed-updater reacceptance are `3e23425`. No application source changed between those two commits.

## Scoped production commands

Always use the complete configuration, including the private environment file. Never print its rendered environment or run an unscoped `up`:

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  up -d --no-deps --wait api local-api proxy
```

The combined overlay pins API, website and offline publisher images. It does not retag older production/rollback images. Existing collector, PostgreSQL, monitor and backup services remain on their existing identities. Enrichment is the one separately replaced worker, started with `--profile metadata ... up -d --no-deps enrichment` after schema/provider setup. There is one auction collector; no new collection project is started.

Before migration, require exact-commit backend/browser/Windows CI, signed original-byte Windows acceptance, current checked backup/actual isolated restore, every-table original-column migration preservation, resource headroom and pinned rollback images. The verified rehearsal uses only `market_restore`; destructive test fixtures remain restricted to `market_test`. Required order is `0012 → 0013 → meta_20261114`. Keep the additive schema during application rollback.

Publish only the prepared original signed beta bundle with the pinned network-isolated `private-beta-publisher`. The API reads that dedicated volume read-only. Its allowlist ends with owner account ID 1 only. Temporary audited test membership is removed after acceptance. Every published version/evidence/audit is immutable, and no updater private key enters the publisher/API/CI/database.

## Immediate rollback without data deletion

Pause queued/running metadata jobs through the authenticated administrator controls and stop only enrichment. Supplemental providers and automatic recovery are disabled initially, so the predecessor UI's supplemental attribution limitation cannot be triggered by this initial rollout. If new supplemental records have subsequently been imported, retain the compatible metadata UI/API until attribution is reviewed; never erase metadata projections to make a rollback convenient.

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  --profile metadata stop enrichment
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.combined-rollback.yaml up -d --no-deps --wait api local-api proxy
```

The rollback overlay selects the immediately preceding approved API/frontend, preserving schema, encrypted credentials, sessions, new records and all history. Never downgrade the populated schema, restore a dump over production, drop/recreate the database, or modify the collector/AMP/Traefik/Komodo/networking. Database recovery means restoring a verified archive into an isolated database, restoring the separately protected keyring, preserving subsequent live data, and preparing an explicit incident recovery decision. A database cutover or destructive restore is outside this release authorization.

## Metadata keyring recovery

Runtime keyring: `/home/marketdev/.local/share/twichui-market-metadata/keyring.json`, file mode 0600, owned by container UID 10001 under the marketdev rootless UID mapping. API, local API and enrichment mount the same file read-only. Do not print it, add it to Git, or put it in SQL/public download directories. The existing file bind requires a controlled API/enrichment remount for a future atomic key replacement; routine provider-key replacement uses the website and requires no restart.

Encrypted keyring backup: `/home/marketdev/.local/share/twichui-market-metadata-recovery/keyring-20261115.aesgcm`. Its separate 0600 recovery key is `/home/marketdev/.local/state/twichui-market-metadata/keyring-backup.key`. AES-256-GCM uses associated data `twichui-market-metadata-keyring-v1`; the first 12 backup bytes are the nonce. All parent directories are 0700. An actual decrypt/compare and credential encryption/decryption rehearsal passed without displaying key material. Recovery must preserve the UID/mode and verify both application processes can load it. No off-host copy has been verified; transfer the encrypted backup and recovery secret to separate owner-controlled secure locations through the owner's normal secure backup process.

## Owner-controlled Everloot validation

Enter the real key only at authenticated Administration → Data Sources → Everloot → Add API Key. The empty password form does not retrieve stored keys. A staged key is encrypted and validated by the independent worker before replacement; failed validation retains an earlier valid envelope. No fabricated provider key is installed. All provider recovery is initially disabled, including Blizzard, and automatic recovery stays disabled. The existing auction collector continues independently with its preserved OAuth configuration. The metadata worker can validate a privately staged key while recovery is disabled.

The initial Everloot configuration is 20 requests/hour and 20/day, automatic=false, enabled=false. Validation requests share those persistent budgets with recovery. After the genuine connection/contract validates, use a single administrator-controlled job with at most **19 external recovery attempts**, reserving one of the 20 for credential validation; retries count against the same job/provider budgets. Keep it within a **45-minute observation window**, pause/cancel at its deadline, honor stricter provider limits/Retry-After, and do not start bulk imports or other Everloot jobs/tests in that window. If validation requires additional attempts, subtract them from the remaining recovery budget. No larger import or automatic enablement is authorized by this initial test.

Before starting, settle local legacy-catalog backfill, freeze the exact live market-2 snapshot/observation/item IDs and price/supply hashes, and record per-ID primary/supplemental name/provenance availability. After stopping, measure those same IDs and original price rows; report exact gains/losses/conflicts, attempts and cache skips. Existing names/local backfill are baseline availability, not provider gains. The committed production acceptance receipt supplies the current measurement. No coverage improvement is claimed before a genuine fixed-population before/after comparison.

Windows beta remains `2.0.0-beta.2`, installer SHA256 `0fbc53603c218ffa85c8ee7b4e54f25e53c52a6fc3b2330ae914337714d41869`. Free Tauri signatures verify updates; Windows publisher is honestly unsigned. Owner-PC tray actions and a native Windows-to-production walkthrough remain manual acceptance, distinct from automated Windows and public server/browser checks.
