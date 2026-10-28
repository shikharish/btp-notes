**Bug found.** In bignumber.js 11.1.3, `toFormat(2, {groupSize: 0})` duplicates the fractional part, for example `100000.00.00`. Zero grouping skips the integer-string rebuild, leaving the original fractional part in `str`; the fraction append then adds it a second time. This violates the historical documented fixed-point formatting contract. The original report’s literal 9.3.1 comparison and positive-group output contain discrepancies, preserved below.

## Scope, provenance and original hints

I read the frozen original body in `input/issue.md` and `input/original.json`, plus `input/run.json` and `input/provenance.json`. The report already supplies the duplicate fraction examples, the 11.1.3 versus 9.3.1 comparison, and the hint that zero group size is responsible while positive group sizes work. These are original hints, not independently discovered facts. Dataset outcome/status labels were not used. No comments, issue timeline, fixes, history or later implementation were consulted.

Exact releases were downloaded from the npm registry; the 11.1.3 metadata identifies gitHead `cda702b9c5deaab16c3db68e58982804577242d4`, acquired as a GitHub codeload snapshot. Only these historical artifacts will be inspected. The first sandboxed registry download failed with DNS exit 6; the authorized network escalation succeeded. This is not a security investigation.

## Experiment notes

1. Hypothesis before running: the exact npm CommonJS entry point in 11.1.3 duplicates the fraction only when integer grouping is disabled; 9.3.1 and positive grouping are controls. Predict the three original failures, normal `toFixed(2)`, no duplication at zero decimal places, and no duplication for positive group size.
2. Hypothesis before running: the preexisting historical test suite may pass because it tests group sizes above zero but does not assert this zero-group-size fractional case. Run the original test runner unchanged; inspect relevant historical tests/docs to establish intended formatting.
3. Hypothesis before instrumentation: after `toFixed`, `str` still contains the fraction. The positive-group branch replaces it with the integer, but the zero-group case skips that assignment; the later fraction append repeats the existing fraction. Instrument a separate copy to observe values, preserving the release source.


## Source and execution environment

The npm releases and metadata are retained under `evidence/`, with extracted releases under `repo/11.1.3/` and `repo/9.3.1/`. SHA-1 and SHA-512 checks in `experiments/verify-artifacts.cjs` match both registry metadata records. The reported npm gitHead is `cda702b9c5deaab16c3db68e58982804577242d4`; comparison gitHead is `a7bc1f175c1e40db1abe8cebd52b60fc5381f487`. The exact reported GitHub snapshot is `repo/source-cda702b/`. Its CommonJS file matches the npm CommonJS file after CRLF normalization. This ties the inspected source to the executed release; no commit history was inspected. Hashes are in `evidence/integrity.log` and `evidence/sha256.log`.

Acquisition URLs were `https://registry.npmjs.org/bignumber.js/11.1.3`, `https://registry.npmjs.org/bignumber.js/9.3.1`, their metadata-specified tarballs, and `https://codeload.github.com/MikeMcl/bignumber.js/tar.gz/cda702b9c5deaab16c3db68e58982804577242d4`. Registry metadata is provenance evidence, not an independently authenticated publisher signature verification.

Actual experiment runtime: `/usr/local/bin/node`, Node v22.12.0, Darwin arm64, no runtime dependencies. An initial shell probe outside the case returned Node v22.23.2 and npm 10.9.8; the experiments themselves record v22.12.0. npm was not used to install or execute the library. The release package has no runtime dependencies; its TypeScript development dependency is unnecessary for this JavaScript API. This is a reconstructed local environment, not a claim about the reporter’s runtime.

## How I reproduced and debugged it

From this case directory, run:

```sh
./experiments/run.sh
node repo/source-cda702b/test/test.js
```

The first command verifies retained artifacts, invokes the actual CommonJS entry points with the reported API overload, checks controls, and instruments a separate diagnostic copy. Command exit codes are in `evidence/commands.log`; all three final scripts exit 0. The unchanged historical test command also exited 0. The reproduction uses `require('../repo/11.1.3')`, which resolves through the release’s `main` to `dist/bignumber.cjs`; it does not reimplement the algorithm. The npm `require` export also names that exact file. No Vite/React or StackBlitz environment was reconstructed: the original issue separately supplies this standalone CommonJS API, and that is the pipeline reproduced here.

Decisive actual output (`evidence/reproduction.log`):

| Input | 11.1.3 zero group size | 11.1.3 group size 3 | 11.1.3 `toFixed(2)` |
|---|---|---|---|
| `100000` | `100000.00.00` | `100,000.00` | `100000.00` |
| `1234.5` | `1234.50.50` | `1,234.50` | `1234.50` |
| `-9.9` | `-9.90.90` | `-9.90` | `-9.90` |

Zero decimal places (`toFormat(0, {groupSize:0})`) match `toFixed(0)` for all three inputs, so duplication requires a retained fractional part. An explicit comma decimal separator produces `1234.50,50` in 11.1.3, confirming that the first fraction is still the original `toFixed` string while the appended copy uses the configured separator.

**Preserved contradiction:** with the exact sparse `{groupSize:0}` object, 9.3.1 returns `10000000`, `123450`, and `-990`, not the report’s expected dotted strings. With explicit `{groupSize:0, decimalSeparator:'.', groupSeparator:','}`, it returns the expected `100000.00`, `1234.50`, and `-9.90`; 11.1.3 still duplicates them. The earlier release accepts the supplied format object directly and treats its missing decimal separator as `''`; the reported release resolves missing options from defaults. Likewise the original report’s group-size-3 example omits the comma actually supplied by 11.1.3’s defaults. These discrepancies narrow the claim but do not invalidate the three exact reported 11.1.3 failures.

My initial comparison harness incorrectly asserted that the sparse options would produce dotted strings in 9.3.1. Its assertion failed with exit 1. That script and output remain at `experiments/initial-comparison.cjs` and `evidence/initial-comparison-failed.log`. I corrected the comparison expectation and added a controlled explicit-separator comparison; I did not suppress the assertion failure.

## Verified source trace and contract

The reported original source and executed CommonJS bundle use the same line numbers for this function. The instrumentation adds lines, so the table cites the untouched files, not the generated diagnostic copy.

| Verified file and lines | Function / role |
|---|---|
| `repo/source-cda702b/package.json:28–39` | CommonJS `main` and `exports.require.default` select `dist/bignumber.cjs`. |
| `repo/source-cda702b/bignumber.js:1526–1534` | `resolveFormatOptions`: supplied `groupSize:0` overrides the default; missing separator/sign settings use `FORMAT`. |
| `repo/11.1.3/dist/bignumber.cjs:2712–2723` | `P.toFormat`: recognizes the second object argument as formatting options, clears rounding-mode argument. |
| `repo/11.1.3/dist/bignumber.cjs:2754–2766` | `P.toFormat`: `toFixed` supplies `100000.00`; split extracts integer `100000` and fraction `00` without removing the fraction from `str`. Negative sign is removed separately. |
| `repo/11.1.3/dist/bignumber.cjs:2775–2782` | `P.toFormat`: `g1 > 0` guards the assignment of an integer-only string to `str`. At `g1 = 0`, that assignment is skipped. |
| `repo/11.1.3/dist/bignumber.cjs:2784–2797` | `P.toFormat`: appends separator plus fraction to the retained string, then restores sign/prefix/suffix. |
| `repo/source-cda702b/bignumber.js:2712–2798` | Original `P.toFormat` source, identical relevant code and line numbers to the executed bundle. |
| `repo/9.3.1/bignumber.js:2555–2564,2599–2604` | Comparison `P.toFormat`: accepts options directly and constructs `str` from `intPart` plus fraction, explaining both lack of duplication and absent separator for sparse options. |
| `repo/source-cda702b/doc/API.html:1723–1745` | Historical `toFormat` heading: promises normal fixed-point notation rounded to `dp` places; partial options fall back to `FORMAT`. |
| `repo/source-cda702b/doc/API.html:648–658` | Historical `FORMAT`: distinguishes decimal separator and integer grouping settings. |
| `repo/source-cda702b/test/methods/toFormat.js:3–31` | Historical test wrapper/configuration starts from group size 3; the file has no `groupSize:0` test. |

`evidence/trace.log` contains dynamic values from `experiments/trace.cjs` (which creates `experiments/instrumented-11.1.3.cjs` without modifying originals). For `100000`, group size 0 shows `str="100000.00"` immediately before the append and `str="100000.00.00"` afterward; no integer-branch marker occurs. With group size 3, the marker occurs and the pre-append string is `"100,000"`, yielding `"100,000.00"`. The negative input exhibits the same mechanism before the sign is restored. The observed branch state supports the source explanation directly, beyond inferring cause from output alone.

## Experiment results and remaining uncertainty

1. The reported 11.1.3 symptom reproduces for all three exact inputs; positive grouping, no fractional places, and `toFixed` controls distinguish formatting assembly from arithmetic/rounding. The 9.3.1 sparse-options expectation failed as described; the explicit-separator comparison behaves as predicted.
2. The original unchanged suite passes **65,716/65,716**, including **139/139** `toFormat` checks (`evidence/historical-tests.log`). This does not establish correctness for the missing zero-size case. Historical docs support a single fixed-point fractional part; the duplicate is a defect, not a documented representation.
3. Diagnostic logging observes the predicted retained fractional string and responsible skipped branch. Final reproduction and integrity verification run on untouched release files still show the failure. No production patch was made or needed for diagnosis.

The narrowly assigned defect is fully reproduced and causally demonstrated. Reporter runtime and the linked UI integration remain unverified; neither is required for the report’s explicit standalone CommonJS example. There is no remaining gap in the narrowed defect finding.

## Coordinator verification

Independently reran `node experiments/reproduce.cjs` and `node experiments/verify-artifacts.cjs`, both exit 0, into separate `evidence/coordinator-reproduction.log` and `evidence/coordinator-integrity.log`. Confirmed all three duplicate-fraction failures, positive grouping and decimal-place controls, explicit-separator comparison, and the original sparse-option discrepancies. Verified the executed CommonJS split, integer-only branch and later append at the cited source lines. Original worker evidence was retained.
