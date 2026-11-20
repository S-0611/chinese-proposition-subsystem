# -*- coding: utf-8 -*-
"""覆盖与频次统计：只统计校验合格的题，输出覆盖率、字频、语法频次和调整计划。

用法：
    python scripts/stats.py --level 1 --bank banks/level1/round1.json [--tag v1]
    题库缺省取 banks/levelN/final.json。

退出码：0 达标；2 未达标（按 reports/levelN/adjust_plan_<tag>.json 调整后重跑）。
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 保证任意 cwd 下可 import lib

from lib import (default_bank, load_bank, load_level, out_dir, validate_bank,
                 char_freq, detect_grammar_freq)

sys.stdout.reconfigure(encoding="utf-8")


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def compute(level, items):
    clean, results, dup_ids, dup_texts = validate_bank(items, level)
    th = level["thresholds"]

    cfreq = char_freq(clean)
    gfreq = detect_grammar_freq(clean, level)

    all_chars = level["chars"]["all"]
    core_chars = set(level["chars"]["core"])
    uncovered = [c for c in all_chars if cfreq.get(c, 0) == 0]
    core_low = {c: cfreq.get(c, 0) for c in sorted(core_chars) if cfreq.get(c, 0) < th["core_char_freq_min"]}

    grammar_total = len(level["grammar"])
    gname = {g["id"]: g["name"] for g in level["grammar"]}
    g_uncovered = [g["id"] for g in level["grammar"] if gfreq[g["id"]] == 0]
    g_low = {g["id"]: gfreq[g["id"]] for g in level["grammar"] if 0 < gfreq[g["id"]] < th["grammar_freq_min"]}

    failed = []
    cov = pct(len(all_chars) - len(uncovered), len(all_chars))
    if cov < th["char_coverage_min"] * 100:
        failed.append(f"字覆盖率 {cov}% 低于阈值 {th['char_coverage_min'] * 100}%")
    if uncovered and th["char_freq_min"] > 0:
        failed.append(f"有 {len(uncovered)} 个字出现 0 次")
    if core_low:
        failed.append(f"有 {len(core_low)} 个核心字出现少于 {th['core_char_freq_min']} 次")
    gcov = pct(grammar_total - len(g_uncovered), grammar_total)
    if gcov < th["grammar_coverage_min"] * 100:
        failed.append(f"语法覆盖率 {gcov}% 低于阈值 {th['grammar_coverage_min'] * 100}%")
    if g_uncovered:
        failed.append(f"有 {len(g_uncovered)} 个语法点使用 0 次")
    if g_low:
        failed.append(f"有 {len(g_low)} 个语法点使用少于 {th['grammar_freq_min']} 次")

    lo, hi = level["constraints"]["bank_target_items"]
    n_valid = len(clean)
    if n_valid < lo or n_valid > hi:
        failed.append(f"合格题量 {n_valid} 不在目标区间 [{lo}, {hi}]")

    # 调整计划：缺口字打包，缺口语法点必须补，低频核心字按当前次数算缺口
    boost_need = {c: th["core_char_freq_min"] - cfreq.get(c, 0) for c in core_low}
    char_batches = []
    pool = sorted(uncovered, key=lambda c: -cfreq.get(c, 0))
    for i in range(0, len(pool), 4):
        char_batches.append(pool[i:i + 4])
    suggest_items = max(
        math.ceil(len(char_batches) * 1.4),          # 每 1-2 题吃掉一批 4 字
        math.ceil(sum(boost_need.values()) / 5),
        math.ceil((len(g_uncovered) + len(g_low)) * 1.5),
        0,
    )

    stats = {
        "level": level["level"], "tag": None, "items_total": len(items),
        "items_valid": n_valid, "items_invalid": len(items) - n_valid,
        "char": {
            "total": len(all_chars), "covered": len(all_chars) - len(uncovered),
            "coverage": cov, "uncovered": uncovered,
            "freq_top": sorted(cfreq.items(), key=lambda kv: -kv[1])[:15],
            "freq_bottom": sorted(cfreq.items(), key=lambda kv: kv[1])[:30],
            "core_below_min": core_low,
        },
        "grammar": {
            "total": grammar_total, "covered": grammar_total - len(g_uncovered),
            "coverage": gcov, "uncovered": g_uncovered, "below_min": g_low,
            "freq": sorted(gfreq.items(), key=lambda kv: -kv[1]),
        },
        "verdict": "pass" if not failed else "fail",
        "failed_checks": failed,
    }
    plan = {
        "level": level["level"],
        "new_chars": uncovered,
        "new_chars_batches": char_batches,
        "boost_chars": boost_need,
        "new_grammar": [{"id": i, "name": gname[i]} for i in g_uncovered],
        "boost_grammar": [{"id": i, "name": gname[i], "have": gfreq[i], "need": th["grammar_freq_min"] - gfreq[i]} for i in g_low],
        "suggested_new_items": suggest_items,
        "guidance": (
            "出下一轮题时：每题围绕 2-4 个缺口字造句，仍只准用本等级字表；"
            "缺口语法点每点至少安排 2 题，尽量与缺口字合并在同一题；"
            "低频核心字按 boost_chars 的次数差额安排进新句。"
        ),
    }
    return stats, plan


def render_md(level, s, tag):
    c, g = s["char"], s["grammar"]
    lines = [
        f"# 覆盖与频次统计报告（{s['level']} 级，标签 {tag}）",
        "",
        f"- 题库：共 {s['items_total']} 题，合格 {s['items_valid']}，不合格剔除 {s['items_invalid']}",
        f"- 字覆盖：{c['covered']}/{c['total']}（{c['coverage']}%），阈值 {level['thresholds']['char_coverage_min'] * 100}%",
        f"- 语法覆盖：{g['covered']}/{g['total']}（{g['coverage']}%）",
        f"- 结论：{'达标' if s['verdict'] == 'pass' else '未达标'}",
        "",
    ]
    if s["failed_checks"]:
        lines.append("## 未达标项")
        lines.extend(f"- {f}" for f in s["failed_checks"])
        lines.append("")
    lines += [
        "## 字频（前 15）",
        "",
        "| 字 | 次数 |", "| --- | --- |",
    ]
    lines += [f"| {ch} | {n} |" for ch, n in c["freq_top"]]
    lines += ["", "## 字频（最稀少 30）", "", "| 字 | 次数 |", "| --- | --- |"]
    lines += [f"| {ch} | {n} |" for ch, n in c["freq_bottom"]]
    if c["uncovered"]:
        lines += ["", f"## 未覆盖字（{len(c['uncovered'])} 个）", "", "、".join(c["uncovered"])]
    if c["core_below_min"]:
        lines += ["", "## 低频核心字（次数不足）", "", "| 字 | 当前次数 |", "| --- | --- |"]
        lines += [f"| {ch} | {n} |" for ch, n in sorted(c["core_below_min"].items(), key=lambda kv: kv[1])]
    lines += ["", "## 语法点频次", "", "| 语法点 | 名称 | 次数 |", "| --- | --- | --- |"]
    gname = {gg["id"]: gg["name"] for gg in level["grammar"]}
    lines += [f"| {gid} | {gname[gid]} | {n} |" for gid, n in g["freq"]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1, help="等级 1—9（数据取自 data/levels/levelN.json）")
    ap.add_argument("--bank", help="题库路径；缺省取 banks/levelN/final.json")
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()

    level = load_level(args.level)
    bank = args.bank or str(default_bank(args.level))
    items = load_bank(bank)
    stats, plan = compute(level, items)
    stats["tag"] = args.tag
    plan["tag"] = args.tag

    d = out_dir(args.level)
    (d / f"stats_{args.tag}.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"adjust_plan_{args.tag}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"stats_{args.tag}.md").write_text(render_md(level, stats, args.tag), encoding="utf-8")

    c, g = stats["char"], stats["grammar"]
    print(f"[统计] 合格 {stats['items_valid']}/{stats['items_total']} 题")
    print(f"[统计] 字覆盖 {c['covered']}/{c['total']}（{c['coverage']}%），未覆盖 {len(c['uncovered'])} 个")
    print(f"[统计] 核心字低频 {len(c['core_below_min'])} 个；语法覆盖 {g['covered']}/{g['total']}，缺口 {len(g['uncovered'])} 个，低频 {len(g['below_min'])} 个")
    print(f"[统计] 结论：{stats['verdict']}")
    for f in stats["failed_checks"]:
        print("  - " + f)
    if stats["verdict"] != "pass":
        print(f"[调整] 建议补充 {plan['suggested_new_items']} 题，详见 reports/level{args.level}/adjust_plan_{args.tag}.json")
        sys.exit(2)


if __name__ == "__main__":
    main()
