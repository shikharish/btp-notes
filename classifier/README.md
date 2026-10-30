# Luna classifier — handoff

**Give your coding agent this directory and the dataset. Nothing else from the investigation workspace is needed.**

Paste this instruction to the agent:

> Read `classifier/AGENTS.md` and `classifier/README.md`. Classify [INPUT PATH] into [OUTPUT DIRECTORY], using [N reports / the entire dataset]. Check setup, run the offline tests, run the classifier, and verify the output counts. Resume safely if interrupted. Do not change the models or rules. Tell me what completed, what failed, and where the outputs are.

Replace the bracketed values. If the input is not local, the original dataset link is below. Your agent can obtain and prepare it. Authentication may need one action from the collaborator; credentials are not included here.

## Fixed pipeline

1. **Report type:** `openai-codex/gpt-6-luna`, **high** thinking. Categories: `bug`, `no_bug`, `change_submission`, `unclear`.
2. **Only for `bug`:** collect relevant reporter-linked evidence, then use the same Luna model at **max** thinking for the vagueness checks.
3. Code maps those checks to **1 clear**, **2 partly specified**, **3 vague**, or **pending** when necessary evidence/target selection is unresolved.

Ten concurrent workers, up to ten reports per fresh model session. Large batches split before inference. Reports are never silently truncated. No reviewers, benchmark loop, Terra, Jev, or tuning step is needed.

The owner has finalized this configuration for now. It is an automatic judgment, not ground truth: the last independent-agent check matched 134/183 numeric cases (73.2%). This handoff is a simplified operational implementation, not a newly benchmarked classifier. Do not rerun the benchmark or change the configuration unless asked.

## Setup and commands

Requires **Linux/macOS (or WSL), Python 3.11+**, the [Pi CLI](https://github.com/earendil-works/pi), and access to the exact Luna model through the collaborator's own `openai-codex` login. The RPC client targets Pi 1.4.0's protocol.

Authenticate in Pi with `/login openai-codex` if needed. Never copy another person's `auth.json`, print tokens, or substitute an available model when Luna/max is missing.

From the directory containing `classifier/` (a Git checkout is not required):

```sh
# Offline tests: no model or web requests.
python -m unittest discover -s classifier -p 'test_*.py' -v

# Verify login and actual model/thinking selection; no classification request.
python classifier/classify.py check

# Classify the first 100 distinct report texts.
uv run --no-project --with duckdb==2.0.0 python classifier/classify.py run \
  classifier/data/reports --out classifier/runs/luna --limit 100

# Only when the owner requested the whole dataset:
uv run --no-project --with duckdb==2.0.0 python classifier/classify.py run \
  classifier/data/reports --out classifier/runs/luna --all
```

The Parquet examples use `uv` to supply DuckDB 2.0.0; an agent can install `uv` or use its own virtual environment with that dependency. For JSONL, plain `python` works; DuckDB is needed only for Parquet. `--workers 1` through `--workers 10` can reduce load. Code, models and prompts are fixed; there is no model-selection switch.

Use the **same command and output directory** to resume. Completed answers are reused. If a previous attempt failed, first inspect `attempts/`, then explicitly add `--retry-failed`. Earlier attempts remain saved. A failure stops scheduling new batches while already-running batches finish; this avoids flooding a quota-limited service. Never delete good answers to try for a better score.

## Dataset and input

Original archive, about **1.8 GB**:

https://drive.google.com/file/d/1YJ6POTgzfPPnli4nPHSgHKBH73NbEQaG/view

The agent may download it using a public-download tool such as `gdown`, inspect the ZIP before extraction, and extract it under `classifier/data/`. Do not execute anything from the archive. Expect **27 `*_data_part*.parquet` files**, with 5,966,490 raw rows in the original snapshot. If the download needs permission, ask the collaborator for access or a local copy—do not invent another dataset. Allow disk space for the archive, extracted data, state and evidence.

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

Do not mix a changed dataset or edited classifier into an existing output directory. The runner checks input-file identity and code/prompt fingerprints; use a new directory for an intentional new configuration.

## Links and pictures

The collector saves a current public snapshot once. It prioritizes screenshots, Markdown links and reproducer/example links instead of downloading incidental package-registry URLs from logs. It records every discovered URL, including excluded, failed and limited ones.

- No live issue refresh, later discussions/fixes, arbitrary web search, authentication, installation, or downloaded-code execution.
- Direct screenshots, text/code files and bounded reproducer archives are supported. Reproducer archives require Git 2.40+; PDFs use `pdftotext` if installed.
- Bounds: 20 resources/report, 10 MiB/resource, 20-second HTTP budget, and bounded ZIP expansion. Only public addresses/default HTTP(S) ports are allowed; redirects are checked too.
- Text views have a 40,000-character/report budget. Longer material has **explicit excerpts**, with complete saved text parts available as optional reads. Unsupported binary files remain unread, not silently interpreted. Images embedded only inside a source archive are not rendered automatically.
- Current sources are not claimed to be historical versions. Missing optional evidence does not lower a grade. If necessary information still cannot be assessed, keep **pending**, not “vague.”

The agents have read-only tools and audited file allowlists, **not an OS sandbox**. Run untrusted datasets in an appropriately isolated environment.

## Outputs

Everything is written under the chosen output directory. Prefer `classifier/runs/` so the supplied source-only `.gitignore` protects it; arbitrary output directories elsewhere are not automatically Git-ignored:

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
