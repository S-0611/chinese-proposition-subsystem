# -*- coding: utf-8 -*-
"""后端统一测试（成员B 第五天任务交付物：题库导入、查询、发布和抽题的统一测试）。

用法（后端已启动时，推荐：显式指定命题端口）：
    python backend/test_api.py --base http://127.0.0.1:8001
    python backend/test_api.py                      # 未指定 --base 时自动拉起独立测试库（端口 8017）

覆盖：真实查询、按等级/编号查询、404 错误返回、校验/统计接入、状态管理、
      发布门槛、按等级抽题、按覆盖程度抽题（w = max(0, C - rec_count)）、
      短时间防重复、录音计数与候选排除。
结果写入 reports/level1/：
    api_test_<日期>_<端口>.txt、api_responses_<日期>_<端口>.json、
    api_validate_<日期>_<端口>.json、api_stats_<日期>_<端口>.json
"""
import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PASS, FAIL = [], []
RESPONSES = {}


def req(method, path, body=None, base="http://127.0.0.1:8001"):
    url = base + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw}


def check(name, cond, info=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  <- {info}" if info and not cond else ""))


def hanzi_count(text):
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None,
                    help="已启动服务的基址（如 http://127.0.0.1:8001）；缺省自动拉起独立测试服务")
    ap.add_argument("--skip-server", action="store_true")
    args = ap.parse_args()

    srv = None
    test_db = None
    if args.base:
        base = args.base.rstrip("/")
        print(f"[test] 直接测试已启动服务：{base}（指定 --base 时不再拉起本地测试服务）")
    else:
        # 后端未启动时：用独立测试库拉起 uvicorn 子进程（不影响正式 bank.db）
        import os
        import subprocess
        import time
        test_db = ROOT / "backend" / "test_bank.db"
        if test_db.exists():
            test_db.unlink()
        env = dict(os.environ, BANK_DB=str(test_db))
        subprocess.run([sys.executable, "backend/init_db.py", "--db", str(test_db)],
                       cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, "backend/import_bank.py", "--db", str(test_db)],
                       cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL)
        srv = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", "8017"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "http://127.0.0.1:8017"
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("后端未能启动")
            srv.kill()
            sys.exit(1)
        print(f"[test] 已用独立测试库启动后端：{base}（test_bank.db）")

    print("=== 1. 服务与真实查询 ===")
    st, info = req("GET", "/", base=base)
    check("服务信息返回", st == 200 and info.get("service"), f"{st} {info}")
    check("数据库题量 = 导入的 256", info.get("questions_total") == 256, f"{info}")

    st, lst = req("GET", "/api/questions", base=base)
    RESPONSES["list_all"] = lst
    check("GET /api/questions 返回 200", st == 200, f"{st}")
    check("返回数量与导入文件一致(256)", lst.get("total") == 256, f"{lst.get('total')}")

    st, lst1 = req("GET", "/api/questions?level=1", base=base)
    RESPONSES["list_level1"] = lst1
    check("GET /api/questions?level=1 返回 256", st == 200 and lst1.get("total") == 256,
          f"{st} {lst1.get('total') if isinstance(lst1, dict) else lst1}")

    st, empty = req("GET", "/api/questions?level=2", base=base)
    check("查询未建库等级 → 标准空题库响应", st == 200 and empty.get("total") == 0
          and empty.get("items") == [] and empty.get("detail") == "该等级题库尚未完成", f"{st} {empty}")
    st, empty = req("GET", "/api/questions?level=99", base=base)
    check("查询越界等级 → 422", st == 422, f"{st}")

    st, q1 = req("GET", "/api/questions/L1-001", base=base)
    RESPONSES["get_one"] = q1
    need = {"id", "question_id", "question_version", "content_revision",
            "level", "text", "display_text", "tokens", "grammar", "status",
            "rec_count", "last_selected_at"}
    check("GET /api/questions/L1-001 返回 200", st == 200, f"{st}")
    check("返回包含全部统一字段", st == 200 and need <= set(q1.keys()), f"{set(q1.keys())}")
    check("tokens 与汉字逐字对应", st == 200 and len(q1["tokens"]) == hanzi_count(q1["text"]),
          f"{len(q1.get('tokens',[]))} vs {hanzi_count(q1.get('text',''))}")
    check("统一题目字段存在", st == 200 and q1.get("question_id") == q1.get("id")
          and q1.get("question_version") and q1.get("content_revision"), f"{q1}")
    check("tokens 含规范化拼音和原始展示拼音", st == 200 and all(
        {"c", "py", "display_py", "display_start"} <= set(t) for t in q1.get("tokens", [])), f"{q1.get('tokens')}")
    check("初始 rec_count=0 / last_selected_at=null",
          q1.get("rec_count") == 0 and q1.get("last_selected_at") is None, f"{q1.get('rec_count')}")

    st, miss = req("GET", "/api/questions/NOPE-999", base=base)
    RESPONSES["get_404"] = miss
    check("查询不存在的题目 → 404", st == 404 and "detail" in miss, f"{st} {miss}")

    print("=== 2. 校验与统计接入 ===")
    st, v = req("POST", "/api/pipeline/validate?level=1", base=base)
    RESPONSES["validate"] = v
    check("POST /api/pipeline/validate → 200", st == 200, f"{st}")
    check("校验结果：256 题全部合格", v.get("valid") == 256 and v.get("invalid") == 0,
          f"{v.get('valid')}/{v.get('invalid')}")
    check("校验结论 pass", v.get("verdict") == "pass", f"{v.get('verdict')}")

    st, s = req("POST", "/api/pipeline/stats?level=1", base=base)
    RESPONSES["stats"] = s
    check("POST /api/pipeline/stats → 200", st == 200, f"{st}")
    check("统计结论 pass 且字覆盖 100%", s.get("verdict") == "pass"
          and s.get("char", {}).get("coverage") == 100.0, f"{s.get('verdict')} {s.get('char')}")

    print("=== 3. 状态管理与发布门槛 ===")
    st, bad = req("POST", "/api/questions/L1-001/status", {"status": "published"}, base=base)
    check("非法状态流转（ready→published 直改）→ 400", st == 400, f"{st} {bad}")

    st, pub = req("POST", "/api/questions/L1-001/publish", base=base)
    RESPONSES["publish_one"] = pub
    check("单题发布（达标库）→ ok", st == 200 and pub.get("ok") is True, f"{st} {pub}")
    st, q1b = req("GET", "/api/questions/L1-001", base=base)
    check("发布后状态 = published", q1b.get("status") == "published", f"{q1b.get('status')}")

    st, puball = req("POST", "/api/pipeline/publish", {"level": 1}, base=base)
    RESPONSES["publish_all"] = puball
    check("整级发布 → 其余 255 题发布", st == 200 and puball.get("published_count") == 255,
          f"{st} {puball}")
    st, lstp = req("GET", "/api/questions?status=published", base=base)
    check("published 题共 256", lstp.get("total") == 256, f"{lstp.get('total')}")

    st, miss2 = req("POST", "/api/questions/NOPE-999/publish", base=base)
    check("发布不存在的题 → 404", st == 404, f"{st}")

    print("=== 4. 按等级抽题（random）===")
    st, rnd = req("GET", "/api/questions/random?level=1&n=5", base=base)
    RESPONSES["random"] = rnd
    check("GET /api/questions/random?level=1 → 200", st == 200, f"{st}")
    ids = [i["id"] for i in rnd.get("items", [])]
    check("返回 5 道 published 题", st == 200 and len(ids) == 5
          and all(i["status"] == "published" for i in rnd["items"]), f"{ids}")
    check("抽取后 last_selected_at 已更新", all(i["last_selected_at"] for i in rnd["items"]))

    st, rnd99 = req("GET", "/api/questions/random?level=2", base=base)
    check("对未建库等级抽题 → 404", st == 404, f"{st}")
    st, rnd99 = req("GET", "/api/questions/random?level=99", base=base)
    check("对越界等级抽题 → 422", st == 422, f"{st}")

    print("=== 5. 按覆盖程度抽题（recommend，w = max(0, C - rec_count)）===")
    st, rec1 = req("GET", "/api/questions/recommend?level=1&n=3&C=10", base=base)
    RESPONSES["recommend"] = rec1
    check("GET /api/questions/recommend → 200", st == 200, f"{st}")
    ids1 = [i["id"] for i in rec1.get("items", [])]
    check("返回 3 道题且权重均为 10（rec_count=0）",
          st == 200 and len(ids1) == 3
          and all(rec1["algorithm"]["weights_used"].get(i) == 10.0 for i in ids1),
          f"{ids1} {rec1.get('algorithm', {}).get('weights_used')}")
    check("返回算法说明含新权重公式",
          rec1.get("algorithm", {}).get("formula") == "w = max(0, C - rec_count)",
          f"{rec1.get('algorithm')}")

    st, rec2 = req("GET", "/api/questions/recommend?level=1&n=3&C=10", base=base)
    ids2 = [i["id"] for i in rec2.get("items", [])]
    check("短时间连续抽取不返回同一题", st == 200 and not (set(ids1) & set(ids2)),
          f"{ids1} vs {ids2}")

    st, rec3 = req("GET", "/api/questions/recommend?level=1&n=3&C=10", base=base)
    ids3 = [i["id"] for i in rec3.get("items", [])]
    check("第三次抽取仍不与前两次重复", st == 200 and not (set(ids1) & set(ids3))
          and not (set(ids2) & set(ids3)), f"{ids1} {ids2} {ids3}")

    print("=== 6. 录音计数与覆盖权重联动 ===")
    for _ in range(5):
        st, recd = req("POST", "/api/questions/L1-002/recorded", base=base)
    check("记录 5 次有效录音 → rec_count=5", recd["item"]["rec_count"] == 5,
          f"{recd['item']['rec_count']}")
    check("录音不影响题目状态", recd["item"]["status"] == "published")
    st, rec4 = req("GET", "/api/questions/recommend?level=1&n=10&C=10", base=base)
    ids4 = [i["id"] for i in rec4.get("items", [])]
    check("高录音题(L1-002)退出最低覆盖候选集", st == 200 and "L1-002" not in ids4, f"{ids4}")
    w = {i: rec4["algorithm"]["weights_used"].get(i) for i in ids4}
    check("返回题目权重 w = max(0, 10 - rec_count)", all(v == 10.0 for v in w.values()),
          f"{w}")

    st, rec5 = req("GET", "/api/questions/recommend?level=1&n=5&C=4", base=base)
    ids5 = [i["id"] for i in rec5.get("items", [])]
    check("C 可调：C=4 时 rec_count=5 的题权重为 0 被排除", st == 200 and "L1-002" not in ids5,
          f"{st} {ids5}")

    st, miss3 = req("POST", "/api/questions/NOPE-999/recorded", base=base)
    check("对不存在的题记录音 → 404", st == 404, f"{st}")

    print("=== 7. 录音幂等与覆盖快照契约 ===")
    st, before = req("GET", "/api/questions/L1-003", base=base)
    st, first = req("POST", "/api/questions/L1-003/recorded",
                    {"recording_id": "contract-recording-001", "speaker_id": "speaker-test"}, base=base)
    st2, second = req("POST", "/api/questions/L1-003/recorded",
                      {"recording_id": "contract-recording-001", "speaker_id": "speaker-test"}, base=base)
    check("同一 recording_id 重试不重复计数", st == 200 and st2 == 200
          and first["item"]["rec_count"] == before["rec_count"] + 1
          and second.get("duplicate") is True
          and second["item"]["rec_count"] == first["item"]["rec_count"], f"{first} {second}")
    snapshot = {"snapshot_version": "contract-v1", "generated_at": "2026-11-19T18:00:00+08:00",
                "items": [{"question_id": "L1-003", "recording_count": 1, "unique_speaker_count": 1}]}
    st, cov1 = req("PUT", "/api/v1/integration/coverage", snapshot, base=base)
    st2, cov2 = req("PUT", "/api/v1/integration/coverage", snapshot, base=base)
    check("覆盖快照首次写入成功", st == 200 and cov1.get("applied") is True, f"{st} {cov1}")
    check("同一覆盖版本重放不重复应用", st2 == 200 and cov2.get("applied") is False, f"{st2} {cov2}")

    print("=== 8. 参数错误处理 ===")
    st, e1 = req("GET", "/api/questions?status=hacked", base=base)
    check("非法 status 参数 → 400", st == 400, f"{st}")
    st, e2 = req("GET", "/api/questions/random?level=1&n=999", base=base)
    check("n 超上限 → 422", st == 422, f"{st}")

    print()
    print(f"=== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ===")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)

    out_dir = ROOT / "reports" / "level1"
    out_dir.mkdir(parents=True, exist_ok=True)
    from urllib.parse import urlparse
    port = urlparse(base).port or 8001
    suffix = f"{datetime.now().strftime('%Y%m%d')}_{port}"

    out = out_dir / f"api_test_{suffix}.txt"
    out.write_text(
        "\n".join([f"PASS {n}" for n in PASS]) + "\n\n返回样例：\n"
        + json.dumps(RESPONSES, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    files = [out]
    resp_file = out_dir / f"api_responses_{suffix}.json"
    resp_file.write_text(json.dumps(RESPONSES, ensure_ascii=False, indent=2), encoding="utf-8")
    files.append(resp_file)
    for key in ("validate", "stats"):
        if key in RESPONSES:
            p = out_dir / f"api_{key}_{suffix}.json"
            p.write_text(json.dumps(RESPONSES[key], ensure_ascii=False, indent=2), encoding="utf-8")
            files.append(p)

    print(f"测试记录已写入：" + "、".join(str(f.relative_to(ROOT)) for f in files))
    if srv is not None:
        srv.terminate()
        srv.wait(timeout=10)
        if test_db is not None:
            test_db.unlink(missing_ok=True)
        print("[test] 测试库已清理")


if __name__ == "__main__":
    main()

