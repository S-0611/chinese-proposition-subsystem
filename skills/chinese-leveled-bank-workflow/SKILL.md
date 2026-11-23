---
name: chinese-leveled-bank-workflow
description: Assemble, repair, validate, statistically audit, import, publish, and test Chinese proficiency level question banks when official character tables, grammar notes, project banks, and a backend pipeline must stay consistent.
---

# Chinese Leveled Bank Workflow

Use this skill when a user asks to reconcile or complete a Chinese levelled question bank, fix character or grammar validation, prepare a backend import, or verify random and recommendation extraction. Do not treat a configuration file as a question bank, and do not treat a mock or empty source package as a formal bank.

Follow the staged workflow in [references/workflow.md](references/workflow.md). Keep each stage reviewable: after each user-requested stage, report changed files, commands, results, remaining risks, and stop until the user explicitly confirms the next stage.

Core invariants:

- Use the official level character tables and grammar notes supplied by the user as the source of truth. For level N, use the explicitly confirmed cumulative character table; for the level-two workflow this is official level-one 300 plus official level-two 300, totaling 600.
- Preserve original banks and configuration with a clearly named backup before any mutation. Never overwrite an existing backup silently.
- Distinguish hard validation failures from warnings. A script reporting `pass` because a threshold is 90% does not mean a complete bank; for a complete level-two deliverable require 600/600 character coverage, 81/81 grammar coverage, zero validation failures, zero duplicate IDs/texts, and zero unresolved character warnings.
- Grammar IDs must belong to the level and the annotation must be manually or structurally verified as actually present. If pattern rules are known to be descriptive rather than executable, use ID validation plus an explicit manual-review gate; do not silently claim semantic grammar verification.
- Do not invent official characters to make a bank pass. Rewrite or remove out-of-scope questions, and add targeted questions for official characters that are not covered.
- Import only after validation and statistics pass. New database rows start as `ready`; only the publish gate may move the level to `published`.
- Test random and recommendation endpoints only after publication, and verify returned level, status, tokens, grammar, and recommendation algorithm fields.

For a backend workflow, read the detailed command and endpoint sequence in the reference before mutating the database.
