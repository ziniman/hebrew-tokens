#!/usr/bin/env node
/**
 * Measures Hebrew vs English tokenization cost on OpenAI's tokenizers.
 * No API key and no network needed - gpt-tokenizer bundles the encodings offline.
 *
 * Usage:  npm install && npm run measure
 */
const fs = require('fs');
const path = require('path');

const ENCODINGS = {
  // friendly label -> gpt-tokenizer module
  'GPT-3.5 / GPT-4  (cl100k_base)': 'cl100k_base',
  'GPT-4o / GPT-5   (o200k_base)': 'o200k_base',
};

const corpus = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'corpus', 'pairs.json'), 'utf8')
);
const pairs = corpus.pairs;

const results = { generated_at: new Date().toISOString(), encodings: {} };

for (const [label, mod] of Object.entries(ENCODINGS)) {
  const enc = require(`gpt-tokenizer/encoding/${mod}`);
  let heTok = 0, enTok = 0, heChr = 0, enChr = 0;
  const rows = [];

  for (const p of pairs) {
    const h = enc.encode(p.he).length;
    const e = enc.encode(p.en).length;
    heTok += h; enTok += e; heChr += p.he.length; enChr += p.en.length;
    rows.push({
      id: p.id, genre: p.genre,
      he_tokens: h, en_tokens: e,
      he_chars: p.he.length, en_chars: p.en.length,
      ratio: +(h / e).toFixed(3),
    });
  }

  results.encodings[mod] = {
    label,
    totals: {
      he_tokens: heTok, en_tokens: enTok,
      he_chars: heChr, en_chars: enChr,
      token_ratio_he_over_en: +(heTok / enTok).toFixed(3),
      char_ratio_he_over_en: +(heChr / enChr).toFixed(3),
      he_tokens_per_char: +(heTok / heChr).toFixed(4),
      en_tokens_per_char: +(enTok / enChr).toFixed(4),
    },
    per_pair: rows,
    ratio_min: +Math.min(...rows.map(r => r.ratio)).toFixed(2),
    ratio_max: +Math.max(...rows.map(r => r.ratio)).toFixed(2),
  };
}

// ---- report ----
const enc = Object.values(results.encodings);
const [older, newer] = [enc[0], enc[1]];

console.log('\nHebrew vs English - same meaning, both languages\n');
console.log(`Corpus: ${pairs.length} meaning-equivalent pairs`);
console.log(`Characters: ${older.totals.he_chars} Hebrew vs ${older.totals.en_chars} English ` +
            `(Hebrew is ${Math.round((1 - older.totals.char_ratio_he_over_en) * 100)}% SHORTER on screen)\n`);

for (const e of enc) {
  console.log(`${e.label}`);
  console.log(`  Hebrew ${e.totals.he_tokens} tokens vs English ${e.totals.en_tokens} tokens`);
  console.log(`  Hebrew costs ${e.totals.token_ratio_he_over_en}x English  (per-pair range ${e.ratio_min} - ${e.ratio_max})\n`);
}

const improvement = older.totals.token_ratio_he_over_en / newer.totals.token_ratio_he_over_en;
console.log(`The Hebrew penalty fell ${improvement.toFixed(2)}x between the two tokenizer generations.`);
console.log(`  ${older.totals.token_ratio_he_over_en} / ${newer.totals.token_ratio_he_over_en} = ${improvement.toFixed(3)}\n`);
console.log('Note: these are OpenAI tokenizers. They do NOT predict Claude or Gemini.');
console.log('      For Claude, run  python3 src/measure_anthropic.py  with an API key.\n');

fs.mkdirSync(path.join(__dirname, '..', 'results'), { recursive: true });
fs.writeFileSync(
  path.join(__dirname, '..', 'results', 'openai.json'),
  JSON.stringify(results, null, 2) + '\n'
);
console.log('Wrote results/openai.json');
