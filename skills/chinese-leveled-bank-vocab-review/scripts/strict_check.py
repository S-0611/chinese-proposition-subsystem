# -*- coding: utf-8 -*-
"""Strict vocabulary coverage for a Chinese levelled bank.

A word counts as covered only if at least one of its occurrences is NOT contained in a
longer word-list word.

Usage:
    python strict_check.py --level 3
    python strict_check.py --level 3 --bank banks/level3/final.json --json out.json
"""
import argparse
import json
import sys
from pathlib import Path


def resolve_repo(arg):
    if arg:
        p = Path(arg).resolve()
        if not (p / "scripts" / "lib.py").exists():
            raise SystemExit(f"--repo 不是仓库根目录：{p}（缺少 scripts/lib.py）")
        return p
    for c in [Path.cwd(), *Path.cwd().parents]:
        if (c / "scripts" / "lib.py").exists():
            return c
    fallback = Path(r"F:\github\chinese-proposition-subsystem")
    if (fallback / "scripts" / "lib.py").exists():
        return fallback
    raise SystemExit("找不到仓库根目录，请用 --repo 指定")


def strict_coverage(words, texts):
    occ = []
    for t in texts:
        cur = []
        for w in words:
            s = 0
            while (i := t.find(w, s)) >= 0:
                cur.append((i, i + len(w), w))
                s = i + 1
        occ.append(cur)

    strict, parasit, never = set(), {}, []
    for w in words:
        n = len(w)
        standalone = 0
        hosts = []
        for t, o in zip(texts, occ):
            s = 0
            while (i := t.find(w, s)) >= 0:
                cover = [(a, b, v) for a, b, v in o if a <= i and i + n <= b and (b - a) > n]
                if cover:
                    if len(hosts) < 3:
                        hosts.append((t, cover[0][2]))
                else:
                    standalone += 1
                s = i + 1
        if standalone:
            strict.add(w)
        elif hosts:
            parasit[w] = hosts
        else:
            never.append(w)
    return strict, parasit, never


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--json", default=None, help="把结果写成 JSON")
    args = ap.parse_args()

    repo = resolve_repo(args.repo)
    sys.path.insert(0, str(repo / "scripts"))
    from lib import load_level, load_vocabulary, load_bank  # noqa: E402

    lvl = load_level(args.level)
    vocab = load_vocabulary(lvl)
    if not vocab:
        raise SystemExit("该等级没有配置 vocabulary.list_path，先接入词表")

    meta = {}
    for x in vocab.get("items") or []:
        if x.get("word"):
            meta.setdefault(x["word"], x)
    words = sorted(meta)
    bank = Path(args.bank) if args.bank else repo / f"banks/level{args.level}/final.json"
    texts = [it["text"] for it in load_bank(bank)]

    strict, parasit, never = strict_coverage(words, texts)
    single = sorted(w for w in parasit if len(w) == 1)
    multi = sorted(w for w in parasit if len(w) > 1)

    print(f"词表 {len(words)} | 严格覆盖 {len(strict)} | 只寄生 {len(parasit)} | 从未出现 {len(never)}")
    print(f"寄生中：单字 {len(single)}，多字 {len(multi)}")

    if never:
        print("\n== 从未出现 ==")
        print("、".join(never))
    if single:
        print("\n== 单字寄生 ==")
        print("、".join(single))
    if multi:
        print("\n== 多字寄生（前 120）==")
        print("、".join(multi[:120]))
    if parasit:
        print("\n== 典型宿主（前 20）==")
        for w in list(parasit)[:20]:
            t, host = parasit[w][0]
            print(f"  {w} ← 「{t}」中的「{host}」")

    if args.json:
        out = {
            "level": args.level, "total": len(words), "strict_covered": len(strict),
            "parasitic": len(parasit), "never_appeared": len(never),
            "single_parasitic": single, "multi_parasitic": multi,
            "targets": [{"word": w, "pinyin": meta[w].get("pinyin"), "pos": meta[w].get("pos"),
                         "status": "parasitic" if w in parasit else "never",
                         "hosts": parasit.get(w, [])} for w in sorted(list(parasit) + never)],
        }
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {args.json}")

    if not never and not parasit:
        print("\n严格口径 100%：寄生 0，缺口 0")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
