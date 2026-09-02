# How much more does Hebrew cost than English?

A small, reproducible measurement of what it costs to say **the same thing** in
Hebrew versus English, counted in LLM tokens.

Short answer - saying the same thing in Hebrew costs, in tokens:

| Tokenizer | Models | Hebrew costs |
|---|---|---|
| OpenAI `cl100k_base` | GPT-3.5, GPT-4 | **3.57x** English |
| OpenAI `o200k_base` | GPT-4o, GPT-4.1, GPT-5, o-series | **1.42x** English |
| Claude 4.5 / 4.6 generation | Sonnet 4.5, Sonnet 4.6, Haiku 4.5, Opus 4.5 | **2.54x** English |
| Claude 5 generation | Opus 5, Sonnet 5 | **1.77x** English |

Two things to take from this:

- **The old "Hebrew costs 3-4x" rule is out of date.** On OpenAI it fell to 1.4x
  with `o200k_base`; on current Claude it is 1.8x. If you are still budgeting
  3-4x, you are now roughly 2x too pessimistic.
- **Claude's newer tokenizer did not make Hebrew cheaper.** Between the 4.5 and 5
  generations the Hebrew count for this corpus barely moved (1,211 -> 1,217
  tokens); the ratio improved only because English got ~44% *more* expensive
  (477 -> 688). Contrast OpenAI's `o200k_base`, which cut the absolute Hebrew
  count by 60%. A Hebrew product pays the same absolute Hebrew token bill on
  Claude 5 as on Claude 4.5.
- **Sonnet 4.6 did not bring a new tokenizer.** Its counts are byte-identical to
  Sonnet 4.5, Haiku 4.5 and Opus 4.5 on every pair (1,211 Hebrew / 477 English).
  The tokenizer changed at 4.5 -> 5, not at 4.5 -> 4.6.

---

## What exactly was measured

This is the part that matters, and it is easy to get wrong.

**The unit is meaning, not characters and not words.**

Each of the 10 items in [`corpus/pairs.json`](corpus/pairs.json) is a *pair*: the
same message written twice, once in natural Hebrew and once in natural English.
They are deliberately **not**:

- word-for-word translations,
- matched on character count,
- matched on word count.

Each side is written the way that language is actually written for that genre. A
Hebrew support ticket is written the way an Israeli customer writes one; the
English side says the same thing the way an English speaker would.

That is the right unit because it is the real question a developer has. Nobody
asks "what do 1,000 characters cost". They ask: *I am shipping this product in
Hebrew instead of English. What happens to my bill?*

### Why this matters more than it sounds

Hebrew is a **denser** script. For the same meaning, this corpus is:

- **1,757 Hebrew characters** vs **2,515 English characters**
- Hebrew is **30% shorter on screen**

And yet Hebrew still costs **more tokens**. On GPT-4 (`cl100k_base`) it cost 3.57x
more while being 30% shorter. That gap is entirely the tokenizer: common English
words are single tokens, while Hebrew words get split into 3-4 pieces.

```
o200k_base:   "developers" -> 1 token    "מפתחים" -> 3 tokens
Claude 5:     "developers" -> 2 tokens   "מפתחים" -> 5 tokens
```

Measuring per character would hide this completely, and measuring per word would
flatter Hebrew for the wrong reason. Per unit of meaning is the only framing that
answers the billing question.

### The corpus

Ten pairs across ten genres, chosen so the result is not an artifact of one
register: product prose, a customer support message, an LLM system prompt,
editorial prose, Hebrew with embedded Latin technical terms, a legal/HR contract
clause, an e-commerce product description, news reporting, developer
documentation, and a clinical note.

The result holds in **every one of the ten pairs**, which is what makes it more
than a lucky sample:

| Tokenizer | Total ratio | Per-pair range |
|---|---|---|
| OpenAI `cl100k_base` | 3.574x | 3.00x - 4.45x |
| OpenAI `o200k_base` | 1.420x | 1.22x - 1.60x |
| Claude 4.5 / 4.6 generation | 2.539x | 2.21x - 2.95x |
| Claude 5 generation | 1.769x | 1.52x - 2.13x |

**Claude changed its tokenizer between the 4.5 and 5 generations, but not in
Hebrew's favour.** Sonnet 4.5, Sonnet 4.6, Haiku 4.5 and Opus 4.5 share one
tokenizer (byte-identical on this corpus); Opus 5 and Sonnet 5 share a different
one. Going from 4.5 to 5, the corpus's Hebrew count went 1,211 -> 1,217 tokens
(essentially unchanged) while English went 477 -> 688.
Word-level: `"developers"` is 1 token on Claude 4.5 and 2 on Claude 5, while
`"מפתחים"` is 5 on both. The 5 tokenizer compresses ordinary English prose *worse*
than 4.5 and leaves Hebrew where it was.

---

## Reproduce it

### OpenAI tokenizers - no API key, no network

```sh
npm ci
npm run measure
```

`gpt-tokenizer` is pinned to an exact version and bundles the encodings offline,
so this runs fully locally and is deterministic. Each run is archived to
`results/openai-<timestamp>.json` (git-ignored); `results/openai.json` is
refreshed as the canonical latest snapshot and carries no timestamp, so it only
changes in git when the counts do.

### Claude - needs an API key

Anthropic publishes **no downloadable tokenizer**, so Claude cannot be measured
offline. It has to be asked. The `count_tokens` endpoint returns exact,
model-specific counts and does **not** consume tokens or run inference - so this
script costs nothing to run. It does, however, go through the standard API, which
rejects every request (`count_tokens` included) when the account's credit balance
is zero. The account needs a small positive balance; the script will not draw it
down.

```sh
pip install -r requirements.txt          # needs anthropic >= 0.41.0
export ANTHROPIC_API_KEY=sk-ant-...       # from console.anthropic.com, on a credited account
python3 src/measure_anthropic.py                                       # default: claude-opus-5
python3 src/measure_anthropic.py --models claude-opus-5 claude-sonnet-4-6 claude-sonnet-4-5   # compare tokenizer generations
```

Each run is archived to `results/anthropic-<timestamp>.json` (git-ignored);
`results/anthropic.json` is refreshed as the canonical latest snapshot. Pass
`--out PATH` to write a single file to an explicit path instead. If a rate limit
or connection error interrupts a run, models that already finished are still
written - re-run to complete the rest.

> **`gpt-tokenizer` is a poor proxy for Claude, and worst for Hebrew.** Measured
> against Claude 5, `o200k_base` undercounts the English side of this corpus by
> ~33% (462 vs 688 tokens) and the Hebrew side by ~46% (656 vs 1,217). Anthropic's
> docs warn of a 15-20% undercount on ordinary text and more on non-English; here
> it is larger than that even on English. For Claude, use the `count_tokens`
> numbers, not the OpenAI ones.

**A note on method:** every `count_tokens` call includes a small fixed
per-message overhead. The script probes it with a known single-token message and
subtracts it, so the reported figures are the cost of the text itself. The
overhead is printed and stored in the results so you can check the correction.

---

## Limitations

- **10 pairs is a small corpus.** The direction and rough magnitude are stable
  across all ten pairs and all four tokenizers, but the third decimal place is
  not meaningful. Treat 3.6x / 1.4x (OpenAI) and 2.5x / 1.8x (Claude) as the
  honest precision.
- **Only two Claude tokenizer generations are in play.** Claude 3.x and 4.0/4.1
  now return 404 from `count_tokens`. Sonnet 4.5, Sonnet 4.6, Haiku 4.5 and Opus
  4.5 all share one tokenizer; Opus 5 and Sonnet 5 share the next. So the
  comparison is 4.5/4.6 vs 5.
- **Hebrew only.** Arabic, Russian and other non-Latin scripts used in Israeli
  products are not covered here, though the same script would measure them.
- **Tokenizers are not prices.** A cheaper-per-token model with a worse tokenizer
  can still cost more. Compare total cost, not ratios alone.
- **Input tokens only.** Output tokens are billed separately, typically at 3-5x
  the input rate, and Hebrew output carries the same tokenization penalty. A
  product that reads *and* writes Hebrew feels this on both sides of the bill.

Contributions of real-world pairs, or of results from other models, are welcome.

## License

Apache License 2.0
