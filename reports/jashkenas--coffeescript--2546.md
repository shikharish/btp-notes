# Bug found: `./` truncates compiler output folders

The real CoffeeScript 1.3.3 CLI reproduces the reported `llections`, `dels`, and `ews` folders. Traversal removes the input `./` prefix, but output-path calculation still removes its two-character length from the folder names. `.` and explicit root paths preserve the names.

The original report describes `coffee -co ../js ./` run inside `src`, producing `llections`, `dels`, and `ews` instead of `collections`, `models`, and `views`. It supplies neither version nor file contents/runtime. The original record is a pull request; only its frozen original body and provenance were read. No PR patch, discussion, commits, solution history, later implementation or other case was consulted.

## Historical reconstruction

Original creation: 2012-09-12T19:37:59Z. npm metadata identifies coffee-script 1.3.3 (2012-05-15T16:36:07.179Z) as the last published release before that date. Its tarball SHA-1 is `150d6b4cb522894369efed6a2101c20bc7f4a4f4`, matching npm. Official tag `1.3.3` resolves to source commit `79492aab362e7af0279579d69c6d68525bbb7147`. The npm `command.js` is byte-identical to the release source's checked-in generated `lib/coffee-script/command.js`.

Node v0.8.9 (2012-09-11) is the last stable Node release before the report, acquired from official nodejs.org. It runs on this Darwin arm64 host using the downloaded darwin-x64 executable. This is a justified reconstruction, not identification of the reporter's actual environment. The package has no runtime dependencies. Existing Node v22.12.0 runs `--version` but lacks historical `path.exists`; the actual reproduction will use v0.8.9 without shims. An initially downloaded v0.8.8 archive was superseded before use after checking release dates.

## Experiments and predictions

1. Hypothesis: `path.normalize('./')` preserves `./`, but recursive `path.join` removes that prefix. `outputPath` then incorrectly slices two characters from each relative source directory. Prediction: the real CLI exits zero and writes exactly the three truncated directory names from the report. Control `.` enters the explicit special case and preserves names. Explicit absolute `src` and parent-directory `src/` inputs should preserve directory names as well.
2. Planned causal observation: instrument only a separate copy of the generated command module to print the actual `source`, `base`, `srcDir`, `baseDir`, and result. Prediction: faulty base is `./`, `srcDir` is e.g. `models`, and `baseDir` is `dels`. Keep the unmodified package and release source intact.

## Finding: Bug found

The exact reported folder truncation was reproduced by the unmodified CoffeeScript 1.3.3 CLI. `./` and `.` name the same input directory, but only `.` receives the compiler's special treatment. With `./`, the compiler removes two characters from directory names that no longer contain that prefix. All three files compile successfully; the defect is their destination, not compilation failure.

## How I reproduced and debugged it

From this case directory, run:

```sh
python3 experiments/run.py > evidence/reproduction.log 2>&1
```

The script creates a fresh fixture under `tmp/fixture/src` with `collections/init.coffee`, `models/init.coffee`, and `views/init.coffee`. Since the report omitted file contents, each file contains `module.exports = "<directory>"`, making the compiled file's origin observable. It invokes the downloaded real Node executable on `env/package/bin/coffee`, with working directory `tmp/fixture/src`, and the exact compiler arguments `-co ../js ./`. Thus the fully spelled command is equivalent to:

```sh
cd tmp/fixture/src
../../../env/node-v0.8.9-darwin-x64/bin/node ../../../env/package/bin/coffee -co ../js ./
```

The Python driver uses absolute executable paths, captures exit codes/stdout/stderr, and lists and reads actual emitted files. It then resets only the fixture output directory between controls. The instrumented module is created separately at `tmp/instrumented-package/lib/coffee-script/command.js`; a single diagnostic print is inserted immediately before the return in `outputPath`. No behavior-changing patch or production repair was made. The original source/package remain unmodified.

| Input and working directory | Actual output paths relative to fixture | Exit |
| --- | --- | --- |
| `-co ../js ./`, inside `src` | `js/llections/init.js`, `js/dels/init.js`, `js/ews/init.js` | 0 |
| `-co ../js .`, inside `src` | `js/collections/init.js`, `js/models/init.js`, `js/views/init.js` | 0 |
| `-co ../js <absolute src path>`, inside `src` | same preserved names | 0 |
| `-co js src/`, inside fixture parent | same preserved names | 0 |

Every run emits only the historical Node deprecation notice `path.exists is now called fs.exists` (with backticks around `fs.exists` in the raw log). It does not prevent writes. Actual JS contents identify the expected source collection/model/view. Copies of the emitted outputs are saved under `evidence/outputs-dot-slash`, `evidence/outputs-dot`, `evidence/outputs-absolute`, and `evidence/outputs-parent-explicit`.

The separate instrumented run observed these decisive values:

```text
source=models/init.coffee base=./ srcDir=models baseDir=dels result=../js/dels/init.js
source=collections/init.coffee base=./ srcDir=collections baseDir=llections result=../js/llections/init.js
source=views/init.coffee base=./ srcDir=views baseDir=ews result=../js/ews/init.js
```

For `.` the observed base is `.`, and `baseDir` equals the complete `srcDir` in each case. Experiment 1 and experiment 2 both matched their predictions. The absolute and parent explicit directory controls also show this is tied to spelling of the selected root, rather than invalid CoffeeScript, file naming, or general output-directory creation.

## Source trace (verified pinned files)

The executed package is `env/package`; `repo/src/command.coffee` is original CoffeeScript source and `repo/lib/coffee-script/command.js` is the release's generated JavaScript. The generated `command.js` matches the npm package byte for byte. Line references below point to the pristine versions, not the instrumented copy.

| Link | Original source | Executed package | Effect |
| --- | --- | --- | --- |
| CLI entry | `repo/bin/coffee:3–7` | `env/package/bin/coffee:3–7` | Loads the command module and calls `run`. |
| Argument setup | `repo/src/command.coffee:307–314`, `parseOptions` | `env/package/lib/coffee-script/command.js:458–469`, `parseOptions` | Sets compile/output options and the source arguments. |
| Root base | `repo/src/command.coffee:62–79`, `exports.run` | `env/package/lib/coffee-script/command.js:49–86`, `exports.run` | Calls `compilePath(source, true, path.normalize(source))`; the traced base for `./` is `./`. |
| Recursive paths | `repo/src/command.coffee:84–111`, `compilePath` (especially 105) | `env/package/lib/coffee-script/command.js:91–150`, `compilePath` (especially 136) | Recurses through `path.join(source,file)` while keeping `base` unchanged. Joined child paths lose initial `./`, yielding e.g. `models/init.coffee`. |
| Actual compilation | `repo/src/command.coffee:120–136`, `compileScript` | `env/package/lib/coffee-script/command.js:159–185`, `compileScript` | Compiles file contents, then calls `writeJs` with the original base. |
| Wrong destination | `repo/src/command.coffee:257–262`, `outputPath` (especially 260) | `env/package/lib/coffee-script/command.js:388–394`, `outputPath` (especially 392) | Special-cases exactly `base === '.'`; otherwise removes `base.length` characters from `srcDir`. `./` has length 2, so `models.substring(2)` is `dels`. Joins that result to the output directory and filename. |
| File write | `repo/src/command.coffee:267–278`, `writeJs` | `env/package/lib/coffee-script/command.js:397–419`, `writeJs` | Uses that destination, creates its directory when needed, and writes the compiled JS. Actual files confirm this last step. |

The observed mismatch is between a retained relative-root spelling and normalized recursive child paths. The conditional's assumption—that every non-`.` base is a prefix still present in `srcDir`—does not hold for `./`.

## Why this is a defect

Pinned historical documentation explicitly promises a parallel directory tree: `repo/index.html:417–421` describes compiling a tree in `src` into a parallel tree in `lib`, using `coffee --compile --output lib/ src/`. The same release's changelog at `repo/index.html:2644–2645` says the `coffee` command preserves directory structure when compiling a directory full of scripts. Its `--output` description is at `repo/index.html:314–318`. Removing arbitrary first letters of real folder names violates that behavior; the equivalent-root and explicit-path controls demonstrate the intended result with the same compiler and same files.

## Evidence and limits

- `evidence/reproduction.log`: real CLI commands, working directories, versions, exit statuses, complete actual filenames/content, and separate diagnostic traces.
- `experiments/run.py`: runnable fixture, integration runs, and separate diagnostic instrumentation.
- `evidence/npm-metadata.json`, `evidence/tag-1.3.3.json`, and `evidence/node-release-index.json`: version selection and source identity provenance. Full registries are retained only as metadata; later implementations were not inspected.
- `evidence/coffee-script-1.3.3.tgz`, `evidence/source-1.3.3.tgz`, and `evidence/node-v0.8.9-darwin-x64.tar.gz`: acquired artifacts. Source archive local SHA-1: `5cd3889d7c732080469adb985ef516ec46929b35`; Node archive local SHA-1: `68aa7341807fb114f334151b7a1c8859e96b83d4`. These last two are locally computed identities, not independent published-integrity checks.
- `evidence/environment.log`: host/runtime identity, artifact hashes and byte-identity check of baseline command modules.

The reporter's exact version, platform, Node version, and file contents are unknown. This investigation proves the exact reported symptom and cause in a release available at the original date, not that the reporter definitely ran that release. No original version was inferred from the forbidden pull-request change. No material ambiguity remains for the demonstrated 1.3.3 path defect. Initial network access needed approved escalation; no cybersecurity safeguard was encountered. No prior answers or solution hints were used; the frozen original report itself names `baseDir` in its title, which was the only supplied causal hint.

## Coordinator verification

Independently ran the unmodified historical CLI and all four source-root controls through `python3 experiments/coordinator-verify-relative.py`, exit 0, on a separate fixture. The primary command retains the original `-co ../js ./` arguments. Confirmed exact truncated folder names only for ./ and correct names for dot, absolute source and parent-explicit source controls. Fresh commands, outputs and asserted filenames are in `evidence/coordinator-results.json` and `evidence/coordinator-relative-reproduction.log`. Checked the pinned traversal, outputPath substring and historical parallel-directory-tree documentation. An initial independent driver used a space-containing absolute output directory and produced ENOENT instead of files; its assertion failed despite compiler exit 0. That setup deviation is retained in `evidence/coordinator-reproduction.log` and `experiments/coordinator-verify-absolute-output.py`, and is not counted as the reported failure. Using the original relative output syntax avoids that deviation. Original worker evidence is unchanged.
