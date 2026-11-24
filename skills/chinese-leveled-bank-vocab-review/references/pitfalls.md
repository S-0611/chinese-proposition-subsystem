# Pitfalls (learned the hard way)

## PDF and word lists

- The standard PDF is a **scanned image**: `pypdf` extracts 0 characters on every page.
  Use `pymupdf` (`pip install --target <lib> pymupdf`) to render pages to PNG, then read the
  images. Page mapping: PDF page = 内页 + 6.
- Do not transcribe 900+ entries by hand when a transcription already exists. Sample
  head / middle / tail by entry number first; level 3 matched 153/153, which justified
  keeping the CSV.
- The same word legitimately appears in two levels' lists (`了`, `过去`, `毛`), because the
  senses differ. Cross-level overlap is not a transcription error.

## `backend/import_bank.py` segmentation

Three defects found and fixed; keep them if the file is ever rewritten:

1. the chunk regex excluded tone-marked vowels, so `tā` became `t` and 86 items silently fell
   back to pypinyin — include `āáǎà…` in the character class;
2. the finals list had no `in`, so `pǐn`, `yín` failed — add `"in"`;
3. erhua `r` was unknown — add `"r"` as a final, otherwise every 儿化 item falls back to
   `ér` and the token round-trip breaks.

After any import, compare DB tokens with the bank pinyin; 0 differences is the only
acceptable result.

## Pinyin

- `pypinyin` applies 一/不 sandhi only through its phrase dictionary (`一个` → `yí gè`, but
  `一天` stays `yī`). Apply the rules yourself: 一 + tone 4 → `yí`, 一 + tone 1/2/3 → `yì`,
  ordinal/末 → `yī`; 不 + tone 4 → `bú`.
- 儿化 must be `r`, never `ér`: `这儿 zhè r`, `一点儿 yì diǎn r`, `一会儿 yí huì r`. Keep one
  syllable per Han character so tokens stay aligned; the `r` token is acceptable.
- Neutral tones come from context: `这个 zhè ge`, `石头 shí tou`, `弟弟 dì di`, `意思 yì si`.
- Converting a bank to sandhi changes 200+ items; re-import and re-verify, and expect a
  cross-level inconsistency if other levels stay on citation tone.

## Annotation vs pattern

- `pattern` values were auto-generated from example words and are **not exhaustive**. A
  sentence can be semantically right and still miss the regex (`及时` vs 时间副词 list).
  Decide a policy: either extend the pattern, rewrite minimally, or re-annotate to the
  structure the sentence really shows. Record the decision.
- Re-annotating without care pushes one point's frequency up and another's to 1. Simulate the
  counts before applying; every point must stay ≥ `grammar_freq_min` (usually 2).

## Coverage regressions

- Rewriting a sentence to fix annotation deletes rare characters. After every rewrite batch,
  rerun `stats.py`; when coverage drops, add a small sentence back (`他及格了就走了。`,
  `他其实很胖，不喝啤酒。`).
- G3-45-style fallback annotations are tempting; they raise concentration and lower quality.
  Prefer a real structure (把/被/连动/兼语/复句) whenever the words allow it.

## Tooling

- PowerShell `Get-Content -Raw` without `-Encoding UTF8` decodes UTF-8 as ANSI and destroys
  Chinese text. Use Python or `-Encoding UTF8`; never round-trip JSON through PowerShell.
- Multi-line Chinese commit messages break `git commit -m`; write the message to a file and
  use `git commit -F msg.txt`.
- A long-running `uvicorn` started before a code change keeps the old module. Restart it
  before trusting `/api/pipeline/stats`.
- Backups: timestamp to the second, refuse to overwrite, and delete only byte-identical
  duplicates.
- `stats.py` checks `bank_target_items`; raise it before adding sentences or the run fails on
  size instead of coverage.
