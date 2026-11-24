# -*- coding: utf-8 -*-
"""Validate a batch of candidate sentences and report the strict-coverage delta.

Candidate file: {"new": [{"text": "...", "grammar": "G3-xx"}, ...]}

Usage:
    python batch_check.py --level 3 --cand draft1.json
"""
import argparse
import json
import re
import sys
from pathlib import Path


def resolve_repo(arg):
    if arg:
        return Path(arg).resolve()
    for c in [Path.cwd(), *Path.cwd().parents]:
        if (c / "scripts" / "lib.py").exists():
            return c
    fallback = Path(r"F:\github\chinese-proposition-subsystem")
    if (fallback / "scripts" / "lib.py").exists():
        return fallback
    raise SystemExit("找不到仓库根目录，请用 --repo 指定")


HAN = re.compile(r"[\u4e00-\u9fff]")


def strict_set(words, texts):
    occ = []
    for t in texts:
        cur = []
        for w in words:
            s = 0
            while (i := t.find(w, s)) >= 0:
                cur.append((i, i + len(w), w))
                s = i + 1
        occ.append(cur)
    strict = set()
    for w in words:
        n = len(w)
        for t, o in zip(texts, occ):
            s = 0
            while (i := t.find(w, s)) >= 0:
                cover = [(a, b, v) for a, b, v in o if a <= i and i + n <= b and (b - a) > n]
                if not cover:
                    strict.add(w)
                    break
                s = i + 1
            if w in strict:
                break
    return strict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--bank", default=None)
    args = ap.parse_args()

    repo = resolve_repo(args.repo)
    sys.path.insert(0, str(repo / "scripts"))
    from lib import load_level, load_vocabulary, load_bank  # noqa: E402

    lvl = load_level(args.level)
    chars = set(lvl["chars"]["all"])
    gmap = {g["id"]: g for g in lvl["grammar"]}
    vocab = load_vocabulary(lvl)
    if not vocab:
        raise SystemExit("该等级没有配置词表")
    words = sorted({x["word"] for x in vocab["items"] if x.get("word")})

    bank = Path(args.bank) if args.bank else repo / f"banks/level{args.level}/final.json"
    base_texts = [it["text"] for it in load_bank(bank)]
    base_strict = strict_set(words, base_texts)

    data = json.loads(Path(args.cand).read_text(encoding="utf-8-sig"))
    cands = data["new"] if isinstance(data, dict) else data

    seen = set(base_texts)
    sets = [set(HAN.findall(t)) for t in base_texts]
    ok, problems = [], []
    for c in cands:
        t, g = c.get("text", "").strip(), c.get("grammar", "").strip()
        hs = HAN.findall(t)
        p = []
        if not (3 <= len(hs) <= 12):
            p.append(f"字数{len(hs)}")
        if unk := sorted({x for x in hs if x not in chars}):
            p.append("越级" + "".join(unk))
        if g not in gmap:
            p.append("语法点不存在")
        if t in seen:
            p.append("重复")
        cur = set(hs)
        if any(cur and s and len(cur & s) / len(cur | s) >= 0.85 for s in sets):
            p.append("近似重复")
        if p:
            problems.append((t, g, "；".join(p)))
        else:
            ok.append(c)
            seen.add(t)
            sets.append(cur)

    gained = sorted(strict_set(words, base_texts + [c["text"] for c in ok]) - base_strict)
    print(f"候选 {len(cands)} 句，通过 {len(ok)}，问题 {len(problems)}")
    for t, g, why in problems:
        print(f"  ✗ [{g}] {t} -> {why}")
    print(f"严格覆盖 {len(base_strict)} → {len(base_strict) + len(gained)}（+{len(gained)}）")
    print("本批新覆盖:", "、".join(gained) if gained else "（无）")
    print(f"全库剩余缺口 {len(words) - len(base_strict) - len(gained)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
