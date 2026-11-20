# -*- coding: utf-8 -*-
"""pipeline 编排：一键跑完 校验 → 统计 → 生成调整计划；并支持合并多轮题库。

用法：
    一轮完整检查（题库默认取 banks/levelN/final.json，也可用 --bank 指定）：
        python scripts/pipeline.py --level 1 --bank banks/level1/final.json --tag v1
        python scripts/pipeline.py --level 2 --tag v1
    合并增量题（下一轮基础）：
        python scripts/pipeline.py --merge banks/level1/round1.json banks/level1/round2_add.json --out banks/level1/round2.json

退出码：0 达标；1 有不合格题；2 合格但覆盖未达标。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 保证任意 cwd 下可 import lib/stats/validate

import stats as stats_mod
import validate as validate_mod
from lib import ROOT, default_bank, load_bank, load_level, out_dir, validate_bank

sys.stdout.reconfigure(encoding="utf-8")


def cmd_check(args):
    level = load_level(args.level)
    bank = args.bank or str(default_bank(args.level))
    items = load_bank(bank)
    _, results, dup_ids, dup_texts = validate_bank(items, level)
    bad = [r for r in results if not r["ok"]]

    d = out_dir(args.level)
    (d / f"validate_{args.tag}.md").write_text(
        validate_mod.render_report(level, results, dup_ids, dup_texts), encoding="utf-8")

    print(f"=== {args.level} 级命题 pipeline（标签 {args.tag}）===")
    print(f"第 1 步 校验：{len(items)} 题中不合格 {len(bad)} 题，重复 id {len(dup_ids)} 个")
    if bad:
        for r in bad[:10]:
            print(f"  - {r['item'].get('id','?')} {r['item'].get('text','')}")
            for e in r["errors"]:
                print(f"    {e}")
        print(f"处理：修改或剔除不合格题后重跑（见 reports/level{args.level}/validate_{args.tag}.md）")
        sys.exit(1)

    stats, plan = stats_mod.compute(level, items)
    stats["tag"] = args.tag
    plan["tag"] = args.tag
    d = out_dir(args.level)
    (d / f"stats_{args.tag}.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"adjust_plan_{args.tag}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"stats_{args.tag}.md").write_text(stats_mod.render_md(level, stats, args.tag), encoding="utf-8")

    c, g = stats["char"], stats["grammar"]
    print(f"第 2 步 统计：字覆盖 {c['covered']}/{c['total']}（{c['coverage']}%），语法覆盖 {g['covered']}/{g['total']}（{g['coverage']}%）")
    if stats["verdict"] == "pass":
        print(f"结论：达标。报告见 reports/level{args.level}/stats_{args.tag}.md")
        sys.exit(0)
    print("结论：未达标")
    for f in stats["failed_checks"]:
        print("  - " + f)
    print(f"第 3 步 调整：按 reports/level{args.level}/adjust_plan_{args.tag}.json 补题（建议 {plan['suggested_new_items']} 题），")
    print("       合并后作为新一轮题库重跑：python scripts/pipeline.py --merge ... --out ... 然后再 check")
    sys.exit(2)


def cmd_merge(args):
    seen_ids, seen_texts, merged = set(), set(), []
    for p in args.inputs:
        for it in load_bank(p):
            if it.get("id") in seen_ids or it.get("text") in seen_texts:
                continue
            seen_ids.add(it.get("id"))
            seen_texts.add(it.get("text"))
            merged.append(it)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"items": merged}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"合并 {len(args.inputs)} 个题库，去重后 {len(merged)} 题，已写出 {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1, help="等级 1—9（数据取自 data/levels/levelN.json）")
    ap.add_argument("--bank", help="题库路径；缺省取 banks/levelN/final.json")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--out")
    ap.add_argument("inputs", nargs="*")
    args = ap.parse_args()

    if args.out:
        cmd_merge(args)
    else:
        cmd_check(args)


if __name__ == "__main__":
    main()
