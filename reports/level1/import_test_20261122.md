# 题库导入与分级访问测试记录（2026-11-22）

## 结论

- 已整理题库仅 `banks/level1/final.json`（256 题，L1-001—L1-256）。
- 已全量重导入 `backend/bank.db`：256 题全部 level=1，导入 0 跳过。
- pipeline：校验 256/256 合格，字覆盖 300/300、语法覆盖 42/42，结论达标。
- 发布：一级 256 题全部 published（抽题/推荐要求 published）。
- 分级访问：level=1 返回 256 题且 level 全为 1；level=2—9 返回标准空题库响应，不串题。
- 自动化测试：test_api 46/46、test_levels 33/33、test_level23 20/20，全部通过。

## 关键命令

```powershell
python backend/import_bank.py --level 1 --force
python scripts/pipeline.py --level 1 --tag import_20261122
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
python backend/test_api.py
python backend/test_levels.py
python backend/test_level23.py
```

## 接口抽查（正式库 8001）

| 检查 | 结果 |
| --- | --- |
| GET /api/levels | 1 级 available/256；2—9 级 pending |
| GET /api/questions?level=1 | 200，256 条，level 全为 1 |
| GET /api/questions?level=2..9 | 200，0 条，detail=该等级题库尚未完成 |
| GET /api/questions/random?level=1 | 200，均为 1 级 published |
| GET /api/questions/recommend?level=1 | 200，均为 1 级 |
| GET /api/questions/random?level=2 | 404 |
| POST /api/pipeline/validate?level=1 | pass，256/256 |
| POST /api/pipeline/stats?level=1 | pass |
| POST /api/pipeline/publish {level:2} | 404 |

## 说明

- `round1.json` / `round2.json` / `round2_add.json` / `round3_add.json` 是历史分轮文件，最终合并结果即 `final.json`，未单独导入，避免重复题。
- 导入前数据库备份：`reports/bank_before_import_20261122_092827.db`。
- 二级至九级题库尚未交付，当前只能验证“识别等级 + 标准空响应 + 不串题”。
