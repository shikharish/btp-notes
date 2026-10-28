# Finding: Bug found — public TypeScript construction compatibility regression

The reported error is reproduced with the real published packages. The supplied method body compiles with MUI X 7.27.1 and TypeScript 5.7.3, then fails with **TS2339 at `sortModel.push`** with 7.27.2. `GridSortModel` changed from `GridSortItem[]` to `readonly GridSortItem[]`. The compiler consequently resolves that explicitly annotated variable to `ReadonlyArray`, whose interface has no `push` method. The empty array initializer does not override its declared type.

The narrowed defect is loss of an existing public TypeScript capability: building a fresh local sort model using the exported mutable model type and then passing it to the documented `setSortModel` API. No grid-owned state is being mutated in this example. This investigation establishes the regression; it does not infer a runtime sorting failure or propose a production repair.

## Observation, expectation, and historical obligation

The report expects no breaking change between patch releases. Version numbering alone is not the basis for this finding:

* In the original 7.27.1 source, `packages/x-data-grid/src/models/gridSortModel.ts:26–40` defines the item shape and explicitly defines the public model as `GridSortItem[]`. Mutability, including `push`, is part of that concrete exported TypeScript contract.
* The model is exported from `packages/x-data-grid/src/models/index.ts:24`, the Community public entry point at `packages/x-data-grid/src/index.ts:14`, and the Pro public entry point at `packages/x-data-grid-pro/src/index.ts:13`. These are ordinary public exports, not internal state structures.
* Historical `docs/data/data-grid/sorting/sorting.md:27–35` describes the model as a list of sorting items, and lines 86–88 document supplying models programmatically through `setSortModel`. `packages/x-data-grid/src/models/api/gridSortApi.ts:18–22` declares that public input as `GridSortModel`. The generated API reference also lists it at `docs/pages/x/api/data-grid/grid-api.json:401–403`.
* `docs/data/data-grid/api-object/api-object.md:5–10` presents the API object as the programmatic interface and identifies `unstable_` methods as experimental; `setSortModel` has no such prefix. The v6→v7 guide, `docs/data/migration/migration-data-grid-v6/migration-data-grid-v6.md:29–36`, associates public API changes with the major migration and explicitly expects a minor Material upgrade not to break compatibility. This is supporting historical policy context rather than a specific promise that every list must remain mutable.

All paths above are relative to `evidence/source/mui-x-7.27.1/`. The sorting prose does **not** expressly instruct users to call `push`. The more precise obligation is the original explicit public array declaration, coupled with the documented API accepting caller-constructed models. Changing it rejects previously well-typed construction code. Readonly arrays are themselves a legitimate design; the observed incompatibility is the change to an existing public type.

## Pinned artifacts and environment

| Artifact | Pin / provenance |
|---|---|
| MUI X 7.27.1 source | Tag `v7.27.1`, annotated tag `85a14ae592da201a2f9bb2a98bb53d3b012fa6cd`, commit `d1dec0221f63f4c36159645834b522f776af3dcf` |
| MUI X 7.27.2 source | Tag `v7.27.2`, annotated tag `b1c5bff8078502b000ed87ec1dae6ab9d57b524d`, commit `695d41219ba390c0c4648ebb7eb743af51a9b071` |
| Executed declarations | npm `@mui/x-data-grid` and `@mui/x-data-grid-pro`, both pinned to the respective version in isolated installations |
| Compiler/runtime | TypeScript **5.7.3**, Node **22.14.0**, npm **11.1.0** |
| Host | macOS **26.5.2**, arm64; reporter had macOS 15.3.1 |
| Fixed reported dependencies | React/React DOM 19.0.0, `@types/react` 19.0.10, Emotion React/Styled 11.14.0, Material/icons/system/utils/private-theming/styled-engine/core-downloads-tracker 6.4.6, MUI types 7.2.21, X internals/license 7.26.0 |
| Reconstruction addition | `@types/react-dom` 19.0.4; report did not specify it. Other unspecified transitives are recorded by each lockfile and full dependency tree. |

`evidence/tag-*.json` and `tag-object-*.json` preserve GitHub tag metadata. The original tag archives are saved, extracted unchanged under `evidence/source/`. `evidence/provenance.json` records archive SHA-256 hashes, npm tarball URLs, npm SHA-512 integrity, lockfile hashes, and installed pins. npm metadata does not expose a `gitHead`; the association between the npm package and repository source is the matching release version and matching relevant declaration, not an invented npm commit attestation. npm lockfiles preserve each package's resolved artifact/integrity.

Installation bootstrapped using the host Node 22.23.2/npm 10.9.8, then installed the historical Node/npm locally. All reported compiler runs and compiler inspection used the pinned Node 22.14.0; `run.sh` records Node/npm/TypeScript versions. The npm 11.1.0 command also records the actual dependency trees. Initial sandboxed registry access failed DNS resolution; authorized elevated artifact downloads/installations succeeded. This is a reconstructed compiler environment, not the reporter's machine.

## How I reproduced and debugged it

1. Read only this case's prompt and original report. Obtained the two official release tags/archives and npm metadata, without issue comments, history, fixes, or later implementations.
2. Created isolated published-package installations at `experiments/7.27.1` and `experiments/7.27.2`, pinning the reported relevant versions and fixing other dependencies through lockfiles/overrides.
3. Put the original method body into `reported.ts` with minimal missing scaffolding: a Pro public type import, `columnsType` with string `id` and optional boolean sorting order, and an abstract `getGridApi()` returning the published `setSortModel` signature. The method's expressions/control flow are preserved. Since the report omitted its import, `community.ts` repeats it using the Community public import.
4. Compiled every fixture with the real TS 5.7.3 CLI, `strict`, `noEmit`, ES2022/CommonJS/Node resolution and **full declaration checking** (`skipLibCheck` is not enabled). No assertions, suppressed errors, fake model definitions, or altered package declarations were used.
5. Compared the original model source files and inspected the compiler's actual resolved array target and `push` symbol. This tied the diagnostic to the declaration change rather than React peers, grid initialization, or sorting execution.

Run from this case directory after installed dependencies are present:

```sh
./experiments/run.sh
./experiments/node_modules/node/bin/node ./experiments/inspect.cjs
```

`run.sh` saves individual compiler logs and prints their exit status. Its intentionally failing fixtures are recorded, so the script itself succeeds after collecting the matrix. For a fresh dependency setup, run `./experiments/setup.sh` (requires registry access). To reinstall just the two trees, run `npm ci --prefix experiments/7.27.1 --ignore-scripts --no-audit` and the equivalent 7.27.2 command. The tool-runtime manifest/lockfile is in `experiments/`; a fresh install there requires running the Node package's `installArchSpecificPackage.js` if `--ignore-scripts` was used.

Decisive output in `evidence/compilation-matrix.log`:

```text
v22.14.0
11.1.0
Version 5.7.3
7.27.1 reported exit=0
...
7.27.2 reported exit=2
reported.ts(9,19): error TS2339: Property 'push' does not exist on type 'GridSortModel'.
```

| Fixture | 7.27.1 | 7.27.2 | What it checks |
|---|---:|---:|---|
| `reported.ts` | 0 | 2, TS2339 | Original method body through Pro export |
| `community.ts` | 0 | 2, TS2339 | Same failure through Community export |
| `push-only.ts` | 0 | 2, TS2339 | Removes column/class/API scaffolding; isolates property access |
| `construction.ts` | 0 | 0 | Literal model, iteration, and `setSortModel` remain accepted |
| `mutable-builder.ts` | 0 | 0 | Same method with local annotation `GridSortItem[]`; demonstrates valid items and setter, isolates model alias |

The last fixture is an experimental input control, not a source patch or a proposed production repair.

## Responsible source chain and verified locations

Prefix `S2` = `evidence/source/mui-x-7.27.2/`. Prefix `P2` = `experiments/7.27.2/node_modules/`. evidence/source/mui-x-7.27.1/P1 denote the corresponding 7.27.1 trees.

| Link | Exact location | Function/type and effect |
|---|---|---|
| Input annotation and rejected expression | `experiments/7.27.2/reported.ts:6–12` | `Example.sortInit`: explicitly annotates local `sortModel`; accesses `.push` at line 9 before `setSortModel` |
| Pro public forwarding | `evidence/source/mui-x-7.27.2/packages/x-data-grid-pro/src/index.ts:13`; `experiments/7.27.2/node_modules/@mui/x-data-grid-pro/index.d.ts:12` | Re-exports Community models |
| Model forwarding | `evidence/source/mui-x-7.27.2/packages/x-data-grid/src/models/index.ts:24` | Exports `gridSortModel` |
| Responsible change | `evidence/source/mui-x-7.27.1/packages/x-data-grid/src/models/gridSortModel.ts:40` versus `evidence/source/mui-x-7.27.2/packages/x-data-grid/src/models/gridSortModel.ts:40` | `GridSortModel`: `GridSortItem[]` → `readonly GridSortItem[]` |
| Executed published declarations | `experiments/7.27.1/node_modules/@mui/x-data-grid/models/gridSortModel.d.ts:30` versus `experiments/7.27.2/node_modules/@mui/x-data-grid/models/gridSortModel.d.ts:30` | Same alias change in actual compiler input; see `evidence/model-source.diff` for original source comparison |
| Compiler library interface | `experiments/7.27.2/node_modules/typescript/lib/lib.es5.d.ts:1188–1313`, `:1322`, `:1344` | `ReadonlyArray<T>` has no `push`; `Array<T>.push(...items: T[]): number` exists |
| Setter remains valid | `evidence/source/mui-x-7.27.2/packages/x-data-grid/src/models/api/gridSortApi.ts:18–22`; `experiments/7.27.2/node_modules/@mui/x-data-grid/models/api/gridSortApi.d.ts:17–21` | `GridSortApi.setSortModel` accepts `GridSortModel` |

`evidence/type-inspection.log` records the actual compiler checker result: 7.27.1 target `Array`, push symbol present, no diagnostics; 7.27.2 target `ReadonlyArray`, push absent, diagnostic 2339. These are observed compiler values, not inference from the textual diff alone. The rejected property lookup occurs at compile time; no MUI runtime branch or grid state change is reached. For context only, the original `setSortModel` implementation is `evidence/source/mui-x-7.27.2/packages/x-data-grid/src/hooks/features/sorting/useGridSorting.ts:174–187`; it is not executed by this type-only reproduction.

## Experiment notes and limits

**Experiment 1 hypothesis/prediction (recorded before runs):** the model became readonly; original method should pass with 7.27.1, fail at push with 7.27.2, while read-only consumption stays accepted. **Actual:** exactly that, including both public import paths and no unrelated declaration errors. The isolated push fixture fails identically; explicit mutable-item construction succeeds in both.

**Experiment 2 hypothesis/prediction (recorded before inspection):** the compiler resolves the model to `ReadonlyArray` only in 7.27.2 and loses its `push` symbol. **Actual:** confirmed in `type-inspection.log`. Inspection initially reported a declaration's preceding trivia position (1339); the script was corrected to use the declaration token start, which points to `Array.push` at line 1344. This changed only inspection reporting, not package files or compilation outcomes.

No direct contradiction was found. The report's missing import/column type/tsconfig prevent claiming an exact clone of its complete application; both plausible public imports and the unchanged method body reproduce the assigned diagnostic. React rendering, browsers, license setup, grid state mutation and UI sorting were unnecessary for this compiler failure and were not exercised. No original files were patched. Historical documentation does not expressly require `push`, so the finding is limited to the demonstrated public declaration compatibility regression, not a broader claim that models must always be mutable.

## Coordinator verification

Independently ran `python3 experiments/coordinator-verify.py`, exit 0, preserving worker evidence. Original method compiles with 7.27.1 and fails only with TS2339 on 7.27.2; the mutable-item builder control passes 7.27.2 under the pinned compiler with full declaration checking. Fresh commands, outputs and asserted exit codes are in `evidence/coordinator-compilation.json` and `evidence/coordinator-compilation.log`. Verified the public alias change and exported setter against the cited files; expanded abbreviated critical source references to full workspace-relative paths. This finding concerns public type-construction compatibility, not runtime sorting.
