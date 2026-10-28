# Bug investigation summary

**17 reports investigated: 8 bugs found, 7 expected behaviors, 2 unresolved. All 17 reported behaviors were reproduced.**

Reproduction means the behavior was observed in the recorded environment, sometimes reconstructed—not necessarily the reporter's exact setup. It does not automatically establish a bug. Each report contains the source revision, filenames, line numbers, function names, reproduction details and limitations.

| Bug ID | Issue | Short description | Current status | Reproduced? | Report |
|---|---|---|---|---|---|
| B1841218 | [Lodash #1801](https://github.com/lodash/lodash/issues/1801) | `merge` mutates a source through shared array elements. | Bug found | Yes | [Read report](reports/B1841218.md) |
| B1841570 | [Lodash #2137](https://github.com/lodash/lodash/issues/2137) | `cloneDeep` retains original values inside nested Maps. | Bug found | Yes | [Read report](reports/B1841570.md) |
| B1842324 | [Lodash #286](https://github.com/lodash/lodash/issues/286) | Chained `union` returns a wrapper; `.value()` extracts the array. | Expected behavior | Yes | [Read report](reports/B1842324.md) |
| B1843993 | [Lodash #4400](https://github.com/lodash/lodash/issues/4400) | Trailing debounce initially returns undefined, then the last invocation's result. | Expected behavior | Yes | [Read report](reports/B1843993.md) |
| B1845051 | [Lodash #5475](https://github.com/lodash/lodash/issues/5475) | Historical Deno requires import mappings for compatible TypeScript declarations. | Expected behavior | Yes | [Read report](reports/B1845051.md) |
| B1845523 | [Lodash #5985](https://github.com/lodash/lodash/issues/5985) | `sumBy` preserves a singleton boolean instead of coercing it to a number. | Expected behavior | Yes | [Read report](reports/B1845523.md) |
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

`reports/` contains standalone Markdown snapshots. Source checkouts, environments and raw experiment logs remain in the local investigator workspace and are not included in this repository. Source references in reports are relative to those workspaces.

`prev/` preserves the repository's previous files unchanged.
