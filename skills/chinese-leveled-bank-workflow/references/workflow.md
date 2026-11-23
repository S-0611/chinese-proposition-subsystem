# Chinese Leveled Question Bank Workflow

This workflow is designed for a repository with `data/levels/`, `banks/`, `scripts/`, `backend/`, and `reports/` directories. Adapt paths only when the user identifies a different repository. Preserve unrelated local changes and never reset a worktree to force a clean state.

## Stage 1 and stage 2 identify the source and formal bank

1. Locate the actual Git worktree and pull the requested branch with a fast-forward-only update. If uncommitted user changes would be overwritten, stop and ask how to preserve them.
2. Confirm the formal bank path, normally `banks/levelN/final.json`. Inspect the source package before copying anything. An empty manifest such as `items: []` is not a formal question bank. A file such as `banks/final2.json` may be a draft; copy it to the default path only when the user explicitly authorizes that temporary use.

Before mutation, create a backup beside the target with a unique descriptive suffix. Do not overwrite an existing backup without comparing it first.

## Stage 3 validate the bank

Run the repository validator against the formal path:

```powershell
python scripts/validate.py --level 2 --bank banks/level2/final.json --tag step3
```

Review the generated report, not just the exit code. Check:

- `invalid = 0`;
- duplicate IDs and duplicate texts are empty;
- every item has the expected ID, level, text, pinyin, and grammar fields;
- text length, digits, Latin letters, and character-table findings;
- grammar IDs belong to the requested level.

Warnings that represent out-of-scope characters remain data-quality issues. Do not call the bank complete while they remain unresolved, even if the repository currently treats them as non-blocking.

## Stage 4 statistics and targeted supplementation

Statistics must use the confirmed cumulative table. For level two, do not select only `chars.new`; use the merged 600-character table. If the code selects `new` before `all`, fix that rule before trusting the report.

```powershell
python scripts/stats.py --level 2 --bank banks/level2/final.json --tag cumulative600
```

Review:

- character coverage and uncovered characters;
- character frequency and core-character frequency;
- grammar coverage and grammar frequency;
- target bank size and the generated adjustment plan.

For a complete level-two bank, require 600/600 character coverage and 81/81 grammar coverage. A configured threshold of 90% can be useful as an intermediate gate, but it is not the final acceptance criterion.

For each uncovered official character, add natural, level-appropriate sentences using 2–4 missing characters where possible. Preflight every candidate against the official cumulative table and the sentence-length rule. Update pinyin whenever text changes. After supplementation, rerun validation and statistics.

If a character appears in a draft question but is absent from the confirmed official table, rewrite or remove that question. Never add the character to the official table just to silence a warning.

## Stage 5 import the database

Back up `backend/bank.db` before import:

```powershell
Copy-Item backend/bank.db backend/bank_before_levelN_<tag>.db
```

Import only after the bank passes the complete acceptance criteria:

```powershell
python backend/import_bank.py --bank banks/level2/final.json --level 2
```

Check the database status counts. New rows should be `ready`; importing does not publish them. Do not use `--reset` unless the user explicitly requests a destructive database rebuild. Use `--force` only when replacing existing rows is intentional and the backup exists.

## Stage 6 start the backend and run API gates

Start the service from the repository root, using a hidden process on Windows when starting it in the background:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Then run the level-specific API gates:

```powershell
curl.exe -X POST "http://127.0.0.1:8001/api/pipeline/validate?level=2"
curl.exe -X POST "http://127.0.0.1:8001/api/pipeline/stats?level=2"
```

Require `invalid: 0`, no duplicate IDs/texts, cumulative character coverage 100%, grammar coverage 100%, and no unresolved warnings before publication.

## Stage 7 publish

Publish only after the API validation and statistics gates pass:

```powershell
curl.exe -X POST "http://127.0.0.1:8001/api/pipeline/publish" `
  -H "Content-Type: application/json" `
  -d '{"level":2}'
```

The publish gate checks the level bank, statistics, and manual-review gate. Confirm the response reports the expected published count and verify the database has `published` rows for the level.

## Stage 8 test extraction

Only after publication test both modes:

```powershell
curl.exe "http://127.0.0.1:8001/api/questions/random?level=2&n=3"
curl.exe "http://127.0.0.1:8001/api/questions/recommend?level=2&n=3&C=10&candidate_size=20&recent_minutes=10"
```

Verify every returned item has the requested level, `published` status, complete `tokens`, and grammar IDs. For recommendation, verify the response includes `w = max(0, C - rec_count)`, candidate size, recent window, and weights. Extraction tests update `last_selected_at`; that side effect is expected.

## Stage reporting and stopping rules

At the end of each user-approved stage, report:

- files changed and backups created;
- exact command(s) run;
- counts and verdicts;
- remaining warnings or blockers;
- the next stage that is pending.

Stop and ask when an official source is missing, a formal bank is empty, a field schema is ambiguous, a local change would be overwritten, or a proposed rewrite changes the intended grammar or meaning in a way that cannot be inferred safely. Do not continue to import, publish, or extract while an earlier gate is unresolved.
