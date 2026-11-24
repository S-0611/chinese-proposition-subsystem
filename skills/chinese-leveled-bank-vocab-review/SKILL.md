---
name: chinese-leveled-bank-vocab-review
description: Raise a Chinese levelled question bank to 100% strict vocabulary coverage (no substring/parasitic hits), then run the manual-review pass over grammar annotation, word-list provenance, pinyin tone-sandhi/neutral-tone/erhua conventions, and bank size, and finally re-import, publish, and verify through the backend API.
---

# Chinese Levelled Bank — Vocabulary Strict Coverage & Manual Review

Use this skill when a Chinese levelled bank already passes character/grammar gates but its
vocabulary coverage is low or only nominal (words hit only inside longer words), or when a
human-review pass (grammar annotation, word list, pinyin convention, bank size) must be
closed out before import and publication.

Follow [references/workflow.md](references/workflow.md) stage by stage. Stop after each stage
the user asked to review and report changed files, commands, counts, and remaining risks.

## Hard rules

- **Strict coverage only.** A word counts as covered only if at least one occurrence is not
  contained in a longer word-list word. `word in text` is a cross-check, never the verdict.
- **Never edit the word list to fit the bank**, never delete entries, never split a word
  across spaces to force a hit, and never declare coverage through a `vocab_words` field.
- **Only cumulative characters**: every new sentence uses `load_level(N)["chars"]["all"]`;
  a single out-of-table character invalidates the sentence.
- **Sentences**: 3–12 Han characters, Chinese punctuation, ending in 。？！; pinyin generated
  per character with one syllable per character and no space after punctuation.
- **Back up before mutating**: bank, level config, and `backend/bank.db` each get a
  timestamped copy; never overwrite an existing backup.
- **A passing `stats.py` is not the acceptance**: rerun the strict script and confirm
  `parasitic = 0`.

## Scripts (parameterised by level)

All scripts live in `scripts/` and take `--level N` (2–9) and optional `--repo PATH`.

| Script | Purpose |
| --- | --- |
| `strict_check.py` | Strict coverage, gap split (never appeared vs parasitised), host words, JSON output |
| `batch_check.py` | Validate a batch of candidate sentences and report strict-coverage delta |
| `review_audit.py` | Review modes: `pattern`, `concentration`, `unique`, `pinyin`, `redundant` |
| `pinyin_sandhi.py` | Convert a bank to context pinyin (一/不 sandhi, neutral tone, 儿化 → `r`) |

## Stage map

1. Baseline: conventional stats + strict check; classify the gap.
2. Word list: wire `vocabulary.list_path` / `vocab_coverage_min`; verify provenance.
3. Supplement: draft sentences in parallel chunks, verify each batch, merge, dedupe, loop.
4. Manual review: A grammar annotation, B concentration, C word list, D pinyin, E size.
5. Gates: validate / stats / strict / pinyin / duplicates / pattern.
6. Data: import, publish, API validate+stats+random+recommend.
7. Records: manual_review.json, checklist, execution record, commit and push.

Read `references/pitfalls.md` before touching `backend/import_bank.py`, the PDF, or long commit
messages — those three have caused the most wasted time.
