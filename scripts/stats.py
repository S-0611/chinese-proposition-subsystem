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

from lib import (default_bank, load_bank, load_level, load_vocabulary, out_dir,
                 validate_bank, char_freq, detect_grammar_freq)

sys.stdout.reconfigure(encoding="utf-8")


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def compute(level, items):
    clean, results, dup_ids, dup_texts = validate_bank(items, level)
    th = level.get("thresholds") or {}
    char_cov_min = th.get("char_coverage_min", 0.0)
    char_freq_min = th.get("char_freq_min", 0)
    core_freq_min = th.get("core_char_freq_min", 0)
    grammar_cov_min = th.get("grammar_coverage_min", 0.0)
    grammar_freq_min = th.get("grammar_freq_min", 0)
    vocab_cov_min = th.get("vocab_coverage_min", 0.0)

    cfreq = char_freq(clean)
    gfreq = detect_grammar_freq(clean, level)

    # 词汇覆盖：以配置声明的词汇表为准，词条按规范词形去重统计。
    # 题目可以显式声明 vocab_words（词汇/汉字跟读题），也可以由正文自然命中。
    vocab_data = load_vocabulary(level)
    vocab_words = []
    if vocab_data:
        vocab_words = sorted({x["word"] for x in (vocab_data.get("items") or []) if x.get("word")})
    vocab_word_set = set(vocab_words)
    vcovered = set()
    if vocab_words:
        for item in clean:
            for w in item.get("vocab_words") or []:
                if w in vocab_word_set:
                    vcovered.add(w)
            text = item.get("text", "")
            for w in vocab_words:
                if w in text:
                    vcovered.add(w)
    v_uncovered = [w for w in vocab_words if w not in vcovered]

    chars_cfg = level.get("chars") or {}
    # 可用 coverage_chars_key 指定验收口径（如高等只统计新增 1200 字），
    # 否则沿用累计字表/旧配置逻辑。
    coverage_key = level.get("coverage_chars_key")
    if coverage_key and chars_cfg.get(coverage_key):
        all_chars = chars_cfg[coverage_key]
    elif level.get("char_table_mode") == "cumulative":
        all_chars = chars_cfg.get("all") or []
    else:
        all_chars = chars_cfg.get("new") or chars_cfg.get("all") or []
    core_chars = set(chars_cfg.get("core") or [])
    grammar_list = level.get("grammar") or []
    uncovered = [c for c in all_chars if cfreq.get(c, 0) == 0]
    core_low = {c: cfreq.get(c, 0) for c in sorted(core_chars) if cfreq.get(c, 0) < core_freq_min}

    grammar_total = len(grammar_list)
    gname = {g["id"]: g["name"] for g in grammar_list}
    g_uncovered = [g["id"] for g in grammar_list if gfreq[g["id"]] == 0]
    g_low = {g["id"]: gfreq[g["id"]] for g in grammar_list if 0 < gfreq[g["id"]] < grammar_freq_min}

    failed, notes = [], []
    cov = pct(len(all_chars) - len(uncovered), len(all_chars))
    if all_chars:
        if cov < char_cov_min * 100:
            failed.append(f"字覆盖率 {cov}% 低于阈值 {char_cov_min * 100}%")
        if uncovered and char_freq_min > 0:
            failed.append(f"有 {len(uncovered)} 个字出现 0 次")
        if core_low:
            failed.append(f"有 {len(core_low)} 个核心字出现少于 {core_freq_min} 次")
    else:
        notes.append("本等级字表待补，字覆盖率门禁未启用（接入字表后自动生效）")
    gcov = pct(grammar_total - len(g_uncovered), grammar_total)
    if grammar_total:
        if gcov < grammar_cov_min * 100:
            failed.append(f"语法覆盖率 {gcov}% 低于阈值 {grammar_cov_min * 100}%")
        if g_uncovered:
            failed.append(f"有 {len(g_uncovered)} 个语法点使用 0 次")
        if g_low:
            failed.append(f"有 {len(g_low)} 个语法点使用少于 {grammar_freq_min} 次")
    else:
        notes.append("本等级语法点清单待补，语法覆盖率门禁未启用（接入清单后自动生效）")

    vcov = pct(len(vocab_words) - len(v_uncovered), len(vocab_words))
    if vocab_words:
        if vcov < vocab_cov_min * 100:
            failed.append(f"词汇覆盖率 {vcov}% 低于阈值 {vocab_cov_min * 100}%")
            if v_uncovered:
                failed.append(f"有 {len(v_uncovered)} 个词汇出现 0 次")
        # 阈值 < 1.0 时允许存在缺口：缺口清单照常写入 stats / adjust_plan 供后续补题，
        # 但不作为阻断项（阈值 = 1.0 时上一行已等价于“零缺口”）。
    else:
        notes.append("本等级词汇表待补，词汇覆盖率门禁未启用（接入词汇表后自动生效）")

    lo, hi = (level.get("constraints") or {}).get("bank_target_items", [0, 10 ** 9])
    n_valid = len(clean)
    if n_valid < lo or n_valid > hi:
        failed.append(f"合格题量 {n_valid} 不在目标区间 [{lo}, {hi}]")

    # 调整计划：缺口字打包，缺口语法点必须补，低频核心字按当前次数算缺口
    boost_need = {c: core_freq_min - cfreq.get(c, 0) for c in core_low}
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
        "vocabulary": {
            "total": len(vocab_words), "covered": len(vocab_words) - len(v_uncovered),
            "coverage": vcov, "uncovered": v_uncovered,
        },
        "verdict": "pass" if not failed else "fail",
        "failed_checks": failed,
        "notes": notes,
    }
    plan = {
        "level": level["level"],
        "new_chars": uncovered,
        "new_chars_batches": char_batches,
        "boost_chars": boost_need,
        "new_grammar": [{"id": i, "name": gname[i]} for i in g_uncovered],
        "boost_grammar": [{"id": i, "name": gname[i], "have": gfreq[i], "need": grammar_freq_min - gfreq[i]} for i in g_low],
        "new_vocab": v_uncovered[:500],
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
    v = s.get("vocabulary") or {"total": 0, "covered": 0, "coverage": 0, "uncovered": []}
    lines = [
        f"# 覆盖与频次统计报告（{s['level']} 级，标签 {tag}）",
        "",
        f"- 题库：共 {s['items_total']} 题，合格 {s['items_valid']}，不合格剔除 {s['items_invalid']}",
        f"- 字覆盖：{c['covered']}/{c['total']}（{c['coverage']}%），阈值 {(level.get('thresholds') or {}).get('char_coverage_min', 0) * 100}%",
        f"- 词汇覆盖：{v['covered']}/{v['total']}（{v['coverage']}%），阈值 {(level.get('thresholds') or {}).get('vocab_coverage_min', 0) * 100}%",
        f"- 语法覆盖：{g['covered']}/{g['total']}（{g['coverage']}%）",
        f"- 结论：{'达标' if s['verdict'] == 'pass' else '未达标'}",
        "",
    ]
    if s.get("notes"):
        lines.append("## 说明")
        lines.extend(f"- {x}" for x in s["notes"])
        lines.append("")
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
    gname = {gg["id"]: gg["name"] for gg in (level.get("grammar") or [])}
    lines += [f"| {gid} | {gname[gid]} | {n} |" for gid, n in g["freq"]]
    if v["uncovered"]:
        lines += ["", f"## 未覆盖词汇（{len(v['uncovered'])} 个）", "", "、".join(v["uncovered"])]
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

    c, g, v = stats["char"], stats["grammar"], stats["vocabulary"]
    print(f"[统计] 合格 {stats['items_valid']}/{stats['items_total']} 题")
    print(f"[统计] 字覆盖 {c['covered']}/{c['total']}（{c['coverage']}%），未覆盖 {len(c['uncovered'])} 个")
    print(f"[统计] 词汇覆盖 {v['covered']}/{v['total']}（{v['coverage']}%），未覆盖 {len(v['uncovered'])} 个")
    print(f"[统计] 核心字低频 {len(c['core_below_min'])} 个；语法覆盖 {g['covered']}/{g['total']}，缺口 {len(g['uncovered'])} 个，低频 {len(g['below_min'])} 个")
    print(f"[统计] 结论：{stats['verdict']}")
    for f in stats["failed_checks"]:
        print("  - " + f)
    if stats["verdict"] != "pass":
        print(f"[调整] 建议补充 {plan['suggested_new_items']} 题，详见 reports/level{args.level}/adjust_plan_{args.tag}.json")
        sys.exit(2)


if __name__ == "__main__":
    main()
