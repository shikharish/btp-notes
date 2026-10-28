Numeric tab names reorder tabs in React Navigation 5.0.0. The real bottom-tab navigator rendered children named `779001`, then `12345`, as `12345`, then `779001`. Core converts the ordered screen configuration array into an object and reconstructs route order with `Object.keys`; JavaScript enumerates array-index property names numerically. The tab router and tab bar preserve that already changed order.

**Finding:** bug found, narrowed to canonical array-index string names, demonstrated in the published 5.0.0 packages using a web host and React renderer. “Fully numerical strings” in the report is too broad: leading zeros and numbers outside the array-index range do not reorder in the controls.

## Provenance and environment

The input names versions 5.0.0–5.0.5 without identifying the package, exact dependency tree, OS, JavaScript engine or commit. I reconstructed a 5.0.0 environment from published original artifacts: `@react-navigation/core`, `routers`, `native`, and `bottom-tabs`, each exactly 5.0.0. Core 5.0.5 metadata returned HTTP 404, so I used the explicitly reported 5.0.0 rather than guessing which package the upper version bound refers to.

- Core tarball: `https://registry.npmjs.org/@react-navigation/core/-/core-5.0.0.tgz`, published 2020-02-05T14:03:18.109Z.
- Source artifact SHA-1: `66f5b948a92e7a7f913d2acdbe4e5de516c836cb`, verified against registry metadata.
- Source artifact SHA-256: `8027020c92a2fe8c1f72a8f9668ca06f7a53cface6cc18091a3e96fb88f582af`.
- No Git commit SHA is supplied in this package's registry metadata. The immutable release tarball and hashes pin the actual source used; this is a release reconstruction, not a claim to know the reporter's checkout.
- Actual tools: Node 22.12.0, npm 10.9.0, React/React Test Renderer 16.9.0; Babel core 7.8.4/register 7.8.3 loads historical JSX web entry points.
- Host: `react-native` deliberately aliases React Native Web 0.12.0; react-native-screens 2.0.0-beta.2 uses its actual web entry point and `enableScreens(false)` to select its built-in View fallback. Safe-area-context ultimately pinned 0.6.2, matching bottom-tabs' declared range. Other transitive resolutions are recorded exactly in `env/package-lock.json` and `evidence/dependency-tree.json`; they are not represented as the reporter's dependency tree.

Original-body hints were present before investigation: it identifies `useNavigationBuilder.tsx` line 190 and `Object.keys`, proposes mapping children to names, and gives the nonnumeric-name workaround. I used these as disclosed hypotheses. No issue comments, timeline, fix commits/history, later source implementations, sibling cases or prior answers were consulted. The linked Snack was not recovered; the harness reconstructs its stated minimal condition from the body.

## Observation, expectation and scope

Expected: Screen child order determines the displayed tab sequence, including when non-empty string screen names happen to be numeric. Actual: canonical unsigned array-index names (`0` through `4294967294`) are enumerated first in ascending order; other string names follow insertion order. This is an unintended change of route sequence driven by an identifier's spelling. Historical core accepts every non-empty string as a screen name (`getRouteConfigsFromChildren`, lines 89–99); TabRouter initializes routes by mapping its supplied `routeNames` in sequence. The array extraction and downstream ordered mappings support preserving declaration order; there is no numeric-name sorting option in this path. This defect conclusion uses that historical code contract and controlled output, not an assertion that an explicit prose guarantee was recovered.

This is an actual released BottomTabNavigator → core hook → TabRouter → BottomTabView → BottomTabBar → BottomTabItem integration. React Test Renderer executes the real components and their host text output. It is not a copied Object.keys algorithm or merely a successful install. It does not establish on-device pixels, native layout or the exact Snack environment.

## How I reproduced and debugged it

In this case directory, original source was acquired with `curl -L --fail https://registry.npmjs.org/@react-navigation/core/-/core-5.0.0.tgz -o evidence/core-5.0.0.tgz`, extracted with `tar -xzf evidence/core-5.0.0.tgz -C repo`, and hashed with `shasum -a 1` / `shasum -a 256`. Registry access initially failed DNS in the sandbox; a network escalation succeeded. Dependencies were installed locally using npm with explicit versions, `--legacy-peer-deps --ignore-scripts --no-audit --no-fund`. Babel and safe-area alignment install logs are retained.

Runnable replay, with the saved dependency installation:

```sh
./experiments/run.sh
```

For a fresh local dependency installation, first run:

```sh
cd env
npm ci --legacy-peer-deps --ignore-scripts --no-audit --no-fund
cd ..
./experiments/run.sh
```

The replay runs `node experiments/reproduce.cjs`, then `TRACE_CORE=1 node experiments/reproduce.cjs`, then an uninstrumented recurrence. Each exits 0 and prints `PASS: 18 real BottomTabNavigator/BottomTabBar mounts, all predicted states and rendered item labels verified.` An assertion failure exits nonzero. Those assertions verify the observed bug and controls; PASS does not mean declaration order was preserved.

I inspected source with `rg`, `nl -ba`, and `sed`, compared the installed executed bundle with the original tarball using `cmp` and a byte-equality assertion, and used React renderer's tree/host text inspection. No interactive debugger was used. Diagnostic mode loads a logging-only copy of the published core bundle through Node's module loader, preserving the original filename for relative imports. It saves that exact generated text as `experiments/core-trace.generated.cjs`; original installed source is never edited.

## Controlled experiments

Before experiment 1, the prediction was that reverse integer-index names would reorder, whereas prefixed and noncanonical numeric strings would retain child order. All six input cases were mounted independently three times, with fresh trees unmounted after each run. Source components, navigator options and renderer stayed fixed; only names changed.

| Child names in order | Observed state / rendered host text |
|---|---|
| `779001`, `12345` | `12345`, `779001` |
| `10`, `2`, `1` | `1`, `2`, `10` |
| `tab779001`, `tab12345` | same as children |
| `0779001`, `012345` | same as children |
| `5000000000`, `4294967295` | same as children |
| `tabA`, `10`, `tabB`, `2` | `2`, `10`, `tabA`, `tabB` |

The prefixed names are a direct negative control and reproduce the reported workaround. Leading-zero and above-index-range cases challenge the broader “all numerical strings” claim. Mixed input shows numeric properties move ahead of other properties as well as sorting among themselves. The same changed order appears in `routeNames`, `state.routes`, the BottomTabItem label props, and actual host text. Every mount uses index 0, so the altered first route also becomes the initial tab in this setup.

Initial setup failure: `react-native-screens` had platform-specific entry points, requiring selection of its web module. Its default optimized Screen then tried imperative DOM styling against renderer nodes and failed before completion. The retained stack is `evidence/first-renderer-setup-failure.log`. I selected the package's supported `enableScreens(false)` path; no errors/assertions were suppressed. The first safe-area pin 0.7.3 was outside the navigator's declared range; it was corrected to 0.6.2 and all recorded final experiments rerun. `npm ls --all` still exits 1 because native packages see the intentional `react-native-web` alias as a React Native peer-version mismatch; this is recorded in `evidence/dependency-tree-errors.log`, not treated as reproduction.

Before experiment 2, the prediction was that logging at the actual core insertion and Object.keys statements would show child order preserved until enumeration. `evidence/core-trace.log` confirms:

```text
{"stage":"insert screen","name":"779001"}
{"stage":"insert screen","name":"12345"}
{"stage":"Object.keys(screens)","routeNames":["12345","779001"]}
```

The next real component output reports identical reordered state and host text. All controls behave identically with logging enabled. The final uninstrumented recurrence again completes 18 mounts, ruling out the diagnostic loader as the source of the symptom. `evidence/baseline-integrity.txt` confirms the executed core bundle still equals the original tarball bundle (bundle SHA-256 `18cef5ffaadab891a4cba83813960879cc4f13819a537cead6f8b4ff13d5c602`). No behavior-changing source patch was needed.

## Verified causal source trace

All paths below are relative to this case directory. These are original published TypeScript sources unless marked otherwise; executed CommonJS bundles are minified to line 1, with source maps distributed alongside them.

| Link | File and verified lines | Function / observation |
|---|---|---|
| Children enter core | `env/node_modules/@react-navigation/bottom-tabs/src/navigators/createBottomTabNavigator.tsx:23–48` | `BottomTabNavigator` passes children to `useNavigationBuilder(TabRouter, …)` and passes resulting state to BottomTabView. |
| Preserve child order while extracting | `repo/package/src/useNavigationBuilder.tsx:55–87` | `getRouteConfigsFromChildren` uses React.Children.toArray and pushes Screen props sequentially; fragments recurse. |
| Accept numeric names | `repo/package/src/useNavigationBuilder.tsx:89–99` | `getRouteConfigsFromChildren` validates non-empty strings without excluding numeric spellings. |
| Introduce reorder | `repo/package/src/useNavigationBuilder.tsx:177–190` | `useNavigationBuilder` reduces configs into `screens`, then uses `Object.keys(screens)` as routeNames. Diagnostic insertion/order evidence verifies the change here. |
| Pass changed list into state | `repo/package/src/useNavigationBuilder.tsx:250–259` | `useNavigationBuilder` invokes router.getInitialState with routeNames on the fresh mount. |
| Preserve changed order | `env/node_modules/@react-navigation/routers/src/TabRouter.tsx:94–125` | `TabRouter.getInitialState` maps routeNames into routes and returns both arrays unchanged in sequence; default focus index 0. |
| Pass state to bar | `env/node_modules/@react-navigation/bottom-tabs/src/views/BottomTabView.tsx:69–91` | `BottomTabView.renderTabBar` defaults to BottomTabBar and supplies the state. |
| Render each ordered item | `env/node_modules/@react-navigation/bottom-tabs/src/views/BottomTabBar.tsx:194–255` | `BottomTabBar` maps routes and derives label from route.name when options do not override it. |
| Emit visible label text | `env/node_modules/@react-navigation/bottom-tabs/src/views/BottomTabItem.tsx:141–161` | `BottomTabItem.renderLabel` places string label into Animated.Text; harness verifies host strings in this order. |
| Actual executing ordering statement | `env/node_modules/@react-navigation/core/lib/commonjs/useNavigationBuilder.js:1` | Published `useNavigationBuilder` bundle has `acc[curr.name]=curr` followed by `var routeNames=Object.keys(screens)`; byte-identical to `repo/package/lib/commonjs/useNavigationBuilder.js:1`. |

Raw evidence: `evidence/reproduction.log` and `evidence/recurrence.log` (18 mounts each), `evidence/core-trace.log` (same cases with insertion/enumeration logging), `evidence/run-environment.txt` (tools and successful exit codes), registry/package metadata, source tarball and hashes, dependency tree and installation logs. The first-renderer failure is retained as setup evidence.

Remaining gaps are historical/platform fidelity: no reporter lockfile or Git SHA, no recovered Snack, and no Android/iOS run. These do not leave the narrowed ordering cause unresolved because the original core behavior and real tab-rendering pipeline have both been exercised, with controls and clean recurrence. No claims are made about every release through 5.0.5 or every numeric string.

## Coordinator verification

Independently reran `node experiments/reproduce.cjs` (exit 0): all 18 real navigator/bar mounts again matched the reported reorder and all negative controls, including rendered host text. Checked the original child extraction, object enumeration, router initialization and tab rendering source links. Fresh evidence: `evidence/coordinator-reproduction.log`.
