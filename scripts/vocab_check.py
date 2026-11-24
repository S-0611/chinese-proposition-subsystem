# -*- coding: utf-8 -*-
"""词汇覆盖统计：对照 data/vocabulary/levelN.json 统计题库对等级词汇的覆盖。

用法：
    python scripts/vocab_check.py --level 1 [--bank banks/level1/final.json] [--tag v1]

退出码：0 达标；2 未达标。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import ROOT, default_bank, load_bank, load_level, out_dir

sys.stdout.reconfigure(encoding='utf-8')


def load_vocab(level_no: int):
    path = ROOT / "data" / "vocabulary" / f"level{level_no}.json"
    if not path.exists():
        return None, path
    return json.loads(path.read_text(encoding="utf-8")), path


def compute(vocab, items):
    entries = vocab.get("entries") or []
    texts = [it.get("text", "") for it in items]
    covered, uncovered = [], []
    for e in entries:
        variants = e.get("variants") or [e.get("word", "")]
        hit = any(v and v in t for v in variants for t in texts)
        (covered if hit else uncovered).append(e.get("word", ""))
    total = len(entries)
    cov = round(len(covered) / total * 100, 1) if total else 0.0
    return {
        "total": total,
        "covered": len(covered),
        "coverage": cov,
        "uncovered": uncovered,
    }


def render_md(level_no, vocab, s, tag, threshold):
    lines = [
        f"# 词汇覆盖统计（{level_no} 级，标签 {tag}）",
        "",
        f"- 词汇表：{vocab.get('source', '')}（{vocab.get('level_label', '')}，共 {s['total']} 条）",
        f"- 覆盖：{s['covered']}/{s['total']}（{s['coverage']}%），阈值 {threshold * 100}%",
        f"- 结论：{'达标' if s['coverage'] >= threshold * 100 else '未达标'}",
        "",
    ]
    if s["uncovered"]:
        lines += [f"## 未覆盖词（{len(s['uncovered'])}）", "", "、".join(s["uncovered"]), ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--bank")
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()

    level = load_level(args.level)
    vocab, vpath = load_vocab(args.level)
    if vocab is None:
        print(f"[词汇] 等级 {args.level} 无词汇表（{vpath}），跳过")
        return

    items = load_bank(args.bank or str(default_bank(args.level)))
    s = compute(vocab, items)
    threshold = float((level.get("thresholds") or {}).get("vocabulary_coverage_min", 0.0))

    d = out_dir(args.level)
    (d / f"vocab_{args.tag}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"vocab_{args.tag}.md").write_text(render_md(args.level, vocab, s, args.tag, threshold), encoding="utf-8")

    print(f"[词汇] 覆盖 {s['covered']}/{s['total']}（{s['coverage']}%），未覆盖 {len(s['uncovered'])} 个，阈值 {threshold * 100}%")
    if s["coverage"] < threshold * 100:
        print("[词汇] 未达标，未覆盖词：" + "、".join(s["uncovered"][:40]))
        sys.exit(2)


if __name__ == "__main__":
    main()
