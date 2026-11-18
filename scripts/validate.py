# -*- coding: utf-8 -*-
"""等级校验：检查题库每一题是否符合该等级的字表、语法与形式约束。

用法：
    python scripts/validate.py --level 1 --bank banks/level1/round1.json [--tag v1]

退出码：0 全部合格；1 存在不合格题（须先修改或剔除）。
"""
import argparse
import sys

from lib import ROOT, load_bank, load_level, out_dir, validate_bank

sys.stdout.reconfigure(encoding="utf-8")


def render_report(level, results, dup_ids, dup_texts) -> str:
    total = len(results)
    bad = [r for r in results if not r["ok"]]
    warn = [r for r in results if r["ok"] and r["warnings"]]
    lines = [
        f"# 等级校验报告（一级，{total} 题）",
        "",
        f"- 合格：{total - len(bad)} 题",
        f"- 不合格：{len(bad)} 题",
        f"- 合格但有提示：{len(warn)} 题",
        f"- 重复 id：{'、'.join(dup_ids) if dup_ids else '无'}",
        f"- 重复文本：{'、'.join(dup_texts) if dup_texts else '无'}",
        "",
    ]
    if bad:
        lines.append("## 不合格题（须修改或剔除）")
        lines.append("")
        for r in bad:
            it = r["item"]
            lines.append(f"- **{it.get('id','?')}** {it.get('text','')}")
            for e in r["errors"]:
                lines.append(f"  - 问题：{e}")
        lines.append("")
    if warn:
        lines.append("## 合格但有提示（可保留，建议改进）")
        lines.append("")
        for r in warn:
            it = r["item"]
            lines.append(f"- {it.get('id','?')} {it.get('text','')}：{'；'.join(r['warnings'])}")
        lines.append("")
    if not bad and not warn:
        lines.append("全部合格，无提示。")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()

    level = load_level(args.level)
    items = load_bank(args.bank)
    _, results, dup_ids, dup_texts = validate_bank(items, level)

    d = out_dir(args.level)
    report = render_report(level, results, dup_ids, dup_texts)
    (d / f"validate_{args.tag}.md").write_text(report, encoding="utf-8")

    bad = sum(1 for r in results if not r["ok"])
    print(f"[校验] 共 {len(results)} 题：合格 {len(results) - bad}，不合格 {bad}，重复文本 {len(dup_texts)}")
    print(f"报告已写入 reports/level{args.level}/validate_{args.tag}.md")
    if bad or dup_ids:
        sys.exit(1)


if __name__ == "__main__":
    main()
