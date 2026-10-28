**Bug found — reproduced formatting regression.** Adding the report's JSX attributes with jscodeshift 0.14.0 and its historically available recast 0.21.5 dependency produces exactly the redundant parentheses shown in the report. Babel records that the JSX was parenthesized; recast treats that metadata as a request to print an inner pair, then independently wraps the multiline JSX return argument in an outer pair. The result remains valid JavaScript; the demonstrated defect is unnecessary formatting churn.

The same codemod with jscodeshift 0.13.1/recast 0.20.5 prints the expected single pair. Dependency swaps isolate recast: 0.14.0 with recast 0.20.5 passes, and 0.13.1 with recast 0.21.5 fails. **The minimum allowed recast 0.21.0 does not fail.** Thus the finding concerns the demonstrated historical dependency resolution, not every installation bearing a jscodeshift version number.

## Original observation and expectation

The input is a multiline `<div>` returned inside parentheses, with a nested `<a {...props} />`. The codemod appends `data-foo="bar"` to each JSX opening element. Expected: those two attributes and the original single return wrapper. Actual: an additional pair immediately around `<div>…</div>` inside the return wrapper. The original report provides this minimal reproduction and the 0.13.1→0.14.0 boundary, plus a linked external PR. These were prior hints; the PR, issue comments, timelines, fix history, and later implementations were not consulted.

Historical jscodeshift README (`repo/jscodeshift-014/README.md:9–11`) says the tool tries to preserve original style. Recast README (`repo/recast-0215/README.md:111–117`) explains localized reprinting and allows harmless reformatting when falling back to generic printing. Those docs do not promise byte-identical formatting of changed nodes. The narrower bug judgment rests on the independently demonstrated duplicate wrapper, the older and minimum-printer behavior, and the two distinct printer branches below; it is not a claim that any reformatting violates an exact-output API guarantee.

## Pinned artifacts and actual environment

| Artifact | Identity |
|---|---|
| jscodeshift 0.13.1 npm/source | gitHead `7cf9969c1fed3dcf535aebbc9986c32be9214ffc`; npm SHA-1 `69bfe51e54c831296380585c6d9e733512aecdef` |
| jscodeshift 0.14.0 npm/source | gitHead `dbb56dec86c5249a429b7f248c0f4db3cdb35eae`; npm SHA-1 `7542e6715d6d2e8bde0b4e883f0ccea358b46881` |
| recast 0.20.5 source | npm gitHead `f16d0cbc59c4f765c380ec949ae2c617b6be074d` |
| recast 0.21.5 source | tag `v0.21.5`, SHA `c040f86c92c3ff9ac6b508a463e7e5f60a543c0a` |
| recast 0.21.0 control | exact npm release, tarball SHA-1 `4f2f78d3532a94d8f16c4102f3529f57379b0605`; tag SHA `4b1fc1678fb4d3009be354721366496462d1c85c` |
| Actual runtime | macOS arm64, Node 22.12.0/npm 10.9.0; repeated with official Node 16.17.1 |
| Parser | Both jscodeshift baselines resolve `@babel/parser` 7.19.3; esprima control 4.0.1 |
| AST types | 0.13.1 tree: 0.14.2; 0.14.0 tree: 0.15.2 |

The reporter supplies no lockfile or runtime. Dependencies were reconstructed using `npm install --before=2022-10-05 --save-exact jscodeshift@VERSION`, after 0.14.0's 2022-10-04 publication. Its range is `recast:^0.21.0`, versus `^0.20.4` in 0.13.1. Recast 0.21.5 was already published 2022-09-27. This is a plausible controlled historical environment, not a claim to recover the reporter's exact tree. Full lockfiles, trees, metadata, source archives, and SHA-256 records are retained. The official Node 16 binary checksum matches `evidence/node16-SHASUMS256.txt`. Metadata acquisition included registry version/publication metadata only; no later implementation was inspected.

## How I reproduced and debugged it

From this case directory:

```sh
./experiments/run.sh
node experiments/index.cjs env/v013 experiments/source.js
node experiments/index.cjs env/v014 experiments/source.js
node experiments/trace.cjs env/v014 experiments/source.js
```

`experiments/source.js` is the exact reported source; `experiments/index.cjs` executes the supplied `j(source).find(j.JSXElement).forEach(addAttribute).toSource()` pipeline, with only module/fixture paths and explicit control switches added. This is the reported programmatic pipeline, not a replacement AST algorithm or a CLI substitution. All successful reproduction commands exit 0. The validation prints `PASS: exact original outputs, no-op, whitespace option, historical runtime, and three dependency swaps`.

Decisive 0.14.0 output:

```jsx
  return (
    (<div data-foo="bar">
      <a {...props} data-foo="bar" />
    </div>)
  );
```

I first ran both original releases, inspected parsed JSX metadata, then logged the actual printer decisions with `experiments/trace.cjs`. The compile hook injects `console.error` into the loaded recast JavaScript only in that process; it neither edits the installed originals nor replaces the algorithm. Ordinary validation runs use uninstrumented packages.

## Source cause and verified references

All references below are workspace-relative. The npm CommonJS `.js` files are what Node executes. The TypeScript files under `repo/recast-0215` are the pinned tag source, not executed bundles or generated diagnostics. No claim is made that a fresh TypeScript build was run. The three cited jscodeshift source files match the npm files after newline normalization (npm files use CRLF).

| Link in the execution | Executed artifact and verified lines/function | Corresponding original source |
|---|---|---|
| Parse input using default Babel adapter | `env/v014/node_modules/jscodeshift/src/core.js:75–82`, `fromSource`; `env/v014/node_modules/jscodeshift/parser/babel5Compat.js:14–36,44–48`, adapter `parse` | `repo/jscodeshift-014/src/core.js`, `repo/jscodeshift-014/parser/babel5Compat.js`, same lines |
| Preserve parentheses as metadata | `env/v014/node_modules/@babel/parser/lib/index.js:13649–13654`, `wrapParenthesis`: sets `extra.parenthesized=true`, `parenStart=87` | npm parser is a distributed generated artifact; separate Babel development source was not acquired |
| Remember original AST | `env/v014/node_modules/recast/lib/parser.js:124–147`, `TreeCopier.copy`, creates `.original` | `repo/recast-0215/lib/parser.ts:151–185`, `TreeCopier.prototype.copy` |
| Pass transformed tree to printer | `env/v014/node_modules/jscodeshift/src/Collection.js:173–181`, `Collection.toSource` | `repo/jscodeshift-014/src/Collection.js`, same lines |
| Changed attributes require child reprints, and then generic return printing | `env/v014/node_modules/recast/lib/patcher.js:247–268`, `findArrayReprints`; `:340–385`, `findChildReprints` | `repo/recast-0215/lib/patcher.ts:324–353,449–507` |
| Original-path subtree changes parenthesis detection | `env/v014/node_modules/recast/lib/patcher.js:214–233`, `findReprints`, roots old path at `oldNode`; `env/v014/node_modules/recast/lib/fast-path.js:189–252`, `hasParens`, `getPrevToken`, `getNextToken` | `repo/recast-0215/lib/patcher.ts:285–306`; `repo/recast-0215/lib/fast-path.ts:238–309` |
| Request inner pair from Babel metadata | `env/v014/node_modules/recast/lib/fast-path.js:255–287`, `FastPath.needsParens`, especially 283–284 returns true | `repo/recast-0215/lib/fast-path.ts:314–358`, especially 352–353 |
| Generic fallback and inner pair | `env/v014/node_modules/recast/lib/printer.js:54–80`, nested `print`; `:119–146`, `genericPrint` | `repo/recast-0215/lib/printer.ts:71–129,187–224` |
| Outer pair around multiline JSX return argument | `env/v014/node_modules/recast/lib/printer.js:473–490`, `genericPrintNoParens` ReturnStatement case | `repo/recast-0215/lib/printer.ts:657–677` |
| Pre-regression metadata decision | `env/v013/node_modules/recast/lib/fast-path.js:282–285`, `FastPath.needsParens` returns false for metadata-marked nodes | `repo/recast-0205/lib/fast-path.ts:350–355` |

The runtime trace shows the outer JSX metadata is `{parenthesized:true,parenStart:87}`. During initial traversal, `needsParens=true` and `oldHasParens=true`. Modified descendants force the ReturnStatement to print generically (its comment explains avoiding automatic-semicolon-insertion hazards). When that printer prints its argument, `findReprints` constructs an old path rooted at the JSX node itself. Token access intentionally excludes tokens outside that root, so `oldHasParens=false`. The metadata still yields `needsParens=true`, making `findChildReprints` decline reuse. `genericPrint` then reports `avoidRootParens=false, shouldAddParens=true` and produces `(<div …>…</div>)`. The ReturnStatement case sees multiline JSX and independently adds ` (\n…\n)`. The observed final duplicate is therefore generated by both branches; it is not simply an old pair being blindly left in the source text.

## Controls and results

| Control | Result |
|---|---|
| 0.14.0 no mutation | Original source preserved, one pair |
| 0.14.0 `reuseWhitespace:false` | Redundant pair remains |
| Delete only current JSX `extra.parenthesized` metadata | One pair |
| Explicit esprima parser object | No metadata flag; one pair |
| Input with no initial parentheses | One generated return wrapper; some indentation differs |
| Modify only outer or only inner JSX attributes | Both reproduce duplicate pair |
| jscodeshift 0.14.0 + recast 0.20.5 | One pair |
| jscodeshift 0.13.1 + recast 0.21.5 | Duplicate pair |
| jscodeshift 0.14.0 + recast 0.21.0 | One pair |
| Node 16.17.1 with original two trees | Byte-identical to Node 22 baseline outputs |

The swaps override only jscodeshift's `require('recast')` resolution using the actual other dependency tree; recast's own dependencies travel with that selected package. They establish responsibility in the recast subtree. The executed metadata branch plus metadata deletion and identical Babel parser versions narrow the specific mechanism further. No production repair was attempted.

## Remaining limits

The exact reporter lockfile/runtime and first bad recast subrelease are unknown. Neither is needed for the narrowed reproduction and causal conclusion. The esprima and metadata-deletion variants are diagnostics, not recommended production behavior. No security behavior was investigated. No required work remains for this formatting diagnosis.

## Experiment notes recorded while working

Investigation in progress: the report alleges redundant parentheses after adding JSX attributes in jscodeshift 0.14.0, versus 0.13.1. The original report supplies a complete reproduction and identifies the release boundary; it does not identify a responsible dependency or fix. I have not accessed the linked PR or issue discussion.

Environment reconstruction: exact npm releases, dependency resolution restricted to packages published before 2022-10-05 (the day after 0.14.0 release). This is a controlled historical reconstruction, not the reporter's unknown lockfile/runtime. Actual host runtime initially Node 22.12.0/npm 10.9.0.

Experiment 1 hypothesis: the original codemod will preserve a single parenthesis pair in 0.13.1 and introduce a second pair in 0.14.0. No-op printing should preserve the input. Next: run original code plus no-op and option/input controls after installation.

Experiment 1 result: the original input/codemod reproduces the expected 0.13.1 and reported 0.14.0 outputs exactly (apart from console.log's final newline), exit 0. Resolved printers are recast 0.20.5 and 0.21.5 respectively. An initial control invocation mistakenly treated `--noop`/`--reuse-false` as a filename; those ENOENT errors are harness invocation errors, not the issue. Controls will pass the fixture explicitly.

Experiment 2 hypothesis: Babel's `extra.parenthesized` metadata is involved in new printer decisions, and the redundant pair is produced while reprinting JSX, then surrounded again by the ReturnStatement printer. Predict: no-op remains unchanged; deleting parenthesized metadata or using esprima removes inner pair. A source without original parentheses should not gain two pairs. Instrument the actually loaded JS printer/patcher via a compile hook, without editing installed originals.

Experiment 2 result: deleting only `extra.parenthesized` removes the inner parentheses; no-op is unchanged, `reuseWhitespace:false` does not help, and inputs without initial parentheses do not acquire a second pair. Both outer-only and inner-only attribute changes trigger the defect. An initial `withParser('esprima')` control was invalid: that string is not supported by this jscodeshift version and falls back to Babel. Corrected to pass recast's actual esprima parser object; that control has no `extra` metadata and prints one pair. Both the initial misleading observation and the correction are retained here.

Experiment 3 hypothesis: the dependency printer, rather than the jscodeshift traversal itself, causes the regression. Predict: holding jscodeshift 0.14.0 fixed and selecting recast 0.20.5 removes the symptom; holding jscodeshift 0.13.1 fixed and selecting 0.21.5 adds it. Also check the minimum declared recast 0.21.0, without assuming every allowed release fails. Repeat on official Node 16.17.1.

Experiment 3 result: both dependency swaps behave as predicted. Minimum recast 0.21.0 prints the expected single pair; therefore this is not a claim about all resolutions permitted by jscodeshift 0.14.0. Recast 0.21.5 was published 2022-09-27, before jscodeshift 0.14.0 on 2022-10-04. Node 16.17.1 reproduces both baseline outputs byte-for-byte. Initial npm lookup of a platform-specific Node package failed with E404; the official nodejs.org binary was acquired instead and SHA-256 verified.

Acquisition note: the initial non-escalated npm metadata lookup exited 1 with `ENOTFOUND registry.npmjs.org` under restricted networking. Authorized network escalation succeeded; all package installs above then completed. This was a setup failure, not a codemod result. Final validation was rerun successfully after the report/source-reference checks.

## Coordinator verification

Independently reran `node experiments/validate.cjs`, exit 0: exact before/after output, no-op and whitespace controls, historical Node runtime, and all three printer-dependency swaps passed their assertions. Fresh log: `evidence/coordinator-validation.log`. Verified the executed metadata branch, generic inner-parenthesis wrapping and independent multiline-JSX ReturnStatement wrapper at the cited recast lines. Expanded critical abbreviated file references. The minimum-printer counterexample remains explicit, so this verdict is limited to the demonstrated historical dependency resolution.
