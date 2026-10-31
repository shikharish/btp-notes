# Luna classifier — handoff

**Give your coding agent this directory and the dataset. Nothing else from the investigation workspace is needed.**

Paste this instruction to the agent:

> Read `AGENTS.md` and `README.md`. Classify [INPUT PATH] into [OUTPUT DIRECTORY], using [N reports / the entire dataset]. Check setup, run the offline tests, run the classifier, and verify the output counts. Resume safely if interrupted. Do not change the models or rules. Tell me what completed, what failed, and where the outputs are.

Replace the bracketed values. If the input is not local, the original dataset link is below. Your agent can obtain and prepare it. Authentication may need one action from the collaborator; credentials are not included here.

## Completed run — 31 October 2026

We replaced the Pi integration with the Codex CLI app-server adapter in
`codex_runner.py`. The classification prompts and rules stayed unchanged:
Luna (`gpt-6-luna`) at **high** reasoning identifies report types, and Luna at
**max** reasoning assesses bug-report vagueness. The existing evidence collector,
deterministic grading, saved attempts, and resumable pipeline remain in use.
 We then classified the **first 100 distinct reports
from each file**, running one file at a time with four workers. 

### Report types

All **400 selected reports completed**, with 400 distinct record IDs across the
four files and **zero unresolved technical errors**.

| Input file | Completed | Bug reports | Non-bugs | Change submissions | Unclear |
| --- | ---: | ---: | ---: | ---: | ---: |
| `b0_data_part000.parquet` | 100 | 24 | 50 | 20 | 6 |
| `b1_data_part000.parquet` | 100 | 29 | 18 | 53 | 0 |
| `b1_data_part001.parquet` | 100 | 11 | 34 | 51 | 4 |
| `b1_data_part002.parquet` | 100 | 36 | 30 | 33 | 1 |
| **Total** | **400** | **100** | **132** | **157** | **11** |

Of these selected reports, **25% alleged a bug**, **33% were non-bugs**,
**39.25% submitted an implemented change**, and **2.75% had an unclear purpose**.
These categories describe what each document is doing; a bug label does not
establish that a software defect exists.

### How well the bug reports were specified

Only the 100 reports classified as bugs received a vagueness assessment.
The percentages below are therefore percentages of those 100 bug reports.

| Assessment | Count | Meaning |
| --- | ---: | --- |
| **1 — Clear** | 57 (57%) | Defines a concrete attempt and recognizable actual and expected outcomes. |
| **2 — Partly specified** | 26 (26%) | Gives useful information, but an essential element is incomplete. |
| **3 — Vague** | 9 (9%) | Gives no concrete starting action, or lacks both recognizable actual and expected outcomes. |
| **Pending** | 8 (8%) | Necessary evidence or selection of the problem target remains unresolved. |

Thus, 57 bug reports were clear under the fixed rubric, 35 were partly specified
or vague, and 8 could not yet receive a numeric grade. **Pending is a valid
completed evidence status**, separate from a technical failure; those eight
reports were not automatically marked vague. A clear grade does not guarantee
that someone can successfully reproduce the bug.

### Validation, retries, and saved results

Four batch attempts failed strict output validation: three used placeholder
record IDs and one contained an altered ID. We inspected those failures and
resumed the same jobs with `--retry-failed`. Completed labels were retained,
and every failed attempt remains saved. All four jobs ultimately finished with
empty `errors.jsonl` files and `failed_or_unfinished = 0`.

Final checks confirmed that each job's 100 output IDs exactly matched its first
100 distinct input reports, that source mappings covered those reports, that
category totals agreed with the saved labels, and that numeric/pending bug
grades agreed with the fixed Python mapping.

Results are under `runs/luna-100-each/`, with a subfolder matching each input
filename without `.parquet`. Each contains `labels.jsonl`, `records.csv`,
`summary.json`, `errors.jsonl`, `state.sqlite`, `attempts/`, and `evidence/`.
The combined counts and coverage checks are in
`runs/luna-100-each/summary-all.json`. These generated files stay local and are
excluded from Git by the source-only `.gitignore`.

This was an operational classification run. The labels have not been checked
against human ground truth, no new accuracy benchmark was performed, and the
results should not be generalized to the full dataset from this ordered subset.

## Fixed pipeline

1. **Report type:** `gpt-6-luna` through Codex’s OpenAI provider, **high** thinking. Categories: `bug`, `no_bug`, `change_submission`, `unclear`.
2. **Only for `bug`:** collect relevant reporter-linked evidence, then use the same Luna model at **max** thinking for the vagueness checks.
3. Code maps those checks to **1 clear**, **2 partly specified**, **3 vague**, or **pending** when necessary evidence/target selection is unresolved.

Ten concurrent workers, up to ten reports per fresh ephemeral Codex thread. Large batches split before inference. Reports are never silently truncated. No reviewers, benchmark loop, Terra, Jev, or tuning step is needed.

The owner has finalized this configuration for now. It is an automatic judgment, not ground truth: the last independent-agent check matched 134/183 numeric cases (73.2%). This handoff is a simplified operational implementation, not a newly benchmarked classifier. Do not rerun the benchmark or change the configuration unless asked.

## Setup and commands

Requires **Linux/macOS (or WSL), Python 3.11+**, the [Codex CLI](https://learn.chatgpt.com/docs/app-server), and access to the exact Luna model through the collaborator's own Codex ChatGPT login. The adapter was checked against Codex CLI 0.162.0. Pi is not required. It uses the Codex app-server stdio protocol with experimental dynamic tools and environment selection; incompatible versions fail rather than fall back.

Authenticate with `codex login` if needed. Never copy another person's `auth.json`, print tokens, or substitute an available model when Luna/max is missing. The CLI uses its normal login; the adapter never opens or copies credential files.

From this handoff directory (a Git checkout is not required):

```sh
# Offline tests: no model or web requests.
python3 -m unittest discover -s . -p 'test_*.py' -v

# Verify login, model catalog and resolved model/thinking selection; no inference request.
python3 classify.py check

# Classify the first 100 distinct report texts.
uv run --no-project --with duckdb==2.0.0 python classify.py run \
  data/reports --out runs/luna --limit 100

# Only when the owner requested the whole dataset:
uv run --no-project --with duckdb==2.0.0 python classify.py run \
  data/reports --out runs/luna --all
```

The Parquet examples use `uv` to supply DuckDB 2.0.0; an agent can install `uv` or use its own virtual environment with that dependency. For JSONL, plain `python` works; DuckDB is needed only for Parquet. `--workers 1` through `--workers 10` can reduce load. Models and classification prompts are fixed; there is no model-selection switch.

Use the **same command and output directory** to resume. Completed answers are reused. If a previous attempt failed, first inspect `attempts/`, then explicitly add `--retry-failed`. Earlier attempts remain saved. A failure stops scheduling new batches while already-running batches finish; this avoids flooding a quota-limited service. Never delete good answers to try for a better score.

## Dataset and input

Original archive, about **1.8 GB**:

https://drive.google.com/file/d/1YJ6POTgzfPPnli4nPHSgHKBH73NbEQaG/view

The agent may download it using a public-download tool such as `gdown`, inspect the ZIP before extraction, and extract it under `data/`. Do not execute anything from the archive. Expect **27 `*_data_part*.parquet` files**, with 5,966,490 raw rows in the original snapshot. If the download needs permission, ask the collaborator for access or a local copy—do not invent another dataset. Allow disk space for the archive, extracted data, state and evidence.

Accepted inputs:

- A directory of the original `*_data_part*.parquet` files. **Preferred.**
- A prepared directory containing `catalog.parquet` and `conflicting-reports.parquet`. Both are read; unrelated provenance files are not classified.
- One Parquet or JSONL file containing `url`, `title`, `body`, and optional `project`/source ID. The original aliases `issue_title` and `issue_body` also work. A GitHub project can be derived from its URL when absent.

For example, a JSONL input row is:

```json
{"url":"https://github.com/example/project/issues/1","project":"example/project","title":"Crash while opening a file","body":"Full original report text here."}
```

The example is a schema illustration, not a report to classify. Do not send it as a paid smoke test.

Null title/body become empty text. Otherwise prose and whitespace are preserved. Exact normalized duplicates are classified once; **different text versions at the same URL are kept separately**. Deterministic content IDs map back to original URLs/source IDs; when identical text has multiple source IDs, `records.csv` retains each ID. No dataset bucket is treated as a vagueness label. `--limit N` counts the first N distinct texts, including cached ones; it is a workload limit, **not a random sample**.

Do not mix a changed dataset or edited classifier into an existing output directory. The runner checks input-file identity and code/prompt fingerprints; use a new directory for an intentional new configuration. The Codex migration changes the code/transport fingerprint, so existing Pi run directories cannot be reused or overwritten; keep them as historical outputs.

## Links and pictures

The collector saves a current public snapshot once. It prioritizes screenshots, Markdown links and reproducer/example links instead of downloading incidental package-registry URLs from logs. It records every discovered URL, including excluded, failed and limited ones.

- No live issue refresh, later discussions/fixes, arbitrary web search, authentication, installation, or downloaded-code execution.
- Direct screenshots, text/code files and bounded reproducer archives are supported. Reproducer archives require Git 2.40+; PDFs use `pdftotext` if installed.
- Bounds: 20 resources/report, 10 MiB/resource, 20-second HTTP budget, and bounded ZIP expansion. Only public addresses/default HTTP(S) ports are allowed; redirects are checked too.
- Text views have a 40,000-character/report budget. Longer material has **explicit excerpts**, with complete saved text parts available as optional reads. Unsupported binary files remain unread, not silently interpreted. Images embedded only inside a source archive are not rendered automatically.
- Current sources are not claimed to be historical versions. Missing optional evidence does not lower a grade. If necessary information still cannot be assessed, keep **pending**, not “vague.”

The Codex adapter disables native environments, shell, web search, plugins, skills,
memories and multi-agent features for classification, and disables configured MCP
servers on each thread. A client-side `read_report_file` tool serves only exact
allowlisted packet/evidence paths, returns full text or image content, and tracks
successful mandatory reads. Unexpected tools, model rerouting, reported retries,
compaction, missing reads and malformed output fail the attempt. Tool output limits
are raised above the existing batch budget to avoid silent clipping.

`check` verifies the Codex login, catalog capabilities and resolved thread settings
without `turn/start`. This does not prove a paid inference request will succeed or
independently attest the backend's response model. Codex may perform internal
transport retries that its event stream does not expose; the adapter does not
retry attempts and stops on reported recovery. Account/config RPC responses are
excluded from saved raw events; report attempts and evidence remain saved.
Failed setup diagnostics are retained at the temporary path printed in the error.
Codex needs permission to initialize its normal local runtime state.

The file allowlist is a client-side boundary, not a complete OS sandbox. Run
untrusted datasets in an appropriately isolated environment.

## Outputs

Everything is written under the chosen output directory. Prefer `runs/` so the supplied source-only `.gitignore` protects it; arbitrary output directories elsewhere are not automatically Git-ignored:

| File | Purpose |
| --- | --- |
| `labels.jsonl` | Final `record_id`, report `category`, and `vagueness`. Non-bugs have null vagueness. |
| `records.csv` | Content ID → original source ID and URL. |
| `summary.json` | Completed and failed/unfinished counts. |
| `errors.jsonl` | Technical failures/unfinished work; **not** invented classifications. |
| `state.sqlite` | Resume cache, original normalized text and numeric checks. |
| `attempts/` | Every model request, verified model state, raw events, warnings and responses. |
| `evidence/` | Cached linked material and manifests. |

Before calling a job complete, check that `failed_or_unfinished` is zero and the distinct-input count matches the requested scope. `pending` is a valid completed evidence status; a technical error is not. A clear report is not a confirmed bug or a promise that reproduction will succeed.

Only this handoff directory is intended for Git. Do not commit downloaded reports, outputs, caches, credentials or old experiments.
