# Finding: newline loss reproduced; defect status unresolved

In the reconstructed historical environment, pino-pretty replaces the supplied template's newline with a space before inserting `msg` and `err.stack`. A function formatter preserves the requested line break. The mechanism is demonstrated, but **Unresolved** is the justified outcome: historical documentation/tests do not establish the intended treatment of template newlines, and the original two-string logger call does not produce `err.stack` in direct Pino. The reporter's logger/framework and package versions remain unknown.

`reproduced: true` means the narrowed formatting symptom in the actual Pino → pino-pretty stream pipeline with an explicitly supplied structured error; it does **not** mean the original logger integration or exact two-string call reproduced the displayed stack.

## Original observation and reconstruction

Original provenance (`input/provenance.json`) dates the report to **2025-11-21T18:37:35Z**. The original gives:

```js
ignore: 'pid,hostname,context,err'
messageFormat: `[{context}] {msg}{if err.stack}\n{err.stack}{end}`
logger.error(`An error occurred: ${myError.message}`, myError.stack)
```

The JavaScript template literal evaluates `\n` to an actual LF. The reported output places `Error: Something went wrong` on the message line while preserving subsequent stack lines. The expectation is an LF immediately before `Error:`. The postscript says an LF in the log message survives.

There is a material inconsistency: the shown two-string call does not supply an `err` object to Pino. The report may use a framework logger, but none is named. The harness retains that argument order in two controls, records its raw JSON, and separately uses `logger.error({err}, message)` to provide the template data. All cases supply a `context: 'Test'` base field because the report's output includes it without showing its setup. This context setup is a reconstruction choice, not evidence of the reporter's configuration.

The error is a real `Error`; its stack is replaced with a fixed three-line fixture matching the original shape. Timestamp is fixed to zero, color is disabled, and `translateTime` is false for deterministic evidence. These cosmetic substitutions do not affect newline handling. The harness captures Pino's raw JSON, forwards the same chunk into the real pretty stream, waits for stream completion, and reads the actual output file. Its separate `interpretConditionals` call observes that original helper's returned intermediate string; it does not substitute a copied implementation for formatting.

## Historical source and environment

No package version is present in the original report. Selection used **publication metadata only**, choosing the most recent releases published before the original issue date:

| Package | Selected version | npm publication UTC | npm gitHead |
|---|---|---|---|
| pino-pretty | 13.1.2 | 2025-10-10T10:20:40.911Z | `6ee4d5d5669cdbcc49bf41768279841007c17c39` |
| pino | 10.1.0 | 2025-10-18T11:39:51.488Z | `b248d2f805c1455157867276cb91c87f6023004c` |

This is a historical reconstruction, not an assertion of the reporter's versions. Original npm metadata is retained in `evidence/pino-pretty-registry.json` and `evidence/pino-registry.json`; later version metadata was used only to filter publication dates, never to inspect later implementation. Source is the published package with the npm gitHead provenance above. The exact pino-pretty GitHub commit archive is retained in `evidence/source/pino-pretty-6ee4d5d5669cdbcc49bf41768279841007c17c39/`; the relevant source, tests and README were verified byte-identical to the executed npm package. Both package tarballs' SHA-512 values match registry integrity metadata (`evidence/artifact-verification.log`). No history, issue comments, timeline, fix commits, later implementations or online answers were consulted. The original report itself hints that newlines might deliberately be replaced.

Actual experiment runtime: **Node v22.12.0**, `/usr/local/bin/node`, Darwin arm64; npm **10.9.0**. Node binary SHA-256: `9c40e9b16cacab464b63e45731ffd020830144a14c50d440b59b90e22709fe80`. The initial default-context tool check reported Node v22.23.2/npm 10.9.8; subsequent case-scoped execution established the runtime above, and all reproduction/test results use v22.12.0. The available runtime is not claimed to match the reporter's. Dependency installation used an approved network invocation and `npm install --ignore-scripts --before=2025-11-21T18:37:35Z --save-exact pino-pretty@13.1.2 pino@10.1.0`. The resulting full dependency tree is `evidence/dependencies.txt`, and exact resolutions/integrities are pinned in `experiments/runtime/package-lock.json`.

## Historical intended behavior checked before verdict

All paths below are workspace-relative; `P = experiments/runtime/node_modules/pino-pretty/`, `L = experiments/runtime/node_modules/pino/`.

- `experiments/runtime/node_modules/pino-pretty/Readme.md:357–375` describes message templates, nested properties and if/end blocks; it excludes else and nested conditions. `experiments/runtime/node_modules/pino-pretty/Readme.md:375–385` documents the function formatter signature. Neither passage specifies newline preservation or whitespace normalization.
- `experiments/runtime/node_modules/pino-pretty/lib/utils/prettify-message.test.js:152–171` tests nested field substitution, missing fields and conditional blocks; `:174–186` verifies function formatting. These do not test a newline in the template.
- `experiments/runtime/node_modules/pino-pretty/lib/utils/interpret-conditionals.test.js:16–68` tests conditional substitution/removal and unmatched delimiters, without a newline-formatting contract.
- `experiments/runtime/node_modules/pino/docs/api.md:774–791` explains interpolation and explicitly shows that consecutive string parameters are not automatically concatenated. This supports the exact-call control's absent stack, while leaving a possible framework wrapper unresolved.

The two focused historical test files ran unmodified: **31 passed, 0 failed, 0 skipped**, exit 0 (`evidence/historical-tests.log`). Their success supports existing documented features, but does not settle the newline expectation. A deliberate `.replace(/\s+/g, ' ')` in implementation alone cannot establish that the reported behavior is correct. Conversely, a user's expectation and a general customization description do not prove this particular newline treatment violates the intended contract. No separate conditional defect is promoted into a verdict for this report.

## How I reproduced and debugged it

From this case directory:

```sh
# Existing local dependency tree is retained. To restore the exact pinned tree:
npm ci --prefix experiments/runtime --ignore-scripts
node experiments/verify-artifacts.cjs
node experiments/reproduce.cjs
node --test experiments/runtime/node_modules/pino-pretty/lib/utils/interpret-conditionals.test.js experiments/runtime/node_modules/pino-pretty/lib/utils/prettify-message.test.js
```

`reproduce.cjs` should exit 0 and end with `All focused assertions passed; 10 cases.` It writes raw records/intermediates/output to `evidence/observations.json` and individual `.txt` files. Saved run: `evidence/reproduction.log`, exit code `evidence/reproduction.exit` = 0. Verification output is `evidence/artifact-verification.log`.

The decisive structured-error output is:

```text
[0] ERROR: [Test] An error occurred: Something went wrong Error: Something went wrong
    at bootstrap (/dist/apps/test/main.ts:26:19)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
```

The function-format control produces:

```text
[0] ERROR: [Test] An error occurred: Something went wrong
Error: Something went wrong
    at bootstrap (/dist/apps/test/main.ts:26:19)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
```

## Experiment notes and decisive controls

**Before experiment 1:** hypothesis: string-template whitespace is normalized before regular value insertion. Prediction: a literal template LF becomes a space, a message LF survives, and a function LF survives. The planned controls included the exact logger argument order, structured error, literal backslash-n, and conditional variants. Historical docs/tests were inspected before choosing the verdict.

**Actual result:** all predictions about the formatting stage were observed, qualified by the logger-call and conditional effects below.

| Case / evidence filename stem | Observed result |
|---|---|
| `literal-newline-structured` | Original template with `logger.error({err}, message)` reproduces LF→space before Error; stack's later LFs/indentation survive. |
| `function-structured` | Function emits LF before Error and keeps all stack LFs. |
| `newline-in-msg` | A trailing LF in `msg` survives. A space remains at the beginning of the following Error line, so it is not byte-identical to the postscript's displayed output. |
| `same-line-conditional` | Replacing the template LF with a space causes the conditional to match; all stack LFs and indentation collapse too. |
| `no-conditional` | `{msg}\n{err.stack}` also loses its template LF; normalization is not limited to recognized conditional blocks. |
| `literal-backslash-n` | A literal backslash plus n survives as text, while stack LFs collapse. The formatter does not decode it into LF. |
| `exact-original-argument-order` | `logger.error(message, err.stack)` produces raw JSON with no `err` and output ending in `message + ' \n'`; no stack appears. |
| `exact-original-ps-call` | Same exact argument order with a trailing LF in the message still has no `err`; output ends in `message + '\n \n'`. |
| `missing-error` | Supplied multiline conditional leaves a separator space after the message even without an error. |
| `same-line-missing-error` | Same-line conditional removes its body and leaves no separator space. This is a control on regex matching, not a separate final defect claim. |

**Harness correction:** the first run tried `stream.flushSync()`, which the returned transform does not expose, and failed with TypeError (saved in `evidence/first-harness-error.log`). That setup failure is not reproduction. The corrected harness awaits `stream.end` completion before reading the destination; no sleeps, suppressed failures or production source changes are used. All subsequent focused assertions and historical tests pass.

## Verified causal trace

The following paths cite the executed, unmodified npm sources, not generated instrumentation. Source archive equivalence for the key pretty files is recorded separately.

| Step | Exact source and function | What it does |
|---|---|---|
| Logging arguments | `experiments/runtime/node_modules/pino/lib/tools.js:43–74`, `genLog` / returned `LOG` | Object-first calls forward object and message at :65. String-first calls forward null object and interpolated message at :74. |
| No structured error in exact call | `experiments/runtime/node_modules/pino/lib/proto.js:206–233`, `write` | Null object becomes `{}` at :215–216; only supplied error/object data can populate error properties. Raw JSON observation confirms no `err`. |
| Stream formatting | `experiments/runtime/node_modules/pino-pretty/index.js:133–153`, `build` / transform | Parsed log chunks are passed to the real `pretty` function. |
| Format before ignore | `experiments/runtime/node_modules/pino-pretty/lib/pretty.js:78–82`, `pretty` | Calls `prettifyMessage` before `filterLog`; ignoring `err`/`context` does not hide them from messageFormat. |
| Select string formatter | `experiments/runtime/node_modules/pino-pretty/lib/utils/prettify-message.js:38–41`, `prettifyMessage` | Calls `interpretConditionals` before ordinary placeholder replacement. |
| Conditional matching | `experiments/runtime/node_modules/pino-pretty/lib/utils/interpret-conditionals.js:19–25`, `interpretConditionals` | The :20 regex uses `.` without dotAll. A body beginning with literal LF is not matched. :23/:25 then strip leftover if/end delimiters. |
| Newline loss | Same file/function, **:27** | `.replace(/\s+/g, ' ').trim()` changes the template LF to a space. Actual returned intermediate is `"[{context}] {msg} {err.stack}"`. |
| Late insertion preserves stack | `experiments/runtime/node_modules/pino-pretty/lib/utils/prettify-message.js:41–54`, `prettifyMessage`; `experiments/runtime/node_modules/pino-pretty/lib/utils/get-property-value.js:19–29`, `getPropertyValue` | Ordinary `{msg}` / `{err.stack}` values are inserted after normalization. These values' LFs are not normalized in this branch. |
| Same-line conditional contrast | `experiments/runtime/node_modules/pino-pretty/lib/utils/interpret-conditionals.js:29–35`, nested `replacer`, then :27 | For a matching same-line block, `err.stack` is inserted at :32 before whitespace normalization, so the stack's own whitespace also collapses. |
| Function contrast | `experiments/runtime/node_modules/pino-pretty/lib/utils/prettify-message.js:56–58`, `prettifyMessage` | Directly calls function and colorizer, bypassing `interpretConditionals`. |
| Final line | `experiments/runtime/node_modules/pino-pretty/lib/pretty.js:128–137`, `pretty` | Appends formatted message to the prefix and adds final EOL; it does not collapse the message's internal LFs. |

**Observed values:** captured raw Pino JSON, original helper return strings, actual stream output and assertion/test results are saved. **Static inference:** the missed multiline regex match and ordering of delimiter removal/normalization/late insertion are inferred directly from the cited original source and challenged by same-line, no-conditional, missing-error and function controls. No debugger breakpoint trace of individual assignments is claimed. No source patch or instrumentation was necessary.

## Remaining uncertainty and next action

The causal explanation is complete for the selected historical packages. The unresolved gaps are **environment/integration** (reporter's exact logger, wrapper, versions and how `context`/`err.stack` are produced) and **expected behavior** (whether historical messageFormat string syntax was intended to preserve template LFs). These gaps prevent either Bug found or Expected behavior, despite a reproduced narrowed symptom. The next useful action is to obtain the reporter's dependency lockfile/logger setup and an authoritative newline-formatting requirement or historical test. No production fix was made or proposed.

## Acquisition and boundary notes

Initial network access failed with curl DNS exit 6; original artifacts were acquired using approved network escalation. One initial mkdir used the default workspace root and created empty `evidence/` and `experiments/` directories there; they were removed using rmdir without reading parent contents. All investigation inputs/source reads and subsequent writes were scoped to this case. No parent/sibling cases, old investigations, coordinator sessions or prior answers were read. This is an ordinary log formatting case; no cybersecurity safeguard was encountered.

## Coordinator verification

Independently replayed all ten actual Pino-to-pretty stream controls with `node experiments/coordinator-reproduce.cjs`, exit 0, changing only the output directory. Original evidence is preserved; fresh raw JSON, intermediate strings and outputs are in `evidence/coordinator/observations.json`, `evidence/coordinator/reproduction.log` and per-case text files. Verified the whitespace-normalization branch, later placeholder insertion and function bypass at the cited executed source lines. The exact two-string call still lacks err.stack; the reproduced newline symptom uses the explicitly qualified structured-error input. Unresolved remains justified because original integration and newline-formatting obligation are missing.
