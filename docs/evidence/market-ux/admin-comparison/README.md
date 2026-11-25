# Administration before and after

Desktop captures use 1280 × 900 CSS pixels. Phone captures use 390 × 844 with touch emulation. Each pair starts at the top of the same route with the default disclosures closed. All captures came from the authenticated review site using the same isolated database and synthetic receipts. The baseline is commit `15c34e3`. Storage & Backups is the visual benchmark. Its sample service timestamps are relative to each service start.

| Page | Desktop before | Desktop after | Phone before | Phone after |
|---|---|---|---|---|
| Collection | [Before](collection-desktop-before.png) | [After](collection-desktop-after.png) | [Before](collection-phone-before.png) | [After](collection-phone-after.png) |
| Metadata Coverage | [Before](metadata-desktop-before.png) | [After](metadata-desktop-after.png) | [Before](metadata-phone-before.png) | [After](metadata-phone-after.png) |
| Data Sources | [Before](sources-desktop-before.png) | [After](sources-desktop-after.png) | [Before](sources-phone-before.png) | [After](sources-phone-after.png) |
| Storage overview | [Before](storage-desktop-before.png) | [After](storage-desktop-after.png) | [Before](storage-phone-before.png) | [After](storage-phone-after.png) |

## Independent rendered review

An independent GPT-6.2-Astra reviewer compared all sixteen before/after images at both widths. The first review flagged three problems. Disabled markets obscured operational problems, mobile coverage labels ran into their counts, and a missing-key warning made it hard to tell which sources could recover items. The implementation responds to those findings. The reviewer passed all three revised views against Storage.

- **Collection.** Four health cards lead to the affected market and an investigation action. The first phone viewport contains part of the plot. Stacked bars count check outcomes and diamonds count saved snapshots on a separate axis. The 7–90-day admin endpoint aggregates retained check and snapshot rows by UTC day in PostgreSQL, independently of table sorting, filters, and pagination. A snapshot-only window still draws a timeline.
- **Metadata Coverage.** The three cards use the same latest-snapshot denominator. The pictured market has 40/60 names, 0/60 local icons and 1/60 items with stored attributes beyond name/icon. Exact counts remain available beside the percentages and meters.
- **Data Sources.** The first screen summarizes automatic recovery, providers requiring review and disabled sources. Each card displays the effective application limits and measured reservations in its rolling windows. Provider-reported quota, missing data, and a window without a configured limit have distinct labels. On phones the second provider needing review may require scrolling.
- **Storage benchmark.** The paired Storage images show the existing visual hierarchy used in the comparison. The revised keep-flag dialog names the flag change and the archive-specific rotation restrictions. The genuine manager reports the explicit keep flag separately from its recovery pin. Both browsers exercised the manual, scheduled and reserved examples in the isolated preview.

Sol Medium implemented Collection and the metadata views. Astra coordinated integration, made decisions about evidence and backup semantics, and provided the independent visual review. The screenshots use browser touch emulation. Physical Safari remains an owner-device check.
