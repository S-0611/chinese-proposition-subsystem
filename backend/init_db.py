# -*- coding: utf-8 -*-
"""数据库初始化脚本（成员B 任务1/2 交付物）。

用法（项目根目录）：
    python backend/init_db.py
    python backend/init_db.py --db backend/bank.db --reset

--reset 会删除现有库文件后重建（仅表结构，不含题库数据；题库用 import_bank.py 导入）。
"""
import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import db

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DB_PATH))
    ap.add_argument("--reset", action="store_true", help="删除旧库文件后重建")
    args = ap.parse_args()

    if args.reset:
        p = __import__("pathlib").Path(args.db)
        if p.exists():
            p.unlink()
            print(f"已删除旧数据库：{p}")

    conn = db.connect(args.db)
    db.init_schema(conn)

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    n_questions = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    n_runs = conn.execute("SELECT COUNT(*) FROM run_records").fetchone()[0]

    print(f"[init_db] 数据库已建立：{args.db}")
    print(f"[init_db] 表：{', '.join(tables)}")
    print(f"[init_db] questions 表当前 {n_questions} 行；run_records 表当前 {n_runs} 行")
    print("[init_db] 提示：下一步运行 python backend/import_bank.py 导入题库")


if __name__ == "__main__":
    main()
