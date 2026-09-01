#!/usr/bin/env python3
"""
Measures Hebrew vs English tokenization cost on Claude models.

Anthropic publishes no downloadable tokenizer, so unlike the OpenAI script this
one must ask the API. It uses the free `count_tokens` endpoint, which returns
exact, model-specific token counts and does NOT run inference or cost anything
per token.

    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -r requirements.txt
    python3 src/measure_anthropic.py
    python3 src/measure_anthropic.py --models claude-opus-5 claude-sonnet-5

Why not tiktoken / gpt-tokenizer: those are OpenAI's tokenizers. Anthropic's own
docs warn they undercount Claude by roughly 15-20% on ordinary text, and by
considerably more on non-English input. Hebrew is exactly that case, so the
OpenAI numbers in results/openai.json must not be read as Claude numbers.

Scope: this measures INPUT tokens only. Output tokens are billed separately and
at a markedly higher rate (roughly 3-5x the input rate on current models), and
Hebrew output carries the same tokenization penalty measured here, so the effect
on a real bill compounds beyond the input ratio below.
"""
import argparse, json, os, pathlib, sys
from datetime import datetime, timezone

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency. Run:  pip install -r requirements.txt")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_MODELS = ["claude-opus-5"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                    help=f"Claude model IDs to measure (default: {' '.join(DEFAULT_MODELS)})")
    ap.add_argument("--out", default=None,
                    help="Write one file to this exact path instead of the default "
                         "timestamped archive + canonical results/anthropic.json")
    args = ap.parse_args()

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No credentials found. Set ANTHROPIC_API_KEY, or run `ant auth login`.\n"
                 "count_tokens is free - it does not run inference or bill per token.")

    corpus = json.loads((ROOT / "corpus" / "pairs.json").read_text(encoding="utf-8"))
    pairs = corpus["pairs"]
    client = anthropic.Anthropic(max_retries=8)

    def count(text: str, model: str) -> int:
        return client.messages.count_tokens(
            model=model, messages=[{"role": "user", "content": text}]
        ).input_tokens

    results = {"corpus_pairs": len(pairs), "models": {}}
    incomplete = False

    # RateLimitError / connection errors are transient and global: stop, keep
    # whatever models already finished, and let the user re-run to continue.
    # (The SDK already retries these with backoff up to max_retries first.)
    TRANSIENT = (anthropic.RateLimitError, anthropic.APIConnectionError)

    for model in args.models:
        try:
            # Every count_tokens call includes a small fixed per-message overhead.
            # Probe it with a known single-token message so we can subtract it and
            # report the token cost of the text itself.
            overhead = count("x", model) - 1
        except anthropic.NotFoundError:
            print(f"  ! {model}: unknown model id, skipping", file=sys.stderr); continue
        except anthropic.AuthenticationError:
            sys.exit("Authentication failed. Check ANTHROPIC_API_KEY.")
        except TRANSIENT as exc:
            print(f"  ! {model}: {type(exc).__name__}, stopping. Completed models are "
                  f"still written; wait and re-run to continue.", file=sys.stderr)
            incomplete = True
            break
        except anthropic.APIStatusError as e:
            print(f"  ! {model}: {e.status_code} {e.message}", file=sys.stderr); continue

        he_tot = en_tot = he_chr = en_chr = 0
        rows = []
        try:
            for p in pairs:
                h = count(p["he"], model) - overhead
                e = count(p["en"], model) - overhead
                he_tot += h; en_tot += e
                he_chr += len(p["he"]); en_chr += len(p["en"])
                rows.append({"id": p["id"], "genre": p["genre"],
                             "he_tokens": h, "en_tokens": e,
                             "he_chars": len(p["he"]), "en_chars": len(p["en"]),
                             "ratio": round(h / e, 3)})
        except TRANSIENT + (anthropic.APIStatusError,) as exc:
            print(f"  ! {model}: {type(exc).__name__} after {len(rows)}/{len(pairs)} pairs, "
                  f"stopping. Completed models are still written; re-run to continue.",
                  file=sys.stderr)
            incomplete = True
            break

        ratios = [r["ratio"] for r in rows]
        results["models"][model] = {
            "per_message_overhead_tokens": overhead,
            "totals": {"he_tokens": he_tot, "en_tokens": en_tot,
                       "he_chars": he_chr, "en_chars": en_chr,
                       "token_ratio_he_over_en": round(he_tot / en_tot, 3),
                       "char_ratio_he_over_en": round(he_chr / en_chr, 3)},
            "ratio_min": round(min(ratios), 2),
            "ratio_max": round(max(ratios), 2),
            "per_pair": rows,
        }

        print(f"\n{model}")
        print(f"  per-message overhead subtracted: {overhead} tokens")
        print(f"  Hebrew {he_tot} tokens vs English {en_tot} tokens")
        print(f"  Hebrew costs {he_tot / en_tot:.2f}x English "
              f"(per-pair range {min(ratios):.2f} - {max(ratios):.2f})")

    if not results["models"]:
        sys.exit("\nNo model produced a result.")

    def dump(obj) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(dump(results), encoding="utf-8")
        print(f"\nWrote {out}")
    else:
        # Archive each run to its own timestamped file so past runs are never
        # clobbered; refresh results/anthropic.json as the canonical latest
        # snapshot (no timestamp field, so it stays stable in git unless the
        # counts change).
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        results_dir = ROOT / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        archive = results_dir / f"anthropic-{stamp}.json"
        archive.write_text(dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                                 **results}), encoding="utf-8")
        (results_dir / "anthropic.json").write_text(dump(results), encoding="utf-8")
        print(f"\nWrote {archive.relative_to(ROOT)}")
        print("Updated results/anthropic.json (canonical latest)")

    print("Compare against results/openai.json to see how far the OpenAI proxy was off.")

    if incomplete:
        sys.exit("\nRun was incomplete - some models were skipped. Re-run to finish.")


if __name__ == "__main__":
    main()
