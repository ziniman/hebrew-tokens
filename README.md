# How much more does Hebrew cost than English?

A small, reproducible measurement of what it costs to say **the same thing** in
Hebrew versus English, counted in LLM tokens.

Short answer, on OpenAI's tokenizers:

| Tokenizer generation | Models | Hebrew costs |
|---|---|---|
| Previous (`cl100k_base`) | GPT-3.5, GPT-4 | **3.57x** English |
| Current (`o200k_base`) | GPT-4o, GPT-4.1, GPT-5, o-series | **1.42x** English |

**The Hebrew penalty fell by 2.5x between the two generations** (3.574 / 1.42 = 2.52).

If you are still budgeting on "Hebrew costs three or four times more", that rule
of thumb is from the previous generation and it is now roughly 2.5x too
pessimistic.

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

And yet Hebrew still costs **more tokens**. On the previous generation it cost
3.57x more while being 30% shorter. That gap is entirely the tokenizer: common
English words are single tokens, while Hebrew words get split into 3-4 pieces.

```
o200k_base:
  "developers"   -> 1 token   (10 characters)
  "מפתחים"       -> 3 tokens  (6 characters)
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
| `cl100k_base` | 3.574x | 3.00x - 4.45x |
| `o200k_base` | 1.420x | 1.22x - 1.60x |

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
model-specific counts and is **free** - it does not run inference and is not
billed per token.

```sh
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 src/measure_anthropic.py
python3 src/measure_anthropic.py --models claude-opus-5 claude-sonnet-5
```

Each run is archived to `results/anthropic-<timestamp>.json` (git-ignored);
`results/anthropic.json` is refreshed as the canonical latest snapshot. Pass
`--out PATH` to write a single file to an explicit path instead. If a rate limit
or connection error interrupts a run, models that already finished are still
written - re-run to complete the rest.

> **The OpenAI numbers above are not Claude numbers.** Anthropic's own
> documentation warns that `tiktoken` and `gpt-tokenizer` undercount Claude by
> roughly 15-20% on ordinary text, and by considerably more on non-English input.
> Hebrew is precisely that case. Whether Claude's Hebrew ratio is better or worse
> than 1.42x is an open question until someone runs the script above.

**A note on method:** every `count_tokens` call includes a small fixed
per-message overhead. The script probes it with a known single-token message and
subtracts it, so the reported figures are the cost of the text itself. The
overhead is printed and stored in the results so you can check the correction.

---

## Limitations

- **10 pairs is a small corpus.** The direction and rough magnitude are stable
  across all ten and across both tokenizers, but the third decimal place is not
  meaningful. Treat 3.6x and 1.4x as the honest precision.
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
