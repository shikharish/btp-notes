The reported missing and unwrapped category labels are reproduced in ECharts 6.0.0 and are **expected behavior** for the recovered option. `overflow` needs an explicit text width. Separately, the default category-label interval skips labels to avoid overlap; the long category influences the interval even when it is itself skipped. Setting only `overflow` cannot force all categories to appear or supply a wrapping boundary.

## Original report and scope

The report calls the property `axisLabe` in its prose (and misspells “neither”). The original reproduction actually uses the correctly spelled `xAxis[0].axisLabel`, with only `{ overflow: "break" }`. It contains the categories `Mon`, `This is a very long name`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`, a value y-axis, default grid, and the original seven bar values. `experiments/original-option.js` preserves the decoded option including its Chinese series name. No replacement scenario was used.

The historical preview’s exact runtime and chart-panel size cannot now be established from the link. The report says “6.0.0 (whatever version runs in your preview sandbox currently)”; this investigation pins the explicit version. The 1574×830 attachment size describes the screenshot, not necessarily the chart panel. I reproduced the narrowed symptom at a 700×500 chart size. A 1574-pixel chart is a separate size control. I did not inspect the remote attachment pixels or the live, potentially changed editor.

## Pin and environment

- ECharts tag and npm `gitHead`: `52104f7daefb8d01ea809189dab81cadc874ce09` (6.0.0). Tag metadata: `evidence/source-tag.json`; package integrity: `evidence/echarts-metadata.json` and `experiments/package-lock.json`.
- Runtime: unmodified `experiments/node_modules/echarts/dist/echarts.js`, SHA256 `77c1f65da9da7c5960e103e1884470645eff868e2a5d2ceca1ec732118aac8ae`. Original TypeScript source is `evidence/echarts-6.0.0/`; source archive SHA256 `e7116a01d56625ec0ae6b36db081dcb6f2ee4b5239100187754a4826cc5ea5ba`.
- Exact runtime dependencies: zrender 6.0.0 and tslib 2.3.0. Harness: Node v22.12.0, Playwright 1.55.0, lz-string 1.4.4, installed Google Chrome 156.0.8078.48, headless SVG renderer on this macOS host. This is a reconstruction, not Chrome 139/macOS 15.6.1 from the report.
- Historical official docs pinned by report timestamp: `apache/echarts-doc` SHA `7df6fac92f0713508f87a3c2600a23167a21b2b0`, saved in `evidence/docs-revision.json` and `evidence/echarts-doc-7df6fac92f0713508f87a3c2600a23167a21b2b0/`. Revision metadata was used solely to select the documentation snapshot, not investigate fixes/history.

## How I reproduced and debugged it

From this case directory:

```sh
npm ci --prefix experiments
node experiments/decode.cjs
node experiments/run.cjs > evidence/render.log 2>&1
```

The harness launches local Chrome, loads the pinned full ECharts bundle, evaluates the exact decoded option, calls `echarts.init` and `setOption`, and reads the real axis model, generated zrender Text objects/line children, and actual SVG text nodes. Each variant creates a fresh chart. Only animations are disabled; chart configuration is otherwise original except the listed control. It disposes charts and closes the browser. No copied layout algorithm, fake text renderer, or production source edits are involved.

I decoded the link’s raw `code` field after translating URL-safe LZ alphabet characters (`-` to `+`, `_` to `/`). Both the naive raw/URL-parser decoding attempts returned null; no source option existed until that conversion. Initial Chrome launch failed under the filesystem sandbox (SIGABRT/EPERM); launching the local renderer with normal host process permissions succeeded. A harness mistake initially treated the DOM’s named `window.chart` element as an ECharts instance; guarding its `dispose` method fixed setup. These failures are retained in `evidence/browser-initial-failure.log` and `evidence/harness-named-dom-failure.log`; neither is the report symptom.

The controls were motivated by the source hypotheses below; this report records those intentions retrospectively rather than claiming they were written down before the first runs. A final unchanged rerun is predicted to repeat the original Mon/Thu/Sun output and the width-plus-interval wrapping control, establishing recurrence without any source patch.

| Hypothesis / controlled change | Prediction | Observed actual pipeline result |
|---|---|---|
| Original `overflow: break`, 700px chart | Auto interval skips categories; no wrapping boundary | Auto-calculated interval 2, 75px category band; view labels and rendered x-axis Text objects are Mon, Thu, Sun |
| Change overflow alone to truncate / breakAll | Same skipped categories | Both produce Mon, Thu, Sun; generated Text style preserves the requested overflow and has null width |
| Add only interval:0 | All labels emitted; long text stays one line without width | All seven appear, long text unchanged and Text width null |
| Add only width:60 | Auto interval still selects categories using unwrapped measurement | Still Mon, Thu, Sun, interval 2; emitted Text width is 60 |
| Add width:60 and interval:0 | All categories appear; long text wraps by words | Long Text children are `This is a ` / `very long ` / `name`; Wed, Fri, Sat all appear |
| Width:60, interval:0, overflow:truncate | Truncation works once applicable | Long label is `This is a...` |
| Width:60, interval:0, overflow:breakAll | Character wrapping differs from word wrapping | `This is a v` / `ery long na` / `me` |
| Original option at 1574px chart width | More labels selected, but overflow alone still does not wrap | Auto interval 1, band 168.642857px; Mon, Wed, Fri, Sun, long category still skipped |

`autoCalculatedInterval` in the JSON is the algorithm’s diagnostic result, including in explicit `interval:0` variants. It is not the effective configured interval; `viewLabels` and generated SVG show the effective selection. Raw text/coordinates/styles and actual browser version are in `evidence/render-results.json`; console summary and successful command exit are in `evidence/render.log`. SVGs for every variant and screenshots `evidence/original.png`, `evidence/width60_interval0.png` show the actual outputs. Initial screenshot was visually inspected. The final unchanged recurrence run exited 0 and repeated all table results; see `evidence/recurrence-check.json`.

## Source trace (verified original source line references)

Paths below are relative to this case. The executable bundle has different line numbers; the original TypeScript cited here is the matching npm gitHead/tag source, except zrender references come from its exact installed 6.0.0 package.

| Input → responsible function/branch → state/output | Source |
|---|---|
| Category axis defaults to `axisLabel.interval: 'auto'` | `evidence/echarts-6.0.0/src/coord/axisDefault.ts:166–168`, category default option |
| `makeCategoryLabelsActually` reads interval and routes auto to `makeAutoCategoryInterval`, then selects labels | `evidence/echarts-6.0.0/src/coord/axisTickLabelBuilder.ts:185–220` |
| `calculateCategoryInterval` measures every formatted category using font bounding boxes, applies 1.3 width/height factor, computes floor(min(maxW/unitW,maxH/unitH)); this calculation does not pass width/overflow into text measurement | same file `:348–404` |
| `makeLabelsByNumericCategoryInterval` uses step=interval+1 and iterates tick indexes with that stride | same file `:484–537`; interval 2 → indexes 0,3,6 → Mon,Thu,Sun. These selected indexes and labels are directly observed in `labelTextElements` and `viewLabels` |
| `buildAxisLabel` obtains already-filtered `axis.getViewLabels` then creates Text only for those labels, passing text style | `evidence/echarts-6.0.0/src/component/axis/AxisBuilder.ts:1322–1360`, `:1403–1444` |
| `setTextStyleCommon` preserves overflow; `setTokenTextStyle` copies explicitly present width among TEXT_PROPS_SELF | `evidence/echarts-6.0.0/src/label/labelStyle.ts:455–458`, `:524–526`, `:641–646`. Runtime original Text styles have overflow break and null width; controlled styles have width 60 |
| `Text._updatePlainTexts` passes style and possible default overflow area to real parser | `experiments/node_modules/zrender/src/graphic/Text.ts:503–525` |
| `parsePlainText` wraps only if width is non-null and overflow is break/breakAll; otherwise splits only existing newline characters. Truncation likewise requires width | `experiments/node_modules/zrender/src/graphic/helper/parseText.ts:213–249`, `:275–280`. The original string has no newline. Actual interval:0 Text children stay one line; controlled width:60 children wrap/truncate |

Executed bundle correspondence: `experiments/node_modules/echarts/dist/echarts.js:9357` (`parsePlainText`), `:12251` (Text parser invocation), `:35278` (`calculateCategoryInterval`), `:35376` (`makeLabelsByNumericCategoryInterval`). These were read without modifying the bundle.

## Historical expectation and verdict

The pinned docs establish the behavior, beyond merely observing a passing control:

- `evidence/echarts-doc-7df6fac92f0713508f87a3c2600a23167a21b2b0/en/option/partial/text-style.md:37–57`, width/overflow headings: text block width defines the boundary; overflow is available when width is set; break is by word and breakAll by character.
- Same docs `en/option/component/axis-common.md:325–334` declares category label interval default auto and includes the interval explanation at `:1109–1117`: the default strategy avoids overlapping labels, 0 forces all labels, and 2 skips two labels between displayed labels.

Thus the reported failure to wrap without width and omission of short categories under auto interval are documented behavior, reproduced and explained. The width-only counterexample matters: width controls text layout after category selection; it does not automatically replace the selection heuristic. This investigation does not classify a separate width-aware interval feature request as a defect.

No issue comments, timeline, fixes, later implementation, sibling investigations or prior answers were read. A broad search of the historical docs accidentally returned two old, unrelated changelog snippets about interval:0 displaying labels despite overlap; those were not opened or used as verdict evidence. No production fixes or commits were made. Exact historical screenshot pixel matching remains unverified, but no material gap remains for the narrowed behavior and documented expectation above.

## Coordinator verification plan

Before independent rerun: predict the exact recovered option at 700px renders Mon/Thu/Sun, interval 0 emits all seven but leaves the long label unwrapped, width 60 alone retains automatic skipping, and width 60 plus interval 0 emits all seven and wraps the long label into three lines. Independently rerun the original real-rendering harness with separate output paths and additional assertions only, then check the historical width/interval documentation and responsible source branches.

## Coordinator verification result

Independent real-renderer rerun exited 0; all predeclared predictions and added assertions passed. The original and width-only cases emit Mon/Thu/Sun; interval 0 alone emits seven unwrapped labels; width 60 plus interval 0 emits seven labels and wraps the long label into three lines. Verified the pinned docs require width for overflow and document automatic interval omission, plus the actual zrender width gate. Fresh files are under `evidence/coordinator/`, including `render-results.json`, `render.log`, SVGs and two screenshots. The replay changes only evidence output locations and adds post-render assertions; original pipeline remains the same. An initial coordinator setup command used a case-relative path twice and failed before files or rendering were created; corrected the working-directory reference before recording the plan and running.
