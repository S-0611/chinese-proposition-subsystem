# -*- coding: utf-8 -*-
"""二、三级题库导入 + 接口防串题测试（任务：导入 → 测试：三级题库）。

用法（项目根目录）：
    python backend/test_level23.py
    python backend/test_level23.py --base http://127.0.0.1:8019 --skip-server

说明：
  - 本脚本用占位冒烟题（各 6 题）走真实导入链路（backend/import_bank.py），
    只验证导入与按等级查询/防串题，不代表二、三级正式题库内容。
  - 自动拉起独立测试库（系统临时目录）与独立端口 8019，不污染 backend/bank.db。
结果写入 reports/level2-3/api_level23_test_<日期>.txt。
"""
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
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

BASE = "http://127.0.0.1:8019"

SMOKE = {
    2: [
        ("L2-T-001", "我想点一个牛肉面。"),
        ("L2-T-002", "这个苹果多少钱一斤？"),
        ("L2-T-003", "明天上午我们有汉语课。"),
        ("L2-T-004", "他每天早上七点起床。"),
        ("L2-T-005", "请帮我买两张电影票。"),
        ("L2-T-006", "这家饭馆的菜很好吃。"),
    ],
    3: [
        ("L3-T-001", "他昨天坐火车去了北京。"),
        ("L3-T-002", "春节的时候我们一起包饺子。"),
        ("L3-T-003", "这学期的课程比以前难一些。"),
        ("L3-T-004", "她打算下个月回国看父母。"),
        ("L3-T-005", "我们约好周末去公园拍照。"),
        ("L3-T-006", "老师让我们用汉语写一篇短文。"),
    ],
}


def req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw}


def check(name, cond, info=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  <- {info}" if info and not cond else ""))


def write_bank(path, level):
    items = [{"id": i, "level": level, "text": t, "grammar": []} for i, t in SMOKE[level]]
    path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--skip-server", action="store_true")
    args = ap.parse_args()
    BASE = args.base

    srv = None
    tmpdir = Path(tempfile.mkdtemp(prefix="level23_"))
    test_db = tmpdir / "test_level23.db"

    def run(cmd):
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True)
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        if p.returncode != 0:
            raise RuntimeError(f"命令失败：{' '.join(cmd)}\n{out}")
        return out

    if not args.skip_server:
        run([sys.executable, "backend/init_db.py", "--db", str(test_db)])
        run([sys.executable, "backend/import_bank.py",
             "--bank", "banks/level1/final.json", "--level", "1", "--db", str(test_db)])
        for lv in (2, 3):
            bp = tmpdir / f"level{lv}.json"
            write_bank(bp, lv)
            run([sys.executable, "backend/import_bank.py",
                 "--bank", str(bp), "--level", str(lv), "--db", str(test_db)])
        # 测试捷径：正式 publish 接口要求统计达标 + 人工复核，二/三级配置尚未按
        # pipeline 模板整理，无法走 publish；这里直接把占位题置为 published，
        # 仅用于验证抽题接口的按等级过滤（不改变业务结论）。
        import sqlite3
        with sqlite3.connect(str(test_db)) as c:
            c.execute("UPDATE questions SET status='published' WHERE level IN (2,3)")
            c.commit()
        env = dict(os.environ, BANK_DB=str(test_db))
        srv = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", "8019"],
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
        print("== 二、三级题库导入 + 接口测试 ==")

        # 1. 二级
        code, data = req("GET", "/api/questions?level=2")
        RESPONSES["level2"] = data
        items2 = data.get("items", [])
        check("level=2 返回 200", code == 200, str(code))
        check("level=2 共 6 题（占位冒烟题）", data.get("total") == 6, str(data.get("total")))
        check("level=2 全部 level==2", bool(items2) and all(i.get("level") == 2 for i in items2),
              str([i.get("level") for i in items2]))
        check("level=2 不返回一级题目", all(not str(i.get("id", "")).startswith("L1-") for i in items2),
              str([i.get("id") for i in items2]))

        # 2. 三级
        code, data = req("GET", "/api/questions?level=3")
        RESPONSES["level3"] = data
        items3 = data.get("items", [])
        check("level=3 返回 200", code == 200, str(code))
        check("level=3 共 6 题（占位冒烟题）", data.get("total") == 6, str(data.get("total")))
        check("level=3 全部 level==3", bool(items3) and all(i.get("level") == 3 for i in items3),
              str([i.get("level") for i in items3]))
        check("level=3 不返回一级题目", all(not str(i.get("id", "")).startswith("L1-") for i in items3),
              str([i.get("id") for i in items3]))
        check("level=3 不混入二级题目", all(not str(i.get("id", "")).startswith("L2-") for i in items3),
              str([i.get("id") for i in items3]))

        # 3. 一级回归
        code, data = req("GET", "/api/questions?level=1")
        RESPONSES["level1"] = {"total": data.get("total")}
        check(f"level=1 仍为 {EXPECTED_LEVEL1_COUNT} 题",
              code == 200 and data.get("total") == EXPECTED_LEVEL1_COUNT,
              str(data.get("total")))
        check("level=1 不混入二、三级题目",
              all(i.get("level") == 1 for i in data.get("items", [])),
              str({i.get("level") for i in data.get("items", [])}))

        # 4. 全量查询只包含 1/2/3
        code, data = req("GET", "/api/questions")
        RESPONSES["all_total"] = data.get("total")
        levels = {i.get("level") for i in data.get("items", [])}
        expected_total = EXPECTED_LEVEL1_COUNT + sum(len(items) for items in SMOKE.values())
        check(f"不带 level 时总数为 {expected_total}",
              data.get("total") == expected_total, str(data.get("total")))
        check("不带 level 时只含 1/2/3 级", levels == {1, 2, 3}, str(sorted(levels)))

        # 5. /api/levels 总览
        code, data = req("GET", "/api/levels")
        RESPONSES["levels"] = data
        lm = {i["level"]: i for i in data.get("items", [])}
        check("/api/levels 二级 available 且 6 题",
              lm.get(2, {}).get("status") == "available" and lm.get(2, {}).get("question_count") == 6,
              str(lm.get(2)))
        check("/api/levels 三级 available 且 6 题",
              lm.get(3, {}).get("status") == "available" and lm.get(3, {}).get("question_count") == 6,
              str(lm.get(3)))
        check("/api/levels 四级仍 pending", lm.get(4, {}).get("status") == "pending", str(lm.get(4)))

        # 6. 抽题接口按等级返回
        for lv in (2, 3):
            code, data = req("GET", f"/api/questions/random?level={lv}&n=3")
            RESPONSES[f"random{lv}"] = data
            its = [data] if "id" in data else data.get("items", [])
            check(f"random level={lv} 返回 200", code == 200, str(code))
            check(f"random level={lv} 全部为 {lv} 级",
                  bool(its) and all(i.get("level") == lv for i in its),
                  str([i.get("level") for i in its]))

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

    out_dir = ROOT / "reports" / "level2-3"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"api_level23_test_{stamp}.txt"
    lines = [f"二、三级题库导入 + 接口测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"base={BASE}",
             "说明：二、三级使用各 6 道占位冒烟题走真实导入链路；一级使用当前正式题库文件。",
             f"通过 {len(PASS)}/{len(PASS)+len(FAIL)}", ""]
    lines += [f"PASS  {p}" for p in PASS]
    lines += [f"FAIL  {f}" for f in FAIL]
    lines += ["", "关键响应摘录：",
              json.dumps(RESPONSES.get("level2", {}), ensure_ascii=False, indent=2)[:1500],
              json.dumps(RESPONSES.get("level3", {}), ensure_ascii=False, indent=2)[:1500],
              json.dumps(RESPONSES.get("levels", {}), ensure_ascii=False, indent=2)]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n结果已写入 {out}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
