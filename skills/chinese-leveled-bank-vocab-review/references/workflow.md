# Workflow: strict vocabulary coverage + manual review

All commands run from the repository root (the directory holding `scripts/`, `banks/`, `data/`,
`backend/`). `N` is the level number. Scripts resolve the repo themselves, or accept `--repo`.

## Stage 0 — Baseline (do not skip)

```powershell
python scripts/stats.py --level N --bank banks/levelN/final.json --tag vocab_precheck
python "<skill>/scripts/strict_check.py" --level N
```

Record three numbers: conventional coverage, strict coverage, and the gap split
(never appeared / parasitised). If `load_vocabulary()` returns `None`, the level has no word
list yet — go to Stage 1.

Typical starting point (level 3, 2026-11-24): conventional 388/966, strict 338/966,
gap = 577 never appeared + 50 parasitised.

## Stage 1 — Word list

1. Look for the official list under `data/vocabulary/`. If only a CSV transcription exists
   (`hsk3_0_vocabulary.csv` with `级别` column), build `levelN.json` from it with the same
   normalisation as the other levels: strip parenthetical supplements, take the first form
   before `∣`, drop `∥`, drop spaces and ordinal digits.
2. Normalise placeholders such as `…极了` → `极了`; an ellipsis can never be hit literally.
3. Write the file with `source`, `standard`, `level_range`, `level_label`, `entries`,
   `unique_headwords`, `duplicate_entries`, `items` — copy the structure of an existing level.
4. Wire the gate in `data/levels/levelN.json`:

```json
"vocabulary": {"new_count": 973, "total_count": 973, "unique_headwords": 966,
               "list_path": "data/vocabulary/level3.json",
               "source": "HSK 3.0 vocabulary transcription",
               "note": "..."},
"thresholds": {"vocab_coverage_min": 1.0, ...}
```

5. **Provenance check.** If the standard PDF is needed: it is usually a scanned image
   (`pypdf` returns 0 characters). Render pages with `pymupdf`, read them as images, and
   compare a head / middle / tail sample by entry number against the list. Level 3 matched
   153/153, which was accepted as "same source" without transcribing all 973 entries.

Raise `constraints.bank_target_items` before adding sentences, otherwise `stats.py` fails on
size alone.

## Stage 2 — Classify the gap

`strict_check.py --level N` prints:

- `never appeared` — write new sentences containing the word;
- `parasitised` — the word only occurs inside a longer word (`only` inside `only if`); the
  new sentence must contain the word **and** must not contain the host word next to it.

Single-character words are the hard class: each needs a sentence where the character stands
alone (`一只鸟飞走了。` for `只`), because almost any host word (`只有`, `一只` is fine but
`只要` is not) re-parasitises it.

For each item that will be rewritten, list the words only it covers:

```powershell
python "<skill>/scripts/review_audit.py" --level N --mode unique --ids L3-555,L3-628
```

Rewrites must keep those words, or coverage silently drops.

## Stage 3 — Supplement

1. Split the gap into chunks of ~100 words; draft in parallel, one agent per chunk.
2. Each sentence: cumulative characters only, 3–12 Han characters, one grammar id it really
   demonstrates, 2–4 target words, no duplicate and no Jaccard ≥ 0.85 neighbour.
3. Verify every batch before merging:

```powershell
python "<skill>/scripts/batch_check.py" --level N --cand draft1.json
```

4. Merge, dedupe across batches, write once with a backup:

```powershell
python scripts/validate.py --level N --bank banks/levelN/final.json --tag vocabstrict
python scripts/stats.py     --level N --bank banks/levelN/final.json --tag vocabstrict
python "<skill>/scripts/strict_check.py" --level N
```

5. If strict coverage is still short, hand-write the last few words (typically bound
   morphemes such as `费`, `赶`, `证`) and repeat. Level 3 needed 436 merged sentences plus
   8 hand-written ones.

## Stage 4 — Manual review (A–E)

### A. Grammar annotation

```powershell
python "<skill>/scripts/review_audit.py" --level N --mode pattern
```

Lists items whose verifiable grammar point does not match the text. For each, either:

- **minimal rewrite** so the sentence contains a pattern word (`更忙` → `更加忙`), or
- **re-annotate** to the structure the sentence really shows (main-predicate sentence,
  是……的, 把, 连动, 都……了).

Then re-check that no grammar point falls below `grammar_freq_min`; if one would, keep an item
on it deliberately.

### B. Concentration

```powershell
python "<skill>/scripts/review_audit.py" --level N --mode concentration --gid G3-45
```

A high count is acceptable when every item really does contain the structure (level 3: 132
items of `X 的 Y`, all containing `的`). Only rewrite if items lack the structure.

### C. Word list provenance — see Stage 1.5; record the sampling result and the owner decision.

### D. Pinyin convention

Two options, decide with the owner:

- **citation tone** (一 yī, 不 bù, 个 gè);
- **context reading** (一 sandhi, neutral tone, 儿化 `r`).

Convert with:

```powershell
python "<skill>/scripts/pinyin_sandhi.py" --level N           # dry run, prints diff
python "<skill>/scripts/pinyin_sandhi.py" --level N --apply   # writes bank, backs up
```

Then re-import; `backend/import_bank.py` must accept the `r` syllable (see pitfalls).

### E. Size

`review_audit.py --mode redundant` reports how many items could be deleted without losing
strict coverage. Those items usually carry grammar drills, so do not delete blindly; decide
with the owner and, if trimming, keep every grammar point at its minimum.

## Stage 5 — Gates (all must pass)

```powershell
python scripts/validate.py --level N --bank banks/levelN/final.json --tag strict
python scripts/stats.py     --level N --bank banks/levelN/final.json --tag strict
python "<skill>/scripts/strict_check.py" --level N
```

| Check | Target |
| --- | --- |
| strict vocabulary | 100%, parasitic 0 |
| conventional vocabulary | 100% (cross-check) |
| character coverage | cumulative table 100% |
| grammar | every point ≥ `grammar_freq_min` |
| validation | 0 invalid, 0 warnings, 0 duplicate id/text |
| pinyin | syllables = Han characters for every item |
| size | inside `bank_target_items` |
| pattern audit | 0 mismatches (after stage 4A) |

## Stage 6 — Import, publish, verify

```powershell
python backend/import_bank.py --bank banks/levelN/final.json --level N --force
# POST /api/pipeline/publish {"level": N}
```

If the backend has been running since before the stats code changed, restart it — an old
process has no `vocabulary` field in `/api/pipeline/stats` and you will chase a phantom bug.

Verify: `validate` total/valid, `stats` char+vocab+grammar, `random` (level, published,
tokens aligned), `recommend` (formula `w = max(0, C - rec_count)`, candidate size, window).
Check `tokens` in the database against the bank pinyin; a mismatch means the importer fell
back to pypinyin.

## Stage 7 — Records

- `reports/levelN/manual_review.json`: one issue per finding with `severity`, `status`,
  `before`, `after`; unresolved P0 blocks publishing.
- `reports/levelN/人工复核清单_<date>.md`: checklist with A–E rows and a sign-off column.
- `reports/levelN/人工复核执行记录_<date>.md`: what was changed, per-item tables.
- `reports/levelN/词汇严格口径核查_<date>.md`: method, gap, new sentences, final table.
- Commit with a message stating the coverage (`词汇覆盖达 966/966`) and push.
