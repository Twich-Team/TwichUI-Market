# Provider rate management visual review

Actual Chromium captures from isolated `market_test`, **entirely synthetic quota data and fake encrypted credentials**. No live provider calls or production observations. Browser timezone: America/Denver. This is a review candidate, not design or deployment approval.

[Standalone gallery](review.html). Each image opens at its original size.

## 1. Data Sources overview

![Data Sources overview](01-data-sources.png)

## 2. ForeverDB configured limits

![ForeverDB configured limits](02-foreverdb-limits.png)

## 3. Everloot configured limits

![Everloot configured limits](03-everloot-limits.png)

## 4. TheWoWDB refill and burst

![TheWoWDB refill and burst](04-thewowdb-token-bucket.png)

## 5. Editing an approved custom allowance

![Editing an approved custom allowance](05-edit-custom-allowance.png)

## 6. Synthetic provider-reported remaining quota

![Synthetic provider-reported remaining quota](06-provider-reported-quota.png)

## 7. Application-estimated remaining quota

![Application-estimated remaining quota](07-application-estimated-quota.png)

## 8. Persistent HTTP 429 cooldown after saving

![Persistent HTTP 429 cooldown after saving](08-http-429-cooldown.png)

## 9. Recovery job waiting for quota

![Recovery job waiting for quota](09-recovery-waiting-for-quota.png)

## 10. Narrow administration at 390 pixels

![Narrow administration at 390 pixels](10-mobile-administration.png)
