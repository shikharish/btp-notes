The historical website can lose its intended tooltip bounds because it looks up `.ql-container` before Quill adds that class. The lookup returns `null`; the tooltip then uses `document.body`. Selecting the first word makes the tooltip extend left of the editor, and a clipping ancestor hides that portion. The original React Editor component and published Quill 2.0.2 reproduce this mechanism in Chrome, with two controls that retain editor confinement.

**Outcome: Bug found, narrowed to the historical website's bounds-selector initialization.** Negative `style.left` alone is expected with body bounds and is not evidence of a core positioning defect. The reporter's custom dialog HTML/CSS/options and exact deployed website revision remain unavailable; this investigation does not establish that the dialog uses the same selector mistake.

## Observation and expectation

The original report (2024-06-17, author reuse-ay) describes selecting “Quill” on quilljs.com and clicking the link toolbar button; a second screenshot shows a custom dialog. It expects tooltip confinement to the editor, says `left` can become negative, and identifies Quill 2.0.2 for the dialog. Original screenshots are saved as `evidence/original-website.png` and `evidence/original-dialog.png`; both visibly show the tooltip extending beyond the visible left content edge. They do not reveal initialization options, DOM structure, or computed bounds.

The original report already supplied the negative-left hint and suggested `.ql-container` as the desired boundary. No discussions, comments, later code, fix commits, or dataset outcome labels were consulted. An initial environment command accidentally listed parent-workspace filenames due to an omitted workdir; no parent file contents, sibling investigations, or answers were read. Subsequent work stayed within this case.

Historical documentation at `experiments/source/packages/website/content/docs/configuration.mdx:44–48`, heading `bounds`, explicitly defaults to `document.body` and promises left/right confinement within a supplied element or selector. The historical homepage nevertheless explicitly requests its own editor as boundary. That requested configuration is what fails to take effect; the core body fallback itself agrees with the documented default.

## Source and environment

- Original provenance: `input/issue.md`, `input/original.json`, `input/provenance.json`, `input/run.json`. Original URL: https://github.com/slab/quill/issues/4256 . No issue discussion was fetched.
- Tag `v2.0.2` points via annotated tag `3cae6060b4164abceb0611062af30778a8a090d3` to commit **`cc898efe9f5662baeadf18dfd2ccca56a3284a7e`**. This matches npm package `gitHead`. Raw metadata: `evidence/tag.json`, `evidence/tag-object.json`, `evidence/npm-quill-2.0.2.json`.
- Exact source tarball is preserved in `evidence/source.tgz`, extracted unchanged to `experiments/source/`. Published package tarball is `evidence/quill-2.0.2.tgz`, extracted to `experiments/published/`. The executed editor is its `dist/quill.js` with `dist/quill.snow.css`; runtime reports `Quill.version === '2.0.2'`.
- npm SHA-1 `5b26bc10a74e9f7fdcfdb5156b3133a3ebf0a814` matched; SHA-512 integrity matched exactly (`evidence/integrity-check.txt`). SHA-256 artifacts/bundle/style hashes are in `evidence/sha256.txt`. GitHub tag is unsigned; metadata records that fact.
- Actual execution: macOS, Node **22.23.2**, Playwright **1.56.1**, installed Google Chrome **156.0.8078.48**, headless 1200×800 viewport. Reporter only specified Chrome, without version/OS. This is a contemporary browser reconstruction, not the reporter's machine.
- Original React `Editor.jsx` and `NoSSR.jsx` execute unchanged, bundled with esbuild **0.21.5**, React/react-dom **18.2.0** (also the historical source lock versions). Runtime package lock is `experiments/runtime/package-lock.json`.
- Editor UMD is prebuilt and self-contained; it does not use fresh npm resolution of core dependencies. Historical source lock records lodash-es 4.17.21, parchment 3.0.0, quill-delta 5.1.0, eventemitter3 5.0.1.

## How I reproduced and debugged it

From this case directory, run:

```sh
npm ci --prefix experiments/runtime --no-audit --no-fund
node experiments/reproduce.cjs > evidence/browser-run.log 2>&1
node experiments/website.cjs > evidence/website-run.log 2>&1
```

The scripts use the installed `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`. No external page is visited during reproduction. Chrome startup under the filesystem sandbox initially aborted; the same local script ran with authorized OS escalation. The raw setup failure is retained in `evidence/browser-launch-sandbox-failure.log`. Both final commands exited **0**. `website.cjs` also asserts that the historical-selector case falls back to body and both controls resolve the editor and geometrically fit inside it; assertion failure exits nonzero. Browser closes after each script.

First I ran the published editor with Snow theme, one link toolbar button, text “Quill is a rich text editor.”, selection index 0/length 5, and an actual Playwright toolbar click. Selection is established through Quill's real selection API, rather than simulated pointer dragging. `reproduce.cjs` wraps the actual tooltip `position` method only to log inputs/outputs and calls the original method unchanged; no positioning algorithm is copied. It repeats each opening after Escape.

Then I read the historical homepage and found its bounds selector depends on a class created by Quill itself. `website.cjs` executes the actual historical React Editor component and NoSSR wrapper with the exact Snow homepage selector. It logs real DOM selector resolution and inspects resolved Quill options and the tooltip's actual boundary element. The baseline plain editor div lacks `.ql-container` at construction; the two controls alter only the selector or the div's initial class.

This is the actual original component → Quill constructor → toolbar handler → editor selection → tooltip DOM/CSS pipeline, not a reimplementation. It is a focused integration harness, **not a full Next.js build or a replay of deployed quilljs.com**: the page shell is a 600px editor at x=288, with a clipping ancestor; original page fonts/content/styles, syntax module, and full toolbar are replaced by standard Snow styling and a single link button. Clipping CSS is an explicit reconstruction from the screenshot, not recovered reporter CSS. Neither boundary resolution nor its demonstrated controls depend on the syntax module or other toolbar buttons.

## Decisive evidence and controls

All measurements below are browser observations from `evidence/website-results.json`; coordinates are viewport pixels.

| Input to original Editor component | Resolved `q.options.bounds` | Actual tooltip bounds | CSS left | Tooltip viewport left/right | Editor left/right |
| --- | --- | --- | --- | --- | --- |
| Historical `#snow-container .ql-container`, plain div | null | BODY | -124.492px | 164.515625 / 471.96875 | 288 / 888 |
| Stable `#editor`, same plain div | editor element | editor DIV | -1.00781px | 288 / 595.453125 | 288 / 888 |
| Historical selector, initial `className="ql-container"` | editor element | editor DIV | -1.00781px | 288 / 595.453125 | 288 / 888 |

In the baseline, the construction-time query returns false with editor `className=""`. The same selector matches after initialization with `className="ql-container ql-snow"`; it is not re-resolved. In the stable-selector control, construction-time query returns true before the class exists. In the preclass control it returns true with `className="ql-container"`. The first query in each trace occurs before React rendering and is false in every case; the construction-time query is the next one. Screenshots `evidence/website-historical-selector.png`, `evidence/website-stable-selector.png`, and `evidence/website-preclass.png` show the baseline's clipped input/label and the fully visible controls. The slight negative CSS left in passing controls aligns the actual rectangle exactly to editor x=288; sign alone is an invalid failure test.

## Verified source trace

Paths below refer to unchanged pinned source; the executed published JS is minified on line 2, so these TypeScript/JSX line numbers must not be mistaken for bundle offsets. Behavioral equivalence is checked by the actual published runtime's option resolution, DOM query trace, and tooltip measurements.

| Link in causal chain | Source path and verified lines | Function/component and effect |
| --- | --- | --- |
| Intended boundary input | `experiments/source/packages/website/src/pages/index.jsx:313–325` | Homepage Snow Editor passes `bounds: '#snow-container .ql-container'` at 315. The full editor uses the same class-dependent form at 330–332. |
| DOM before construction | `experiments/source/packages/website/src/components/Editor.jsx:27–42` | `Editor` layout effect constructs Quill at 28; JSX at 40 renders a plain div and spreads props. Homepage supplies no initial ql-container class. |
| Ordering | `experiments/source/packages/quill/src/core/quill.ts:195–206` | `Quill.constructor` expands config at 196, then adds `ql-container` at 206. |
| Failed selector resolution | `experiments/source/packages/quill/src/core/quill.ts:768–771,872` | `resolveSelector` immediately calls `document.querySelector`; `expandConfig` resolves `config.bounds` once. No match produces null. |
| Fallback becomes actual state | `experiments/source/packages/quill/src/themes/snow.ts:106–112`; `experiments/source/packages/quill/src/ui/tooltip.ts:14–17` | `SnowTheme.extendToolbar` passes options.bounds to `SnowTooltip`; `Tooltip.constructor` sets `boundsContainer = boundsContainer || document.body`. |
| User trigger | `experiments/source/packages/quill/src/themes/snow.ts:128–141`; `experiments/source/packages/quill/src/themes/base.ts:252–271` | Snow link handler reads selected text; `BaseTooltip.edit` displays editor and passes saved selection bounds to `position`. |
| Coordinate conversion | `experiments/source/packages/quill/src/core/quill.ts:462–478` | `Quill.getBounds` converts selection viewport bounds to editor-relative coordinates. |
| Negative left and absent editor clamp | `experiments/source/packages/quill/src/ui/tooltip.ts:32–50` | `Tooltip.position` centers using reference.left + reference.width/2 − offsetWidth/2, then clamps against boundsContainer's viewport rectangle. With body bounds x=8..1192, tooltip x≈164.516 is legal, although outside editor x=288. |
| Visual placement | `experiments/source/packages/quill/src/assets/core.styl:12–18`; `experiments/source/packages/quill/src/assets/base.styl:67–69` | Editor is positioned relative; tooltip is absolute. Negative editor-relative left therefore moves it outside editor. A clipping ancestor hides that region. |

For the measured selection, reference left=16, width=26.015625, tooltip offsetWidth=307. The centering expression is `16 + 26.015625/2 - 307/2 = -124.4921875`. Positioning does not compare to editor x=288 when `boundsContainer` is body. The controlled selector changes affect that single state and restore the editor clamp without changing the positioning implementation.

## Experiment notes and challenges

1. **Before experiment 1:** hypothesis: default body bounds explain negative left; supplying the editor should contain a wide editor. **Actual:** exactly observed, on first and repeated openings. Raw results: `evidence/browser-results.json`; screenshots have names matching each case. This showed a default-options negative left is documented behavior and could not alone justify Bug found.
2. **Before experiment 2:** hypothesis: a clipping ancestor hides left-overflowing default tooltip but not the same wide editor with explicit bounds. **Actual:** numeric coordinates unchanged; `default-clipped.png` clips label/input, `editor-bounds-clipped.png` contains it. This resembles the original screenshot but does not recover the dialog's CSS.
3. **Before experiment 3:** hypothesis from original source: homepage's class-dependent selector fails during the original component's initialization. **Actual:** original selector resolves null during construction and true afterward; real bounds are BODY. Both already-present selector and already-present class controls resolve the editor and contain the tooltip. The final run asserts all three outcomes and exits 0. This changes the conclusion from a merely explained default to a demonstrated historical website integration defect.
4. **Counterexample retained:** the 260px configured editor is narrower than the ~307.453px tooltip and cannot contain it. Snow CSS at `src/assets/snow/tooltip.styl:9–22` uses nowrap and a 170px input; `Tooltip.position` translates rather than resizing. This supplementary width limit is not counted as the assigned failure, because the report does not supply those dimensions/options.
5. **First-open label challenge:** `BaseTooltip.edit` sets data-mode after positioning (271), changing the pseudo label (`snow/tooltip.styl:11–12,48–49`). Here it changes width only 0.25px; reopening preserves the large baseline displacement. It does not account for the demonstrated loss of editor bounds.
6. **Instrumentation correction:** an early query logger persisted through `page.setContent`, nesting wrappers and producing duplicate query entries in later controls. That raw trace is retained in `evidence/website-results-nested-query-wrapper.json`. The runner now resets `document.querySelector` to the native prototype method before each fixture; the final `website-results.json` contains the clean traces. Geometry and resolved-bound conclusions were unchanged.

## Limits

The demonstrated defect is in the pinned historical website integration, using original component code and published Quill 2.0.2. The issue provides no deployment SHA, so it is unknown whether the June 17 live website used exactly this May 13 tag. Original screenshots qualitatively agree, but exact fonts, pixel dimensions, and dialog configuration were not recoverable. The custom dialog could instead omit bounds or have different clipping/layout; attributing its cause requires its initial DOM, CSS and Quill options. No claim is made that every negative left is wrong, and no production changes were made.

## Coordinator verification

Independently ran `node experiments/coordinator-website.cjs` in local headless Chrome, exit 0. This replay differs from the saved worker harness only in generated bundle and evidence output filenames, preserving the original logs/screenshots. The original class-dependent selector again resolves null/BODY and positions the tooltip left of the editor; both stable-selector and initial-class controls resolve the editor and contain it. Fresh evidence: `evidence/coordinator-website-results.json`, `evidence/coordinator-website-run.log`, and three `evidence/coordinator-website-*.png` screenshots. Verified the original homepage selector, plain Editor div/layout effect, constructor configuration-before-class order, one-time selector resolution, body fallback and positioning formula against pinned source. The verdict is confined to that historical integration; exact live-site deployment and custom-dialog configuration remain unverified.
