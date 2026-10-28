# Custom typography modifier loses its heading margins

**Bug found, narrowed to the original typography 0.5.16 / Tailwind 4.1.11 integration.** The original CSS build emits `.prose-legal` before `.prose`. Chrome computes the test heading's margin-top as **32px**, overriding the custom theme's intended **-72px**. `pointer-events` anywhere inside the legal theme gives the entire class an earlier property-sort key. This takes priority over declaration count, configuration order, and alphabetical order. The result is deterministic; the report's description of an “unpredictable” order is not literal randomness.

The integration breaks the modifier's intended override behavior. The published typography README's “Applying a type scale” (`repo/node_modules/@tailwindcss/typography/README.md:97–138`) requires modifiers alongside `.prose`; “Customizing the CSS” (`:328–386`) describes overriding the generated CSS and configuring each modifier. The core sorter itself behaves as implemented, but applying its property ordering to whole typography components makes an unrelated nested property reverse their cascade relationship. This claim is about that concrete integration failure, not a promise that all arbitrary custom classes follow config insertion order.

## Validation

| Controlled build | Whole-class order | Chrome h2 margin-top |
|---|---|---|
| Original config | legal, base | 32px |
| Reverse config key order | legal, base | 32px |
| Remove only pointerEvents recursively | base, legal | -72px |
| Legal reduced to pointerEvents + negative margin | legal, base | 32px |
| Reduced legal with only negative margin | base, legal | -72px |

Every CSS build exited 0. Browser results are recorded in `evidence/computed.jsonl`; raw DOM and Chrome commands/exit codes are in `evidence/browser-*.html` and `evidence/chrome-*.log`. `evidence/variants.jsonl` records actual CSS offsets. The browser fixture uses the complete generated stylesheet, both original classes, and a non-first h2. The exact original input is built separately in `evidence/node18.css`, so fixture/variant generation does not substitute for the original integration run.

## How I reproduced and debugged it

Commands below run from this case directory (the original README's yarn command is the same CLI pipeline). The installation command was executed inside `repo`; the first original build ran under Node 22.12.0, followed by the reported Node 18.20.7. `cmp evidence/original.css evidence/node18.css` exited 0.

```sh
(cd repo && yarn install --frozen-lockfile --cache-folder ../env/yarn-cache)
env/node18/bin/node repo/node_modules/@tailwindcss/cli/dist/index.mjs --cwd repo --input main_in.css --output ../evidence/node18.css
env/node18/bin/node experiments/baseline.cjs
env/node18/bin/node experiments/run.cjs > evidence/variants.jsonl
env/node18/bin/node experiments/inspect.cjs > evidence/property-sort.jsonl
env/node18/bin/node experiments/browser-fixtures.cjs
env/node18/bin/node experiments/browser.cjs > evidence/computed.jsonl
```

The last command runs local headless Chrome. The scripts call actual installed historical modules, not copied algorithms. The inspector calls `__unstable__loadDesignSystem`, `parseCandidate`, `compileAstNodes`, and `getClassOrder` on the original stylesheet. Its observations are `prose`: earliest property index **30**, **280** declarations; `prose-legal`: earliest index **1**, **79** declarations; both unprefixed classes have no variants. The responsive third class has a distinct variant and does not decide this base/legal ordering.

## Causal source trace

All paths and lines below are relative to this case workspace and verified against the pinned files.

| Link | Exact source and responsible name |
|---|---|
| Load plugin/config and request both classes | `repo/main_in.css:1–3` (`@import`, `@plugin`, `@config`); `repo/index.html:11` (`class`) |
| Conflicting configured values | `repo/tailwind.config.js:67–70` (`theme.extend.typography().DEFAULT.css.h2.marginTop`); `:221–226` (`legal.css.h2.marginTop` and `pointerEvents`) |
| Construct equally specific nested selectors | `repo/node_modules/@tailwindcss/typography/src/index.js:12–25` (`inWhere`), `:32–68` (`configToCss`/`updateSelector`); nested elements and exclusions are within `:where`, leaving the outer single class specificity |
| Register base and modifiers as components | `repo/node_modules/@tailwindcss/typography/src/index.js:120–132` (`plugin.withOptions` handler / `addComponents` call) |
| Turn components into sorted utilities | `env/tailwind-source/packages/tailwindcss/src/compat/plugin-api.ts:477–478` (`buildPluginApi` object's `addComponents`); `:242–318` (`addUtilities`, registration at `:313–318`) |
| Gather nested properties into the whole class sort key | `env/tailwind-source/packages/tailwindcss/src/compile.ts:315–357` (`getPropertySort`), especially traversal `:346–349`; called by `compileAstNodes` at `:137` |
| Prioritize pointer-events over margin | `env/tailwind-source/packages/tailwindcss/src/property-order.ts:1–4` (`GLOBAL_PROPERTY_ORDER`, default export); pointer-events is zero-based index 1 and margin index 30 |
| Sort before count/name tie-breakers | `env/tailwind-source/packages/tailwindcss/src/compile.ts:82–114` (`compileCandidates` comparator), property-index comparison `:105–108`, count/name only `:109–112` |
| Emit conflicting order | `evidence/node18.css:184–201` (legal/h2, negative margin at 200); base class starts `:323`, positive h2 margin at `:442–448` (446). Equal specificity and the same utilities layer make the later base margin win. |

The source archive is for Tailwind v4.1.11, SHA `b24457a9f4101f20a3c3ab8df39debe87564fe8a` (`evidence/tailwind-ref.json`); typography npm provenance reports SHA `39d20e194940903046f2e2733ce0a9b59ccd464b` (`evidence/typography-package-metadata.json`). The TypeScript source is a tracing reference; it was not locally rebuilt. Execution uses the published locked distribution (`repo/node_modules/tailwindcss/dist/lib.mjs:1` imports `chunk-4WXWQT6Y.mjs`; the diagnostic CJS loader uses `dist/lib.js`). These are distinct files from the cited TypeScript, and their minified line numbers must not be confused with source lines. Typography's cited `src/index.js` is the actual published executed source.

## Environment and limits

Final CSS runs use Node **18.20.7**, yarn **1.22.22** install, typography **0.5.16**, core/CLI/node/oxide **4.1.11**. Actual OS is macOS **26.5.2**, arm64; Chrome is **156.0.8078.48**, whereas the original report specifies macOS 15.5 and does not pin Chrome. `evidence/environment.json`, original lockfile integrity fields, `evidence/baseline-sha256.txt`, install/build logs and source metadata preserve the environment. The original fixture inputs remain unchanged. No production repair was made. The browser version differs, but the ordering failure is independently present in the original compiler output and the causal controls isolate it. No remaining material gap in the narrowed finding.

## Recorded investigation notes

The report says that custom `.prose-legal` heading margins lose to `.prose` after Tailwind v4 compiles both. The expected behavior is that a custom typography modifier stacks on the base prose class.

## Provenance and exposure

The original body itself hints at property-count sorting and quotes the purpose of that sorting from a linked PR. I have not opened that PR, issue comments, timeline, fix commits, or later implementations. The reproduction README also identifies negative heading margins as the conflicting declaration.

Original reproduction: `j2em6h/prose-sort-order`, SHA `8df41e02925f14c422a3f52061c659368bbc5e16`. Metadata-only query using `until=2025-07-24T19:44:20Z` (issue creation) returns that same SHA with committer date `2025-07-24T19:21:16Z`. The current branch archive was initially downloaded but left unread until this historical identity was established. The later repository push timestamp is not the commit date. Commit messages and diffs were not read.

The original yarn lock pins typography 0.5.16 and Tailwind CLI/core/node 4.1.11, despite the package manifest's ^4.1.6 ranges. Reported Node is 18.20.7, Chrome, macOS 15.5. Actual initial installed Node is 22.12.0; the final run subsequently used the exact reported Node version.

## Experiment notes

1. Hypothesis: the original locked CLI build emits legal before base and therefore the equally specific base heading margin wins. Prediction: `.prose-legal` precedes `.prose`, with negative and positive margin-top declarations respectively. Confirmed by the original build.
2. Hypothesis: sorting depends on a property's priority before declaration count; legal contains `pointerEvents`, while base does not. Prediction: removing only pointerEvents will change the order; changing config key insertion order will not. The diagnostic variants below tested these predictions without production changes.

Before running variants: `noPointer` removes only pointer-events recursively; predicted base first. `reversed` changes config key order only; predicted same failure. `tinyPointer` keeps only two declarations (pointer-events and negative h2 margin); predicted failure remains despite dramatic count reduction. `tinyMargin` removes pointer-events from that minimal case; predicted modifier wins. Variants use separate generated config/CSS files and the same installed original compiler; original files remain intact.

Observed: all five builds exited 0. Original and reversed config emitted legal first (byte offsets 5299/10999 for legal/base). Removing pointer-events emitted base first (5299/23013 for base/legal). Two-declaration tinyPointer still emitted legal first; tinyMargin emitted base first. The original module design-system API reports prose's property order begins at 30 (margin) with 280 declarations, legal's begins at 1 (pointer-events) with 79 declarations. Both have no variants. This directly rejects count and config insertion order as the deciding factor.

The first diagnostic API invocation used a filesystem package-directory require and failed because that package uses exports without a main field. Switched to Node's createRequire rooted in the reproduction package, then required the actual package name. This was a harness setup correction, not a source modification.

Before browser validation: using a local fixture that retains the compiled CSS and both classes, with h2 following a paragraph, should compute 32px margin-top in original/reversed/tinyPointer and -72px in noPointer/tinyMargin. These values use the original 4px spacing variable. This avoids unrelated `:first-child` typography behavior. The first sandboxed headless Chrome invocation returned no DOM; normal permission escalation allowed the same local command to run. No CSS/browser security flag was changed.

Browser results matched every pre-run prediction. The environment version probe initially requested an unexported package.json subpath; reading the installed package JSON files directly corrected that metadata-only probe.

The original CLI command was repeated through `experiments/baseline.cjs` solely to save an explicit process exit code and assert original rule order in `evidence/baseline-run.json`; it again exited 0 with legal before base.

## Coordinator verification

Independently reran the original Node 18.20.7 CLI build into `evidence/coordinator-original.css`; it is byte-identical to the worker original CSS and retains legal-before-base ordering. Reran the real design-system inspector into `evidence/coordinator-property-sort.jsonl` and confirmed property indices 1 versus 30 and declaration counts 79 versus 280. Checked pinned property-sort traversal/comparator source and original modifier documentation, and reviewed all five recorded browser computed-style controls. Fresh CLI output is `evidence/coordinator-build.log`.
