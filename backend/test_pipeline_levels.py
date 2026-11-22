# -*- coding: utf-8 -*-
"""命题流水线 2—9 级联调测试。

测试目的：验证前端新增的等级选择与后端接口契约，而不是验证正式题库内容。
测试使用临时 SQLite 库和每级两道占位题；占位题在 fixture 阶段直接置为
published，只为覆盖查询、校验、统计、random、recommend 的 HTTP 链路。
正式题库的质量门禁仍由 pipeline 和 publish 接口负责。

用法（项目根目录）：
    python backend/test_pipeline_levels.py
    python backend/test_pipeline_levels.py --base http://127.0.0.1:8020 --skip-server
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "http://127.0.0.1:8020"

PASS, FAIL = [], []


def request(base, method, path, body=None):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path, data=payload, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"detail": raw}
        return exc.code, data


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    if not condition:
        print(f"FAIL  {name} <- {detail}")
    else:
        print(f"PASS  {name}")


def write_fixture(path, level):
    items = []
    for idx, text in enumerate(("我爱学习。", "我喜欢汉语。"), start=1):
        chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        items.append({
            "id": f"L{level}-T-{idx:03d}",
            "level": level,
            "text": text,
            "tokens": [{"c": c, "py": "wǒ"} for c in chars],
            "grammar": [],
        })
    path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")


def run_command(args, cwd=ROOT, env=None):
    result = subprocess.run(args, cwd=str(cwd), env=env, capture_output=True)
    if result.returncode:
        output = (result.stdout + result.stderr).decode("utf-8", "replace")
        raise RuntimeError(f"命令失败：{' '.join(args)}\n{output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--skip-server", action="store_true")
    args = parser.parse_args()

    # Windows 沙箱中的系统临时目录可能对子进程不可见，测试文件放在仓库内的临时目录。
    temp_dir = Path(tempfile.mkdtemp(prefix=".pipeline_levels_", dir=str(ROOT)))
    test_db = temp_dir / "pipeline_levels.db"
    server = None

    if not args.skip_server:
        run_command([sys.executable, "backend/init_db.py", "--db", str(test_db)])
        run_command([
            sys.executable, "backend/import_bank.py", "--bank", "banks/level1/final.json",
            "--level", "1", "--db", str(test_db),
        ])
        for level in range(2, 10):
            bank = temp_dir / f"level{level}.json"
            write_fixture(bank, level)
            run_command([
                sys.executable, "backend/import_bank.py", "--bank", str(bank),
                "--level", str(level), "--db", str(test_db),
            ])

        # 仅为接口联调准备可抽取 fixture；正式发布必须走 publish 门禁。
        import sqlite3
        with sqlite3.connect(str(test_db)) as conn:
            conn.execute("UPDATE questions SET status='published' WHERE level BETWEEN 2 AND 9")
            conn.commit()

        env = dict(os.environ, BANK_DB=str(test_db))
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8020"],
            cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                request(args.base, "GET", "/")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("测试服务启动超时")

    try:
        code, data = request(args.base, "GET", "/api/levels")
        by_level = {int(item["level"]): item for item in (data or {}).get("items", [])}
        check("/api/levels 返回 1—9", code == 200 and set(by_level) == set(range(1, 10)), str(data))
        check("7—9 级均可用", all(by_level[n]["status"] == "available" for n in (7, 8, 9)), str(by_level))
        check("7—9 合并题数正确", sum(by_level[n]["question_count"] for n in (7, 8, 9)) == 6, str(by_level))

        for level in range(2, 10):
            code, data = request(args.base, "GET", f"/api/questions?level={level}")
            items = (data or {}).get("items", [])
            check(f"查询 {level} 级不串题", code == 200 and len(items) == 2 and all(i.get("level") == level for i in items), str(data))

            for mode in ("random", "recommend"):
                code, data = request(args.base, "GET", f"/api/questions/{mode}?level={level}&n=1")
                items = (data or {}).get("items", [])
                check(f"{mode} 抽取 {level} 级", code == 200 and len(items) == 1 and items[0].get("level") == level, str(data))

            for operation in ("validate", "stats"):
                code, data = request(args.base, "POST", f"/api/pipeline/{operation}?level={level}")
                check(f"{operation} 接口支持 {level} 级", code == 200 and data is not None, str(data))

        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        check("前端提供七—九级合并选项", 'value="7">七—九级（合并）' in html)
        check("前端将七—九级映射为三个后端等级", "7: [7, 8, 9]" in js)
        check("前端不再写死一级查询", "/api/questions?level=1" not in js and "/api/questions/recommend?level=1" not in js)
        check("前端接入校验和统计接口", "/api/pipeline/${kind}?level=${level}" in js)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        shutil.rmtree(temp_dir, ignore_errors=True)

    total = len(PASS) + len(FAIL)
    print(f"\n结果：通过 {len(PASS)}/{total}")
    if FAIL:
        print("失败项：")
        for item in FAIL:
            print(f"  - {item}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
