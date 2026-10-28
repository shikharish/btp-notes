SWC 1.2.135 turns valid `console.log(10000..toString());` into invalid `console.log(10e3..toString())` with the reported configuration. Numeric printing shortens 10000 to `10e3`, but member access independently adds two dots because the value is an integer. The exponent literal needs only the property-access dot. This is a demonstrated compiler formatting defect, even with compression and mangling disabled.

## How I reproduced and debugged it
I downloaded the reported npm release and its exact gitHead source archive, then ran `transformSync` on the original input and configuration through the published native compiler. I evaluated both input and output using Node's JavaScript parser/runtime, inspected the actual parsed AST, and repeated with `parseSync` → `printSync` to isolate printing. I then varied only printing options, property syntax, target and numeric AST value. Source inspection explains the same output boundaries these controls observe; no compiler source was changed and no production repair was attempted.

Run from this case directory:

```sh
sh experiments/acquire.sh  # only if artifacts are missing
node experiments/reproduce.cjs > evidence/reproduction.json 2> evidence/reproduction.stderr
```

The final command exits 0; `evidence/reproduction.exit` records it. The reported transform itself succeeds, but its output fails evaluation with `SyntaxError: Unexpected token '.'`. Original input and the report's expected `console.log(10e3.toString())` both print `10000`.

## Source and environment
Source SHA: `3bda85e3033a8a6b08cdd59b8adffc1912030c14`, directly from the release's npm `gitHead` metadata in `evidence/npm-metadata.json`. Archive SHA256: `436a36d2714031cf3d0c355a53ab2f1db72016198f197bece52792f98b9332e2`. Source is extracted under `experiments/source/` unchanged. `experiments/runtime/package-lock.json` records release URLs and package integrity values; the runtime installs exactly `@swc/core@1.2.135` and `@swc/core-darwin-arm64@1.2.135`.

Actual experiment runtime: Node v22.12.0, npm 10.9.0, macOS/darwin arm64. Published binary `experiments/runtime/node_modules/@swc/core-darwin-arm64/swc.darwin-arm64.node` SHA256: `2be69d6f6d9a258056c50bbaf0e53feb09999e60f273c1f157bce97d8dad43ad`. The JavaScript wrapper `experiments/runtime/node_modules/@swc/core/index.js:125–137`, `Compiler.transformSync`, delegates to the native binding; `binding.js:122–129` selects the darwin arm64 package. These are executed package artifacts, distinct from the cited Rust source. I did not compile the Rust source or establish a bit-for-bit source build match; provenance is the publisher's release metadata. Rust toolchain/build dependencies were not run.

The first network attempt failed with npm ENOTFOUND in the restricted environment; an authorized network escalation acquired the exact artifacts. A preliminary shell in the default parent directory reported Node v22.23.2/npm 10.9.8; those were not the versions executing the case. The explicit case commands and saved JSON establish the actual runtime above.

## Causal source trace
All Rust paths below are workspace-relative pinned original source, not native binary addresses. Line references were checked against extracted files; decisive excerpts are saved in `evidence/source-excerpts.txt`.

| Link | Source and function | Verified behavior |
|---|---|---|
| Native transformation | `experiments/source/crates/node/src/transform.rs:116–144`, `transform_sync` | String input creates a source file and calls `Compiler.process_js_file`. |
| Parsed number | `experiments/source/crates/swc_ecma_parser/src/parser/expr.rs:1733,1760–1764`, `parse_lit` | `Token::Num(value)` becomes a Number with span and numeric value. Observed AST has NumericLiteral value 10000 and identifier property `toString` (`evidence/parsed-ast.json`). |
| Transformation to printing | `experiments/source/crates/swc/src/lib.rs:1061–1098`, `Compiler.process_js_inner` | Applies configured passes and calls `self.print` with `config.minify`. |
| Emitter config | `experiments/source/crates/swc/src/lib.rs:467,546–558`, `Compiler.print` | Creates `Emitter` with `Config { minify }`; omitted trailing semicolon explains exact output spelling. |
| Shortened literal | `experiments/source/crates/swc_ecma_codegen/src/lib.rs:524–546`, `Emitter.emit_num_lit` | Converts value to a decimal string; when minify=true, no dot/e, ending in four zeros, calculates trailing zero count minus one, truncates and appends exponent. For 10000: `s="10000"`, count=3, `s="10e3"` (static branch evaluation, supported by observed output). |
| Extra dot | `experiments/source/crates/swc_ecma_codegen/src/lib.rs:722–742`, `Emitter.emit_member_expr`; `:759–781`, `Emitter.needs_2dots_for_property_access` | Emits object first, then for identifier access emits an extra dot if helper true and always emits the property dot. Helper returns true immediately for integral numeric value (`value.fract()==0.0`, lines 760–762); it does not inspect the actual shortened spelling or minify option before this return. |
| Independent printer | `experiments/source/crates/node/src/print.rs:77–102`, `print_sync` | Deserializes real AST and invokes the same Compiler.print with minify configuration. |

The code does not literally retain the original lexical dot: it emits a fresh extra dot after emitting `10e3`. That distinction matters because even originally valid exponent input `1e4.toString()` follows the same integer-value branch. Compression is unnecessary to cause this mismatch.

## Decisive controls
Raw outputs and evaluations are in `evidence/reproduction.json`.

| Change from reported case | Actual output / result |
|---|---|
| Original config (es2022) | `console.log(10e3..toString())`; SyntaxError |
| Top-level minify=false, compression still false | `console.log(10000..toString());`; prints 10000 |
| Numeric value 1000 | `console.log(1000..toString())`; prints 1000 |
| Computed property access | `console.log(10e3["toString"]())`; prints 10000 |
| Exponent input `1e4.toString()` | Same invalid `10e3..toString()` |
| Fraction 10000.5 | `console.log(10000.5.toString())`; valid |
| Targets es3/es5/es2015/es2020 | Same invalid output as es2022 |
| Parse then print, minify=false / true | Valid decimal output / invalid exponent output |
| Same AST member, value changed only | 10000 and 100000 invalid (`10e3..`, `10e4..`); 1000, 10001, 10000.5 valid |

These controls separate the exponent shortening branch from the member punctuation branch: shortening is harmless with computed access, and two dots are harmless for ordinary decimal integer spelling. Their combination breaks syntax. The compiler's own parse acceptance plus Node evaluation demonstrate the valid-input/invalid-output regression without requiring a promised exact shortest spelling.

## Limits
This reproduces the reported compiler integration through the exact published Node package, not the playground UI/wasm deployment. Historical reporter OS/Node, binary build toolchain, and wasm artifact are unknown. The secondary compressed-constant scenario/version 1.2.133 was not needed or separately investigated; no claim about that configuration is made. No dynamic Rust branch instrumentation was performed: intermediate string/count values above are static derivations corroborated by real native output and controlled AST printing. No unresolved gap affects the demonstrated 1.2.135 numeric-property formatting defect.

## Original hints and experiment record

Original report supplies the strong solution hint that decimal-to-exponent formatting leaves an extra dot; no comments, fixes, later source, or issue history consulted. `@swc/core@1.2.135` npm metadata records gitHead `3bda85e3033a8a6b08cdd59b8adffc1912030c14`; the source archive is pinned to that SHA. A preliminary environment command accidentally ran in the parent working directory and listed filenames only; no other investigation contents were read. All subsequent case operations use explicit case cwd.

## Experiment notes
1. Hypothesis: the exact reported transform returns `console.log(10e3..toString());`, which JavaScript rejects. Prediction: input evaluates to 10000 while output raises SyntaxError. Controls: no minified output and smaller integer 1000 should remain valid; computed property access should avoid double-dot logic; an explicit exponent input should still fail because decisions depend on numeric value.
2. Hypothesis: the fault is in code generation rather than compression. Prediction: parseSync followed by printSync with minify true reproduces it; minify false succeeds. The original transform has compression/mangling disabled.

Actual first run: all predicted formatting/syntax observations occurred, but the harness returned exit 1 because I incorrectly asserted a trailing semicolon. SWC omits that semicolon with minify=true; the issue's actual output likewise omits it. `evidence/first-run.json` preserves the observations. Correcting only the assertion (not compiler behavior), rerun the same cases and add these controls:
3. Hypothesis: changing codegen target leaves the failure unchanged; AST numeric value alone selects the wrong dot behavior. Prediction: targets es3/es5/es2015/es2020 fail identically. Holding the parsed member structure fixed and changing only NumericLiteral.value, values 10000/100000 fail, 1000/10001/10000.5 pass. Independently evaluate the report's expected spelling to demonstrate its validity and value.

Actual final run: all three hypotheses matched their predictions except the first-run semicolon expectation documented above. Final harness exit 0, empty stderr; every input is valid, four target controls reproduce the same SyntaxError, and all computed/nonminified/fraction controls evaluate successfully. Changing only AST value shows the predicted decimal/exponent boundary.

## Coordinator verification

Independently reran all 18 saved cases under Node v22.12.0 and SWC 1.2.135; harness exit 0. Valid original input prints 10000, while exact reported transformed output raises SyntaxError. Verified the three cited Rust code-generation branches against the pinned files. Running from `tmp/coordinator/` retained the worker original output/config/AST; fresh results are in `evidence/coordinator-reproduction.json` (stderr empty). Command: `node ../../experiments/reproduce.cjs` from `tmp/coordinator/`, with stdout/stderr directed to those separate evidence files.
