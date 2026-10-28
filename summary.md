# Bug investigation summary

**30 reports investigated: 17 bugs found, 8 expected behaviors, 5 unresolved.**

Reproduction was recorded for 29 cases, including narrowed or partial claims; one was not reproduced. The table and individual reports explain those boundaries.

Reproduction means the behavior was observed in the recorded environment, sometimes reconstructed—not necessarily the reporter's exact setup. It does not automatically establish a bug. Each report contains the source revision, filenames, line numbers, function names, reproduction and debugging process, controls and limitations. The [prompt guide](prompts/README.md) explains the saved instructions; only the latest shared protocol is included.

| Bug ID | Issue | Short description | Current status | Reproduced? | Report |
|---|---|---|---|---|---|
| B1841218 | [Lodash #1801](https://github.com/lodash/lodash/issues/1801) | `merge` mutates a source through shared array elements. | Bug found | Yes | [Read report](reports/B1841218.md) |
| B1841570 | [Lodash #2137](https://github.com/lodash/lodash/issues/2137) | `cloneDeep` retains original values inside nested Maps. | Bug found | Yes | [Read report](reports/B1841570.md) |
| B1842324 | [Lodash #286](https://github.com/lodash/lodash/issues/286) | Chained `union` returns a wrapper; `.value()` extracts the array. | Expected behavior | Yes | [Read report](reports/B1842324.md) |
| B1843993 | [Lodash #4400](https://github.com/lodash/lodash/issues/4400) | Trailing debounce initially returns undefined, then the last invocation's result. | Expected behavior | Yes | [Read report](reports/B1843993.md) |
| B1845051 | [Lodash #5475](https://github.com/lodash/lodash/issues/5475) | Historical Deno requires import mappings for compatible TypeScript declarations. | Expected behavior | Yes | [Read report](reports/B1845051.md) |
| B1845523 | [Lodash #5985](https://github.com/lodash/lodash/issues/5985) | `sumBy` returns a singleton boolean despite its documented numeric return type. | Bug found — documentation/runtime mismatch | Yes | [Read report](reports/B1845523.md) |
| B1845623 | [Lodash #6084](https://github.com/lodash/lodash/issues/6084) | Cloning a Vue-proxied Map loses entries in Node/jsdom; required Proxy support is unclear. | Unresolved | Yes | [Read report](reports/B1845623.md) |
| B2108616 | [Moment #3878](https://github.com/moment/moment/issues/3878) | `utcOffset` mistakes a date fragment for a timezone offset. | Bug found | Yes | [Read report](reports/B2108616.md) |
| B2108664 | [Moment #3920](https://github.com/moment/moment/issues/3920) | RFC parsing replaces nonzero numeric timezone offsets with zero. | Bug found | Yes | [Read report](reports/B2108664.md) |
| B2109128 | [Moment #4349](https://github.com/moment/moment/issues/4349) | Australian week-start setting differs from CLDR 32; governing requirement is unclear. | Unresolved | Yes | [Read report](reports/B2109128.md) |
| B2109889 | [Moment #5043](https://github.com/moment/moment/issues/5043) | Updating an unknown locale leaves its abbreviation undefined. | Bug found | Yes | [Read report](reports/B2109889.md) |
| B2109908 | [Moment #5060](https://github.com/moment/moment/issues/5060) | Date-dependent rounding reports 44 days as two months, contrary to the historical day-range documentation. | Bug found — API/docs mismatch | Yes | [Read report](reports/B2109908.md) |
| B2109984 | [Moment #5132](https://github.com/moment/moment/issues/5132) | `YYYY-WW` mixes calendar year with ISO week; `GGGG-WW` gives the intended label. | Expected behavior | Yes | [Read report](reports/B2109984.md) |
| B2110241 | [Moment #5373](https://github.com/moment/moment/issues/5373) | `DDDo` formats day of year; `Do` formats day of month. | Expected behavior | Yes | [Read report](reports/B2110241.md) |
| B2110444 | [Moment #5569](https://github.com/moment/moment/issues/5569) | Official introduction incorrectly promises local mode for offset-free `parseZone` input. | Bug found — documentation | Yes | [Read report](reports/B2110444.md) |
| B2110563 | [Moment #5692](https://github.com/moment/moment/issues/5692) | Hindi month spellings fail to match; format selection can choose an invalid candidate. | Bug found | Yes | [Read report](reports/B2110563.md) |
| B2110581 | [Moment #5709](https://github.com/moment/moment/issues/5709) | Strict ISO parsing accepts supported `YYYYMM`; `701901` means January 7019. | Expected behavior | Yes | [Read report](reports/B2110581.md) |
| B1841709 | [Lodash #2274](https://github.com/lodash/lodash/issues/2274) | Webpack 2 beta emits invalid JavaScript for imported shorthand properties. | Bug found — Webpack transformation | Yes — reconstructed build | [Read report](reports/B1841709.md) |
| B1845594 | [Lodash #6057](https://github.com/lodash/lodash/issues/6057) | `range` infers a descending step, contrary to the unqualified documented default. | Bug found — documentation | Yes — range; IDE claim unverified | [Read report](reports/B1845594.md) |
| B1843047 | [Lodash #3515](https://github.com/lodash/lodash/issues/3515) | Numeric inputs sum correctly; intentional string concatenation does not resolve the missing database/driver/input types. | Unresolved | Narrowed string symptom only; database path missing | [Read report](reports/B1843047.md) |
| B1844953 | [Lodash #5372](https://github.com/lodash/lodash/issues/5372) | `keyBy` coerces function results into keys; equal keys keep the last value. | Expected behavior | Yes | [Read report](reports/B1844953.md) |
| B2110102 | [Moment #5240](https://github.com/moment/moment/issues/5240) | Bengali regular-expression range error did not recur in controlled script-loading/encoding tests. | Unresolved | No — original IE/Edge runtime and bundle missing | [Read report](reports/B2110102.md) |
| B2108550 | [Moment #3818](https://github.com/moment/moment/issues/3818) | Official rounding test assumes elapsed-day preservation across date-dependent calendar-month decomposition. | Bug found — test expectation | Yes — reconstructed browser/clock | [Read report](reports/B2108550.md) |
| B1622708 | [Day.js #2802](https://github.com/iamkun/dayjs/issues/2802) | London's zero-offset conversion leaves UTC/backing-Date inconsistency in the MUI calendar pipeline. | Bug found — narrowed symptom | Narrowed browser reproduction; literal Thursday label unverified | [Read report](reports/B1622708.md) |
| B1622927 | [Day.js #3025](https://github.com/iamkun/dayjs/issues/3025) | Passing a Day.js instance directly to Moment is unsupported; missing calendar fields default. | Expected behavior | API reproduced; CSV application missing | [Read report](reports/B1622927.md) |
| B1622889 | [Day.js #2985](https://github.com/iamkun/dayjs/issues/2985) | ISO durations retain raw components, contradicting documented getter/token ranges. | Bug found — documentation/API mismatch | Yes — browser and Node | [Read report](reports/B1622889.md) |
| B1622943 | [Day.js #3042](https://github.com/iamkun/dayjs/issues/3042) | Object-duration subtraction omits weeks and loses whole-second milliseconds. | Bug found | Yes | [Read report](reports/B1622943.md) |
| B1032456 | [Zod #3969](https://github.com/colinhacks/zod/issues/3969) | A skipped type-changing transform sends a string to a number-typed outer refinement. | Bug found | Yes | [Read report](reports/B1032456.md) |
| B1033327 | [Zod #4903](https://github.com/colinhacks/zod/issues/4903) | Root/subpath declaration identities diverge in the SDK consumer; legacy-v3 support obligation is unclear. | Unresolved | Yes — SDK compile regression | [Read report](reports/B1033327.md) |
| B1032846 | [Zod #4394](https://github.com/colinhacks/zod/issues/4394) | Beta discriminated-union types expose `.options`, but runtime omits it. | Bug found | Yes — runtime/type mismatch | [Read report](reports/B1032846.md) |

`reports/` contains standalone Markdown snapshots. Source checkouts, environments and raw experiment logs remain in the local investigator workspace and are not included in this repository. Source references in reports are relative to those workspaces.

`prev/` preserves the repository's previous files unchanged.
