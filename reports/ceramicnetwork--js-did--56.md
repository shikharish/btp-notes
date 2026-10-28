The exact reported Babel error is reproducible when an older Babel parser transforms the complete published did-jwt 5.12.1 ES module: its untransformed `??` operator reaches a parser that requires an explicitly enabled syntax plugin. **The overall verdict is unresolved:** the reporter's client application, Babel configuration, versions and build command are absent. The repository's own historical build and Babel configuration pass, which does not exclude the reporter's client failure.

`reproduced: true` is scoped to the historical Babel transformation of the entire published bundle, including the exact error location and code frame; the supplied client integration remains unverified.

## Observation, expectation and provenance

The original report says a compatible dependency update breaks the project, names did-jwt 5.6.1 as a possible pin, and suggests enabling the proposal plugin. These are solution hints already present in the original body, not independent evidence. The observed error is compile-time parsing, before any DID resolver or encryption function executes. The expectation is that a compatible dependency update remains buildable in the client's existing pipeline; that pipeline's supported syntax contract is unspecified.

This is an ordinary software build defect report in a security-related library; no cybersecurity investigation is involved. No issue comments, timeline, fixes, commit history, later source or outcome tags were used. Original issue metadata was filtered to number/title/creation date/body; it establishes creation at 2022-01-08T01:00:21Z (`evidence/original-metadata.json`). npm metadata was used for publication/integrity/version provenance only; saved metadata is limited to historical chronology and inspected versions.

The report gives no js-did revision. I reconstructed the latest stable `dids` release available before that timestamp: **dids 2.4.3, gitHead 4a7b12c81f6b451f67ceea14a0f47e078306c188**, published 2021-11-26. Its source is saved under `evidence/js-did-source/js-did-4a7b12c81f6b451f67ceea14a0f47e078306c188/`. This is a justified historical reconstruction, not a claim about the reporter's installed version.

**did-jwt 5.12.1**, gitHead **bb797d893c13fc070ceeeff0ea3011e4988a64e6**, published 2021-12-03, has the quoted expression at exactly line 1662; this makes it a strong matching artifact, not proof of the reporter's lockfile. Both 5.12.1 and the report's proposed 5.6.1 are allowed by dids 2.4.3's `^5.6.1` range. Older 5.6.2/5.6.3 bundles were also inspected and contain no `??`; I did not assume the first patch after 5.6.1 introduced the syntax. No first-introducing version claim is made.

The published npm tarballs' SHA-1 and SHA-512 values were verified against registry metadata (`evidence/artifact-pins.json`). The js-did source archive was acquired directly from GitHub codeload at the above full SHA. Original source archives and published bundles are retained unchanged.

## How I reproduced and debugged it

I read the original input, acquired the issue timestamp and historical published packages, then searched the complete ES bundles for the quoted operator. did-jwt 5.12.1 matched both the code and line number. I traced it from the published bundle back to the shipped TypeScript function and inspected js-did's dependency declaration, import and build configuration.

I installed the repository's **original package-lock.json** with `npm ci --ignore-scripts`; its actual core/parser are Babel **7.14.6**, preset-env **7.14.5**, TypeScript **4.2.4**, and did-jwt **5.6.1**. Separately I installed Babel core/parser **7.4.4** with parser forced to that version and syntax plugin **7.2.0**. The old parser is an explicit diagnostic reconstruction, not an inferred reporter version. Its other transitive packages were resolved during this investigation and are completely recorded in `experiments/old-babel/package-lock.json` and `evidence/old-babel-dependency-tree.log`; it is not claimed as an entirely period-frozen Babel tree.

The harness calls the real Babel `transformFileSync` API on the entire unchanged published file; it does not copy the algorithm or run a fabricated parser. The repository configuration control uses the actual historical config, with its presets resolved from the original lockfile. I then ran the actual repository `npm run build` pipeline (`prebuild → clean → tsc -p tsconfig.json`) on a separate copy of its unchanged historical source.

Commands from this case directory:

```sh
node experiments/run.cjs
npm --prefix experiments/repository-env run build
# Reinstall dependencies from the saved locks, then run both:
sh experiments/reproduce.sh
```

The transformation run was repeated with the available **Node 16.13.0** executable and **Node 22.12.0**, producing the same four outcomes. Logs are `evidence/transform-node16.log` and `evidence/transform.log`. The build's runtime probe records npm's entry process as Node 22.12.0/npm 10.9.0 and its child npm/tsc processes as Node **16.13.0** (PATH resolution); this generated an npm compatibility warning but the build exited zero. The actual runtime path/argv is retained in `evidence/repository-build.log`. These are measured execution environments, not the reporter's runtime.

## Experiments and controls

These predictions were written in this report before execution, then updated with actual outcomes:

| Hypothesis and prediction | Actual result |
| --- | --- |
| Old Babel without nullish syntax support rejects 5.12.1 at 1662:17. | Rejected with exact report text, code frame and proposal-plugin suggestion. Parser location is zero-based column 16; displayed error is column 17. |
| Keeping Babel/options fixed, 5.6.1 should parse. | Passed; no `??` remains in its output. |
| Keeping the 5.12.1 artifact and parser fixed, adding only nullish syntax support should parse. | Passed; `??` remains, showing syntax acceptance alone is not downlevel transformation. |
| The repository's locked Babel/config should accept and transform 5.12.1. | Passed; generated output contains no `??`. This is a complete-module Babel stage control, not a reconstructed client bundle. |
| The actual historical repository build should pass with its original lockfile. | Passed, exit 0, TypeScript 4.2.4 and did-jwt 5.6.1. This baseline does not test a 5.12.1 upgrade through the complete client pipeline. |

`experiments/run.cjs` asserts all four expected transformation outcomes and the exact rejection location; it exits 0 precisely because the expected first failure occurred. `evidence/results.json` contains structured results. All inputs and controls use unchanged published files; no production patch was made. No encryption/runtime invocation is necessary to trigger this parsing failure.

One instrumentation mistake is retained: an initially unquoted space-containing `NODE_OPTIONS --require` path prevented Node from starting (`evidence/runtime-probe-quoting-error.log`). Quoting the preload path fixed the probe; the subsequent real build passed. Initial sandbox network DNS failures were overcome by authorized network escalation. Outdated Browserslist and npm/Node-version warnings were not suppressed or treated as the reported symptom.

## Verified source trace

Paths below are relative to this case workspace. Source and executed bundle references are distinguished explicitly.

| File and verified lines | Function/configuration and causal role |
| --- | --- |
| `evidence/dids-2.4.3/package/package.json:35–47` | `dependencies.did-jwt: ^5.6.1` admits the matching later artifact; Babel dev dependency is already `^7.14.6`. |
| `evidence/js-did-source/js-did-4a7b12c81f6b451f67ceea14a0f47e078306c188/src/did.ts:2,277–283` | Module import and `DID.createJWE` reference did-jwt's `resolveX25519Encrypters`; establishes the dependency connection. Parsing fails before this runtime call. |
| `evidence/did-jwt-5.12.1/package/package.json:5–8` | Published `module` selects `./lib/index.module.js`; the reported filename is this bundler-oriented artifact. Client resolution itself is unobserved. |
| `evidence/did-jwt-5.12.1/package/src/xc20pEncryption.ts:278–280,302–321` | Original TypeScript `resolveX25519Encrypters` / nested `encryptersForDID`: filtered keys use `?? []` at 312–316. |
| `evidence/did-jwt-5.12.1/package/lib/index.module.js:1641–1664` | Executed published ES bundle, `resolveX25519Encrypters` / `encryptersForDID` / generated `_temp4`: optional chaining has been lowered but `?? []` survives at 1662. |
| `experiments/old-babel/node_modules/@babel/parser/lib/index.js:8265–8287` | `Parser.parseExprOp` recognizes the nullish token and calls `expectPlugin("nullishCoalescingOperator")`. |
| `experiments/old-babel/node_modules/@babel/parser/lib/index.js:7641–7648` | `Parser.expectPlugin` throws when the parser plugin is absent. No compiled output is returned. |
| `experiments/old-babel/node_modules/@babel/core/lib/transformation/normalize-file.js:180–203` | Error handling in `parser` converts the parser's missing-plugin state into the Babel message/code frame. |
| `experiments/old-babel/node_modules/@babel/core/lib/transformation/util/missing-plugin-helper.js:217–238` | `generateMissingPluginMessage` emits the exact reported wording and plugin suggestion. |
| `experiments/old-babel/node_modules/@babel/plugin-syntax-nullish-coalescing-operator/lib/index.js:18–25` | Plugin `manipulateOptions` pushes the missing parser plugin; controlled acceptance follows. |
| `evidence/js-did-source/js-did-4a7b12c81f6b451f67ceea14a0f47e078306c188/babel.config.js:2–7` | Historical presets target Node 12 with preset-env and preset-typescript; the locked stack demonstrably transforms the operator. |
| `evidence/dids-2.4.3/package/package.json:9–16` | Actual `scripts.build` uses tsc; Babel is not this repository's production build command. |

Mechanism demonstrated: entire published ES module → surviving `??` token → old parser's disabled-plugin branch → missing-plugin error → Babel diagnostic exactly matching the report. The empty-array fallback's runtime behavior is not involved. Static source analysis establishes the dependency/import path; the actual Babel run establishes the causal parser branch and its output.

## Remaining gap and verdict

The evidence establishes a compiler/dependency syntax compatibility mechanism, but does not establish which client compiler configuration was promised to be supported, or that js-did's Babel configuration was responsible. Passing repository controls do not show that the reporter was wrong: client tooling can use a different Babel configuration. Conversely, choosing an old parser that rejects newer syntax does not prove a package contract violation. Accordingly this is **unresolved**, with the precise Babel-stage symptom reproduced.

To decide the defect status, obtain the original client's package/lockfile, Babel configuration, loader/bundler configuration and build command (or an equivalent original minimal client), then run that pipeline with did-jwt 5.6.1 and the matching newer artifact while keeping all other inputs fixed. No unrequested repair is proposed.

## Coordinator verification

The coordinator independently reran all four Babel transformation controls and confirmed the exact rejection location (1662, zero-based column 16), all three passing controls, and the cited parser branches. The harness result output was redirected to a separate file to preserve original evidence. See `evidence/coordinator-verification.log` and `evidence/coordinator-results.json`. Verdict remains Unresolved because the actual client pipeline is unavailable.
