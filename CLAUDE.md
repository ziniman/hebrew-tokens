# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A small, reproducible measurement of how many more LLM tokens it costs to express
the **same meaning** in Hebrew versus English. It is a data/measurement project,
not an application — the deliverable is the numbers in `results/` and the argument
in `README.md`. Keep both in sync: the README quotes specific figures
(3.574x, 1.42x, the 2.5x improvement) that are computed by the scripts.

## Commands

```sh
# OpenAI tokenizers — offline, deterministic, no API key (gpt-tokenizer is pinned)
npm ci
npm run measure                       # -> results/openai-<ts>.json + refreshes results/openai.json

# Claude — needs credentials, hits the free count_tokens endpoint
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 src/measure_anthropic.py                                   # default: claude-opus-5
python3 src/measure_anthropic.py --models claude-opus-5 claude-sonnet-5
python3 src/measure_anthropic.py --out results/anthropic.json      # write one explicit file, no archive
```

Each run archives to `results/{openai,anthropic}-<timestamp>.json` (git-ignored);
the un-suffixed `results/*.json` are the tracked canonical snapshots and carry no
timestamp field, so they only change in git when the counts change.

There is no test suite, linter, or build. Verification is running a script and
checking that `results/*.json` and the README's quoted numbers still agree.

## Architecture

Two independent measurement scripts, one shared corpus, one results file each.
Both scripts implement the **same procedure** so their outputs are comparable —
if you change the methodology in one, change it in the other and regenerate both.

- **`corpus/pairs.json`** — the single source of truth. 10 objects, each with
  `id`, `genre`, `he`, `en`. The pairs are *meaning-equivalent*, deliberately
  NOT matched on character count, word count, or literal translation, and Hebrew
  is written without nikkud (as in real production text). This choice is the
  whole point of the experiment; preserve it if you add pairs. Adding a pair
  requires regenerating both results files.

- **`src/measure-openai.js`** — loads `gpt-tokenizer/encoding/{cl100k_base,o200k_base}`
  (bundled offline), encodes each side of each pair, sums tokens, computes
  per-pair and total He/En ratios. The two encodings represent the previous
  (GPT-3.5/4) and current (GPT-4o/5/o-series) OpenAI tokenizer generations.

- **`src/measure_anthropic.py`** — same procedure via `client.messages.count_tokens`.
  Key subtlety: every `count_tokens` call carries a fixed per-message overhead,
  so the script probes it once per model with `count("x") - 1` and subtracts it
  from every measurement. The overhead is recorded in the results as
  `per_message_overhead_tokens`. An unknown/unavailable model id is skipped; a
  rate-limit or connection error (after the SDK's own `max_retries=8` backoff)
  stops the run but still writes the models that finished, and exits non-zero.

- **`results/openai.json`** committed; **`results/anthropic.json`** is generated
  on demand (requires credentials) and may not be present. The timestamped
  `*-<ts>.json` archives are git-ignored.

## Important constraints

- OpenAI tokenizer counts do **not** predict Claude. Anthropic's docs warn that
  `tiktoken`/`gpt-tokenizer` undercount Claude by ~15–20% on ordinary text and
  more on non-English. Do not present OpenAI numbers as Claude numbers anywhere.
- Results JSON is written with `ensure_ascii=False` / UTF-8 — Hebrew must stay
  readable in the file. Don't let a tool re-encode it to `\uXXXX`.
- Treat the reported precision as "3.6x and 1.4x" — the corpus is only 10 pairs,
  so trailing decimals are not meaningful (the README says this explicitly).
