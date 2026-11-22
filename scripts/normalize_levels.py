# -*- coding: utf-8 -*-
"""把 data/levels/level2—9.json 统一成 level1.json 的模板结构。

背景：2026-11-21 提交的 2—9 级文件直接用了标准里的统计口径（chars 平铺、
grammar 只有条数），pipeline 读取时 KeyError。本脚本做结构转换：

  - chars：{"all": 累计字表, "core": [], "new": 本级新增}
    二级 600 = 一级 300 + 二级新增 300，依此类推；7—9 级标准未给分级字表，
    all 留空并注明待补（不造假）。
  - grammar：[]（标准附录 A 的语法点清单未随文件交付，留空并注明待补）
  - constraints / thresholds：按一级口径 + 文档《命题流水线说明》建议
    （二级句长 4—16，覆盖率阈值不变），缺依据的标“暂定/待确认”。
  - tier：一至三级 beginner，四级 inter，五级以上 advanced（见流水线说明第九节）。

用法：
    python scripts/normalize_levels.py          # 就地转换 2—9 级
    python scripts/normalize_levels.py --check  # 只检查，不写文件
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "levels"
sys.stdout.reconfigure(encoding="utf-8")

TIER = {1: "beginner", 2: "beginner", 3: "beginner", 4: "inter", 5: "advanced",
        6: "advanced", 7: "advanced", 8: "advanced", 9: "advanced"}

# 句长上限：二级按文档建议 4—16；其余逐级 +4，均标“暂定待确认”
MAX_CHARS = {2: 16, 3: 20, 4: 24, 5: 28, 6: 32, 7: 36, 8: 40, 9: 44}

BASE_THRESHOLDS = {
    "char_coverage_min": 0.9,
    "char_freq_min": 1,
    "core_char_freq_min": 3,
    "grammar_coverage_min": 1.0,
    "grammar_freq_min": 2,
}


def load(n):
    return json.loads((DATA / f"level{n}.json").read_text(encoding="utf-8"))


def new_chars(d, n):
    """取本级新增字表；一级是 {all, core}，7—9 级没有分级字表，返回空。"""
    c = d.get("chars")
    if isinstance(c, list):
        return c
    if isinstance(c, dict):
        if n == 1:
            return c.get("all") or []
        return c.get("new") or []
    return []


def cumulative(n, cache):
    """累计字表：一级起逐级并入新增字，保持首次出现顺序、去重。"""
    seen, out = set(), []
    for lv in range(1, n + 1):
        for ch in new_chars(cache[lv], lv):
            if ch not in seen:
                seen.add(ch)
                out.append(ch)
    return out


def convert(n, cache):
    src = cache[n]
    all_chars = cumulative(n, cache)
    has_chars = bool(all_chars) and n <= 6
    grammar_note = src.get("grammar", {}).get("note") if isinstance(src.get("grammar"), dict) else None
    g_new = src.get("grammar", {}).get("new_count") if isinstance(src.get("grammar"), dict) else None

    chars = {
        "all": all_chars if has_chars else [],
        "core": [],
        "note": (
            "核心字表未随文件交付，暂不设核心字频门禁"
            if has_chars else
            f"高等字表待补：累计 {src.get('chars_total_count', '?')} 字、新增 "
            f"{src.get('chars_new_count', '?')} 字，标准未按 7/8/9 分级，需补 5.8.3 手写字表与认读字表"
        ),
    }
    if n <= 6:
        chars["new"] = new_chars(src, n)
        chars["cumulative_count"] = len(all_chars)

    grammar = []
    appendix = f"A.{n}" if n <= 6 else "A.7"
    if n >= 7:
        grammar_note_text = (
            "语法点清单待补：高等语法点 148 条（附录 A.7，七至九级共用），"
            "当前不参与校验与统计"
        )
    else:
        grammar_note_text = (
            f"语法点清单待补：本等级应新增 {g_new if g_new is not None else '?'} 条"
            f"（标准附录 {appendix}），当前不参与校验与统计"
        )
    if grammar_note:
        grammar_note_text += f"；标准说明：{grammar_note}"

    th = dict(BASE_THRESHOLDS)
    th["grammar_coverage_min"] = 0.0
    th["grammar_freq_min"] = 0
    if not has_chars:
        th["char_coverage_min"] = 0.0
        th["char_freq_min"] = 0

    constraints = {
        "min_chars": 4 if n == 2 else 3,
        "max_chars": MAX_CHARS[n],
        "allow_ascii": False,
        "allow_digits": False,
        "bank_target_items": [110, 280],
        "note": "句长/题量为暂定值（二级取文档建议 4—16，其余逐级 +4；题量沿用一级），待项目负责人确认",
    }

    out = {
        "level": n,
        "name": src.get("name") or f"{'一二三四五六七八九'[n - 1]}级",
        "tier": TIER[n],
        "source_note": (
            "依据《国际中文教育中文水平等级标准》(GF 0025-2021) 整理；"
            + (f"字表累计 {len(all_chars)} 字，本级新增 {len(new_chars(src, n))} 字；"
               if has_chars else "分级字表待补（标准未按 7/8/9 级拆分）；")
            + "语法点清单待补录。"
        ),
        "constraints": constraints,
        "thresholds": th,
        "chars": chars,
        "grammar": grammar,
        "grammar_note": grammar_note_text,
        "syllables": src.get("syllables"),
        "vocabulary": src.get("vocabulary"),
        "chars_total_count": src.get("chars_total_count"),
        "chars_new_count": src.get("chars_new_count"),
        "core_chars_count": src.get("core_chars_count"),
        "core_chars_total_count": src.get("core_chars_total_count"),
        "core_chars_note": src.get("core_chars_note"),
        "boundary": src.get("boundary"),
    }
    # 去掉值为 None 的参考字段，保持文件干净
    return {k: v for k, v in out.items() if v is not None}


def check(n, d):
    problems = []
    for k in ("level", "name", "tier", "constraints", "thresholds", "chars", "grammar"):
        if k not in d:
            problems.append(f"缺 {k}")
    if not isinstance(d.get("chars"), dict) or "all" not in d.get("chars", {}):
        problems.append("chars 不是 {all, core}")
    if not isinstance(d.get("grammar"), list):
        problems.append("grammar 不是数组")
    if not isinstance(d.get("constraints"), dict):
        problems.append("constraints 不是对象")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = ap.parse_args()

    cache = {n: load(n) for n in range(1, 10)}
    for n in range(2, 10):
        d = convert(n, cache)
        problems = check(n, d)
        if problems:
            print(f"level{n}: FAIL " + "；".join(problems))
            continue
        n_all = len(d["chars"]["all"])
        status = f"chars.all={n_all}, grammar=0"
        if args.check:
            print(f"level{n}: OK ({status})")
            continue
        path = DATA / f"level{n}.json"
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        print(f"level{n}: 已写入 ({status})")


if __name__ == "__main__":
    main()
