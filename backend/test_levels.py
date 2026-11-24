# -*- coding: utf-8 -*-
"""九级接口统一测试（成员B 九级扩展交付物：等级 1—9 识别、空题库标准响应、防串题）。

用法（项目根目录）：
    python backend/test_levels.py
    python backend/test_levels.py --base http://127.0.0.1:8001 --skip-server

自动拉起独立测试库（backend/test_levels.db）与独立端口 8018，不污染正式 bank.db。
覆盖：
  1. level=1 正常查询（题量从当前题库文件读取，全部 level==1）
  2. level=2—9 均可被接口识别，返回标准空题库响应 {"total":0,"items":[],"detail":"该等级题库尚未完成"}
  3. 空题库等级绝不串题（items 为空，不返回一级题目）
  4. /api/levels 九级总览（一级 available，二至七级 pending，八至九级 merged 到七级）
  5. level 越界（0 / 10）返回 422
  6. 空题库等级的 random / recommend / validate / stats / publish 均给出明确 404
结果写入 reports/level1/api_levels_test_<日期>.txt。
"""
import argparse
import io
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(ROOT / "scripts"))
from lib import default_bank, load_bank  # noqa: E402

EXPECTED_LEVEL1_COUNT = len(load_bank(default_bank(1)))

PASS, FAIL = [], []
RESPONSES = {}

BASE = "http://127.0.0.1:8018"
EMPTY_DETAIL = "该等级题库尚未完成"


def req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
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


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--skip-server", action="store_true")
    args = ap.parse_args()
    BASE = args.base

    srv = None
    test_db = ROOT / "backend" / "test_levels.db"
    if not args.skip_server:
        import os
        if test_db.exists():
            test_db.unlink()
        env = dict(os.environ, BANK_DB=str(test_db))
        subprocess.run([sys.executable, "backend/init_db.py", "--db", str(test_db)],
                       cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, "backend/import_bank.py",
                        "--bank", "banks/level1/final.json", "--level", "1", "--db", str(test_db)],
                       cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL)
        srv = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", "8018"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                req("GET", "/")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("测试服务启动超时")

    try:
        print("== 九级接口统一测试 ==")

        # 1. level=1 正常查询
        code, data = req("GET", "/api/questions?level=1")
        RESPONSES["level1"] = data
        check("level=1 返回 200", code == 200, str(code))
        check(f"level=1 共 {EXPECTED_LEVEL1_COUNT} 题",
              data.get("total") == EXPECTED_LEVEL1_COUNT, str(data.get("total")))
        check("level=1 全部题目 level==1",
              data.get("total", 0) > 0 and all(i.get("level") == 1 for i in data.get("items", [])),
              f"total={data.get('total')}")

        # 2/3. level=2—9 标准空题库响应且不串题
        for lv in range(2, 10):
            code, data = req("GET", f"/api/questions?level={lv}")
            RESPONSES[f"level{lv}"] = data
            ok_shape = (code == 200 and data.get("total") == 0 and data.get("items") == []
                        and data.get("detail") == EMPTY_DETAIL)
            ok_no_leak = all(i.get("level") == lv for i in data.get("items", []))
            check(f"level={lv} 返回标准空题库响应", ok_shape,
                  f"{code} {data}")
            check(f"level={lv} 不串题（无一级题目）", ok_no_leak, str(data.get("items")))

        # 4. /api/levels 总览
        code, data = req("GET", "/api/levels")
        RESPONSES["levels"] = data
        check("/api/levels 返回 200", code == 200, str(code))
        levels = {i["level"]: i for i in data.get("items", [])}
        check("/api/levels 覆盖 1—9", set(levels.keys()) == set(range(1, 10)),
              str(sorted(levels.keys())))
        check(f"一级 status=available 且 {EXPECTED_LEVEL1_COUNT} 题",
              levels.get(1, {}).get("status") == "available"
              and levels.get(1, {}).get("question_count") == EXPECTED_LEVEL1_COUNT,
              str(levels.get(1)))
        check("二至七级 status=pending 且 detail 正确",
              all(levels.get(lv, {}).get("status") == "pending"
                  and levels.get(lv, {}).get("detail") == EMPTY_DETAIL
                  and levels.get(lv, {}).get("question_count") == 0
                  for lv in range(2, 8)),
              str({k: v for k, v in levels.items() if 2 <= k <= 7}))
        check("八、九级 status=merged 且指向七级",
              all(levels.get(lv, {}).get("status") == "merged"
                  and levels.get(lv, {}).get("merged_into") == 7
                  and levels.get(lv, {}).get("question_count") == 0
                  for lv in (8, 9)),
              str({k: v for k, v in levels.items() if k in (8, 9)}))

        # 5. level 越界
        for bad in (0, 10, 99):
            code, _ = req("GET", f"/api/questions?level={bad}")
            check(f"level={bad} 返回 422", code == 422, str(code))
        code, _ = req("GET", "/api/questions/random?level=10&n=1")
        check("random level=10 返回 422", code == 422, str(code))
        code, _ = req("POST", "/api/pipeline/publish", {"level": 10})
        check("publish level=10 返回 422", code == 422, str(code))

        # 6. 空题库等级的操作接口给出明确 404
        code, data = req("GET", "/api/questions/random?level=2&n=1")
        check("random level=2 返回 404", code == 404, str(code))
        code, data = req("GET", "/api/questions/recommend?level=2&n=1")
        check("recommend level=2 返回 404", code == 404, str(code))
        code, data = req("POST", "/api/pipeline/validate?level=2")
        check("validate level=2 返回 404 且说明题库尚未完成",
              code == 404 and "题库尚未完成" in str(data.get("detail", "")), str(data))
        code, data = req("POST", "/api/pipeline/stats?level=2")
        check("stats level=2 返回 404 且说明题库尚未完成",
              code == 404 and "题库尚未完成" in str(data.get("detail", "")), str(data))
        code, data = req("POST", "/api/pipeline/publish", {"level": 2})
        check("publish level=2 返回 404 且说明题库尚未完成",
              code == 404 and "题库尚未完成" in str(data.get("detail", "")), str(data))

    finally:
        if srv is not None:
            srv.terminate()
            try:
                srv.wait(timeout=10)
            except subprocess.TimeoutExpired:
                srv.kill()

    print(f"\n== 结果：通过 {len(PASS)} / {len(PASS) + len(FAIL)} ==")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)

    out = ROOT / "reports" / "level1" / f"api_levels_test_{datetime.now().strftime('%Y%m%d')}.txt"
    lines = [f"九级接口统一测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"base={BASE}", f"通过 {len(PASS)}/{len(PASS)+len(FAIL)}", ""]
    lines += [f"PASS  {p}" for p in PASS]
    lines += [f"FAIL  {f}" for f in FAIL]
    lines += ["", "关键响应摘录：", json.dumps(RESPONSES.get("level2", {}), ensure_ascii=False, indent=2),
              json.dumps(RESPONSES.get("levels", {}), ensure_ascii=False, indent=2)]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n结果已写入 {out}")

    if test_db.exists() and not args.skip_server:
        test_db.unlink()
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
