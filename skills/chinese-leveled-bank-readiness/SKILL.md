---
name: chinese-leveled-bank-readiness
description: Move a Chinese proficiency level question bank from "built" to "ready for human review": confirm national-standard consistency for characters, words, grammar points and syllables; raise syllable coverage; enforce a 20-item review-readiness gate; and produce the admission report with a reviewer ledger.
---

# Chinese Leveled Bank Readiness

Use this skill when a level bank already exists but has not been cleared for human review, or when a reviewer asks "is this level ready to be reviewed?" — i.e. when the goal is to hand reviewers a bank where every machine-checkable defect is already gone, and every machine-unverifiable risk is written down as an explicit list.

Do **not** use it to claim the bank is finished. Readiness means "machines are done"; correctness of meaning, naturalness of sentences and level appropriateness remain human work.

Follow the staged procedure in [references/workflow.md](references/workflow.md). Run one stage, report changed files, commands, results and remaining risks, then stop until the user confirms the next stage.

## Core invariants

- **The national standard is the only source of truth.** `GF 0025—2021` character tables, vocabulary lists, grammar outline (Appendix A) and syllable tables define the level. Project configs are not authority. When a scanned table cannot be read reliably, declare the gap and keep the number out of the acceptance claim — never invent entries.
- **Every coverage number must state its denominator.** "100%" is meaningless without saying whether it counts this level's new items or the cumulative table, and whether the table is official or derived. Record it in config, not only in a report.
- **Back up before any mutation.** `*.bak_<date>_<reason>` next to the original. Never overwrite a silently existing backup.
- **Anything a machine can verify must be zero before review.** Character out-of-list, sentence length, digits, punctuation, syllable/character alignment, tone sandhi, empty annotations, annotation/rule mismatch, duplicate ids or texts, cross-level duplicates.
- **Anything a machine cannot verify must be handed over as a list, not as a promise.** Produce a ledger with a decision column; do not mark it "checked".
- **Statistics passing is not evidence.** `stats.py` passes on one-way coverage, `grammar_validation = id_only`, and (before this workflow) did not even notice missing pinyin punctuation. Always add the reverse check.
- **Prefer rewriting existing items to adding new ones.** Adding items changes volume and difficulty distribution; obtain explicit approval, then recompute coverage and syllables after every addition.

## Pipeline

1. **Standard consistency** — characters compared element-by-element against the extracted table; vocabulary entry count against the standard's per-level new-word count; grammar points anchored to Appendix A identifiers.
2. **Syllable coverage** — enter the official syllable table, align bank readings to the standard vocabulary (including neutral tone), check 一/不 sandhi, close gaps that have vocabulary support, and record the residual as a stated acceptance clause.
3. **Admission gate** — 20 machine checks; all blocking ones must be zero.
4. **Admission report and ledger** — pass/fail table with measured values, the lists handed to reviewers, and what admission deliberately excludes.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/gate.py --level N` | 20-item review-readiness gate; writes `<out>/L{N}_准入检查.json` and `L{N}_复核台账.csv`; exit 0 only when nothing blocks |
| `scripts/check_vocab_oov.py N` | reverse vocabulary check (are the words used actually in the cumulative list) |
| `scripts/check_sandhi.py [--fix]` | 一/不 tone-sandhi check with 第一 / 差不多 exceptions |
| `scripts/syllable_coverage.py --level N` | build syllable table from vocabulary and measure bank coverage |

`BANK_ROOT` overrides the repository root; it defaults to the ancestor of this skill folder.

## Checklist before declaring readiness

- [ ] Character table compared element-by-element, result recorded in config
- [ ] Vocabulary entry count matches the standard's per-level new count, duplicates explained
- [ ] Grammar points carry Appendix A identifiers
- [ ] Syllable table entered from the official pages, coverage and residual listed
- [ ] Neutral-tone and sandhi readings aligned to the standard vocabulary
- [ ] `gate.py` exits 0, and the ledger is generated
- [ ] Coverage and syllable numbers re-measured **after** the last add/delete of items
- [ ] Single-character polyphones (脏 zāng/zàng, 假, 干, 数, 空, 发 …) listed for review — word-level alignment does not catch them
- [ ] Reviewer lists exist: out-of-vocabulary items, polyphone rows, syllable residual
- [ ] Report states what admission does **not** cover
