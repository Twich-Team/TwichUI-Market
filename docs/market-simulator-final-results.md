# Final simulator verification and release status — November 23, 2026

**The simulator environment is restored. The complete required suite ran and failed its unchanged assertions. The coordinated release is held; production remains healthy and unchanged. The final packaging remains25 Market data addons.**

## Exact executed source and environment

| Component | Exact identity |
| --- | --- |
| Tested addon | `8aa42c16b6896555cd3bc857cf7ab0482dbf4116` |
| Tested addon tree | `fb0983bbfcd9742bd3b9c4e2d2e1f56eca81a32a` |
| Market candidate | `e48e0eee828355ac1ed95c5be3eec46b032f9e82` |
| Market candidate / tested preview tree | `e1b7b9b1b60ea714d7a333f281512bbe46064c7a` |
| Tested Market PR preview | `1c29acd121f3b5c1c84fdf0b89483cb93e11210a` |
| Addon main, rechecked after verification | `5824b73eaf169cf60e7eea06391aed7d392a57e1` |
| Market main, rechecked after verification | `3f0421a2221e424df751b963f5b66b445e319018` |
| Full run / job | [45187769049 /137737762923](https://github.com/Twich-Team/TwichUI/actions/runs/45187769049/job/137737762923) |
| Disposable runner | Ubuntu24.04.5, image `ubuntu-24.04` / `20261116.133.1`, AWS us-east-1 |
| Runtime | glibc2.39; Bubblewrap0.9.0; libvulkan1 `1.3.275.0-1build1`; Mesa Vulkan `25.2.8-0ubuntu0.24.04.5` |
| Simulator | Unmodified wow-ui-sim v0.1.37 Forever |
| Pinned simulator archive SHA256 | `66e9afa95b61619fb15af335c74a8e9e2b0cc645d9bbf078dca492ec8bf8dfae` |
| Pinned UI source | `ca8368f2f2380cbe696854f7f2646387c278a61b` |

The exact command was:

```sh
bash tests/run.sh full --profile cloud --jobs 2 --sim-jobs 1 --measure
```

Source was clean and unchanged before/after. Actual execution took **3328.763seconds**. Final command and workflow exit status was **1 / FAIL**. This is execution time, not modeled scheduler time.846 Lua files passed syntax;328 offline modules, including244 Python methods, passed. No catalog was omitted.

## Every executed catalog

| Catalog | Native launches | Structured checks | Raw passed markers | Raw failed markers | Catalog exit / result |
| --- | ---: | ---: | ---: | ---: | --- |
| lab-guard | 0 | 0 | 0 | 0 | 0 / PASS |
| smoke | 2 | 0 | 0 | 0 | 0 / PASS |
| interact | 4 | 244 | 243 | 1 | 0 / PASS |
| diagnose | 6 | 101 | 101 | 0 | 0 / PASS |
| auctionproof | 13 | 1547 | 1544 | 3 | 0 / PASS |
| auctionpreview | 52 | 7290 | 7289 | 1 | 0 / PASS |
| workshop | 49 | 26178 | 24150 | 2028 | 1 / FAIL |
| testlab | 9 | 229 | 229 | 0 | 0 / PASS |
| settings | 62 | 1090 | 1090 | 0 | 0 / PASS |
| reminders | 36 | 3984 | 3983 | 1 | 1 / FAIL |

Totals:233 native launches,40,663 structured assertion executions,38,629 raw passed markers and2,034 raw failed markers. **Eight catalogs pass; Workshop and Reminders fail.** Structured markers do not count every guard, construction, replay or screenshot assertion. Zero structured markers in smoke does not mean it has no assertions.

Raw failed counts include deliberately wrong controls: passing interact, auctionproof and auctionpreview explicitly expect those failures. The generic report's filename-only negative-control tag misses two named integrated auction controls; the original catalog verdict correctly accepts them. Workshop has1,986 failed markers outside its `wrong` launch; its wrong launch has42 failures, so the independent guard requiring only the doctored check to fail also correctly fails. These are repeated occurrences across poses, not2,034 distinct bugs. Reminders has one failed assertion naming ten artwork IDs.

The artifact contains516 PNG files and **zero GPU-adapter panics**. Native launch/rendering works; a successful launch is not represented as suite success. The job-specific AppArmor profile was removed successfully. The earlier pre-Mesa TestLab width failure is retained; TestLab passes in this corrected run without any product/assertion change. Its earlier standalone width cause is not asserted from one rerun.

[Exact report and artifact identity](evidence/market-simulator-unblock/full-final-summary.json), [lossless original report](evidence/market-simulator-unblock/full-final-report.json.gz), [all unique failed assertion lines and occurrence counts](evidence/market-simulator-unblock/full-final-failed-assertions.json.gz).

## Why testing worked previously and what changed

The binary and Bubblewrap isolation were introduced together by `f2a23cc3349cffd4b0f367871f1bb24adabc70b0` on October30. The version/archive digest and `--unshare-all` have not changed. Previous prepared environments already supplied compatible libc, software Vulkan and namespace permissions. The documented native host was Ubuntu26.04 WSL2; historical cloud report metadata does not establish its exact OS/kernel/AppArmor configuration.

A real archived full-cloud pass exists for `febed289d7db429d00d02fcff73cdbf262d541c2`, with raw report/console committed at `4e08bdceec5d717ffe5855bd8351bd19bd06ae88`:247 modules,192 launches,30,552 structured checks,2446.279seconds, PASS. The documented L3 full pass at `9e00d8e9a05a24461841514b9c717d3ca3c985b4` is an older November16 source and its raw artifact is not committed. These are not claims that recent routine offline GitHub runs were full runs. Historical failed runs remain failed. [Evidence grades and full history](market-simulator-historical-audit.md).

The new workflow was incomplete. Its Ubuntu22 switch `f7f42425ff53d0057c9c4799cbd85ca7791b9f06` avoided a namespace restriction but supplied incompatible glibc. Ubuntu24 needed the approved executable-specific AppArmor `userns` permission. The workflow also used the wrong installation-variable handoff and omitted documented Mesa drivers. Those are introduced workflow errors, not an upstream binary upgrade.

The correction uses the existing workflow and disposable Ubuntu24 runner, the supported `WOWSIM_INSTALL` handoff and documented Mesa packages. The temporary profile attaches only to that job's exact Bubblewrap executable. Global `apparmor_restrict_unprivileged_userns` remains1. Original read-only mounts, hidden home/game, network isolation and all assertions/catalogs remain. No production security setting, simulator binary, loader, framework or permanent runner was changed.

## Remaining failure causes and required correction

**Workshop:** old exact expectations conflict with already integrated main behavior. Examples are the unsupported-outcomes assertion after outcomes became supported, the default layout assertion after an editable heading was added, direct tooltip checks requiring craft/unknown recommendation lines after those lines were deliberately suppressed, icon-bearing preview strings and the old “Add optimized plan” label. Positional designer interactions then select the wrong row after the heading is inserted.

- `208e0f9e628c75656f5e78d84464dec306edcc69` (outcomes) and `db11aebf690a7cf73ab9f07e034b3ba2390c9142` (sale-only tooltip recommendations) entered main through [PR63](https://github.com/Twich-Team/TwichUI/pull/63), merge `5dc8ee7fd8a92878996b2ddbea356af81d3ddafd`, November19 16:43:38UTC.
- `bc787b14aa27270d3557cf1efb36a491e68efbd0` (editable heading) entered main through [PR84](https://github.com/Twich-Team/TwichUI/pull/84), merge `653e128ba59c302c6cc4e13cc52d1e9b1f320700`, November20 20:25:25UTC.
- These pure tooltip/layout contracts and their simulator scenario files are unchanged between current main and this candidate. Their contradictions are independent of Market container splitting. Some additional Advisor/filter pose mismatches remain unclassified as fixture versus product defects; they are not waived or all called harmless cosmetic failures. Those include carried identities expected3/actual4, combined filters expected1/actual0, the reagent filter expected item3371/actual159, and an auction-advice pose showing “No bag copies.” They require diagnosis against explicit fixture inputs.

**Reminders:** `tools/simlab/scenarios/reminders.lua:555` assumes every art texture filename contains its logical artwork ID. Main's approved catalog now maps IDs such as `art-tabard` to `npcs\tabard`; the substring assumption is false for ten new entries. Offline gallery tests independently check these mappings and the actual32/64-pixel files. The catalog addition `53287ec4c7a955a2b7e3a01d1e40c28b463460fe` entered main through [PR128](https://github.com/Twich-Team/TwichUI/pull/128), merge `f21db0aa1c0a04bad532b30d70c39a001fc7a6d9`, November22 19:16:35UTC. It is not a missing-Vulkan or missing-game-assets finding.

**Required next work:** reconcile the existing scenario contracts with these approved main changes, retain exact economic checks and every independent negative control, and resolve the remaining Advisor/filter expectations before rerunning the same full command. Blindly replacing expected output with observed output would not establish correctness. Current assertions and approved main features were preserved. The release is stopped at this failed full-regression gate; no extra architecture or environment campaign is started.

The full release/high-risk policy already existed by `003d0bba9165473aa079882934b6f276be7279f4` on November16 and the owner explicitly requested this full command. It is not a newly invented release requirement. Actual WoW Forever remains an owner-directed limitation, not another added gate. Cloud testing excludes game-asset rendering, actual client fonts/visual fidelity, combat/taint, secure actions, real message transport and reload persistence. No native Forever acceptance is claimed.

## Completed independent verification and preserved release state

All nine Market candidate CI checks pass, including749 PostgreSQL tests, website, Windows installation/upgrade, picker, prepared publication/consumption, updater checks and repeated Windows comparison. The PR preview tree exactly equals candidate source. This is **PR integration evidence**, not a post-merge canonical installer or newly signed beta.12 acceptance. [Exact check IDs/URLs](evidence/market-simulator-unblock/final-market-ci-proof.json).

The candidate backend image `sha256:2de5aa76348ed3977db928464fb72a212b42c57f7142c923e35bda7ff12237cb` passed193 focused checks in an isolated market_test database. All65 modules match source at both image locations. The temporary database is stopped. Compose rendering preserves API environments and the repaired collector image, and prepares replacement of only api/local-api. **None of this was deployed.**

A private seven-runtime-folder addon ZIP passes the existing archive validator. Its shipped runtime is identical to8aa42c1, which changes only CI provisioning after c872d027. It remains an internal, uncertified candidate pending full verification and merge. No public addon tag/release was created. [Prepared-only image/archive/Compose receipts](evidence/market-simulator-unblock/prepared-only-release-work.json).

The approved25-addon benchmark decision remains unchanged: larger-fixture current physical-load CPU p95/max4.326/5.499ms, no load above16ms in the retained campaign. These are offline host results, not Forever frame measurements. [All600 samples, memory/CPU tradeoffs and retained failed serialization evidence](performance-packaging-final.md).

## Merges, deployment, published version and local action

No coordinated Market46/47/48/49/50 or TwichUI131/136 PR was merged. No coordinated merge commit exists. The ordered Market ancestry and all Windows fixes remain in PR50; reader131 precedes136. Independent addon main141/142 and collector repair51 are preserved. Temporary Codec Probe135 and chart117 were not merged by this task. Main hashes are the exact values above.

The API remains the prior approved image `sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c` (prior Workshop module source `29fa95b569cc3834ed2c17490d251a2a4ac6b4f5`). The collector remains repaired image `sha256:ec94420d36baf501d312f3cbc85e38b77222e5b5bff92b76aae82dd8df95575d`, associated with repair PR51/main3f0421a. No prepared backend promotion or database change occurred.

At14:54:27UTC, HTTPS health is200, house114 last succeeded at14:50:03.921859UTC, both feeds and the market have zero failures, and the300-second schedule is unchanged. All eleven original production container IDs/images match the preflight. Verification made zero provider requests and no production writes. Previous API/collector images, signed installers and established database/generation recovery paths are retained. [Actual final production evidence](evidence/market-simulator-unblock/production-final-verification.json).

The private update channel still publishes **Companion2.0.0-beta.11**, source `b39a35c01676b50dbc159f4793e0ad547676acfc`, installer SHA256 `84dacad168dc212d8dda7d06f15ddc5a918f170ba1af0e9ece4e6373cd883129`. **Beta.12 is prepared but not signed or published and is not offered to installed users.** Post-merge source verification, deployment, final-main Windows build, signing, actual signed SDK acceptance and publication remain unexecuted.

No local PC/WoW action is required for this held release. Nothing was force-installed or updated. The one remaining release blocker is the unsuccessful complete simulator regression, not collector health or the selected25-addon architecture.
