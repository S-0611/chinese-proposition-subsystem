# -*- coding: utf-8 -*-
"""Review audits for a levelled bank.

Modes:
    pattern       grammar id vs executable pattern mismatches
    concentration grammar-point concentration (optionally require a surface token)
    unique        words covered only by the given item ids
    pinyin        pinyin format, syllable alignment, polyphones
    redundant     items removable without losing strict vocabulary coverage

Usage:
    python review_audit.py --level 3 --mode pattern
    python review_audit.py --level 3 --mode concentration --gid G3-45 --token 的
    python review_audit.py --level 3 --mode unique --ids L3-555,L3-628
    python review_audit.py --level 3 --mode pinyin
    python review_audit.py --level 3 --mode redundant
"""
import argparse
import json
import re
import sys
from pathlib import Path

HAN = re.compile(r"[\u4e00-\u9fff]")
PUNC = "，。？！、：；"
# pattern 里出现这些词，说明它不是可执行的字面特征，而是语法描述
META = ("引出", "时间", "处所", "方向", "对象", "施事", "受事", "排除", "表示", "动作",
        "持续", "结束", "动词", "形容词", "短语", "数词", "量词", "主语", "宾语", "补语",
        "句型", "强调", "疑问", "语调", "用法", "结构", "类型", "概数", "重叠", "作", "用")


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


def executable(pat):
    """pattern 是否是可执行的字面特征（而非“主谓谓语句”“表使令”这类语法标签）。"""
    if not pat or pat == ".*":
        return False
    if ".*" in pat:                      # 带通配的结构式，如 从.*起 / 越.*越.*
        return True
    parts = [p for p in pat.split("|") if p]
    if not parts:
        return False
    if any(any(m in p for m in META) for p in parts):
        return False
    if any(len(p) > 2 for p in parts):   # 标签通常 3 字以上
        return False
    if len(parts) == 1 and len(set(parts[0])) == 1 and len(parts[0]) > 1:
        return False                     # 形如“不不”的坏正则
    return True


def tokens(p):
    out, cur = [], ""
    for ch in p:
        if ch in PUNC:
            cur += ch
            if cur.strip():
                out.append(cur)
            cur = ""
        elif ch == " ":
            if cur.strip():
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [t.rstrip(PUNC) for t in out]


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
    ap.add_argument("--repo", default=None)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--mode", required=True,
                    choices=["pattern", "concentration", "unique", "pinyin", "redundant"])
    ap.add_argument("--gid", default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    repo = resolve_repo(args.repo)
    sys.path.insert(0, str(repo / "scripts"))
    from lib import load_level, load_vocabulary, load_bank  # noqa: E402

    lvl = load_level(args.level)
    gmap = {g["id"]: g for g in lvl["grammar"]}
    bank = Path(args.bank) if args.bank else repo / f"banks/level{args.level}/final.json"
    items = load_bank(bank)

    if args.mode == "pattern":
        bad = {}
        for it in items:
            if not it.get("grammar"):
                continue
            g = it["grammar"][0]
            gd = gmap.get(g)
            if not gd:
                continue
            pat = gd.get("pattern", "")
            if not executable(pat):
                continue
            if args.gid and g != args.gid:
                continue
            try:
                if pat and not re.search(pat, it["text"]):
                    bad.setdefault(g, []).append(it)
            except re.error:
                pass
        total = sum(len(v) for v in bad.values())
        print(f"可执行 pattern 未命中：{total} / {len(items)}，涉及 {len(bad)} 个语法点")
        print("说明：pattern 多为标准示例词枚举，句子用同类词时也会未命中；")
        print("请按语法点分组判断——结构类（把/被/连动/兼语/比较/复句/固定格式）才是真错标。")
        for g, lst in sorted(bad.items(), key=lambda kv: -len(kv[1])):
            gd = gmap[g]
            print(f"\n  {g} {gd['name']} pattern={gd.get('pattern')}：{len(lst)} 条")
            for it in lst[:args.limit if args.limit < 10 else 6]:
                print(f"    {it['id']} {it['text']}")
        return 0 if not total else 1

    if args.mode == "concentration":
        counts = {}
        for it in items:
            if not it.get("grammar"):
                continue
            counts[it["grammar"][0]] = counts.get(it["grammar"][0], 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
        print("语法点集中度 top8:", "，".join(f"{g}={n}" for g, n in top))
        if args.gid:
            sel = [it for it in items if it.get("grammar") and it["grammar"][0] == args.gid]
            print(f"{args.gid} 共 {len(sel)} 条（占 {len(sel)/len(items)*100:.1f}%）")
            if args.token:
                miss = [it for it in sel if args.token not in it["text"]]
                print(f"不含「{args.token}」的 {len(miss)} 条（应为 0）：")
                for it in miss[:args.limit]:
                    print(f"  {it['id']} {it['text']}")
            else:
                for it in sel[:args.limit]:
                    print(f"  {it['id']} {it['text']}")
        return 0

    if args.mode == "unique":
        vocab = load_vocabulary(lvl)
        if not vocab:
            raise SystemExit("该等级没有配置词表")
        words = sorted({x["word"] for x in vocab["items"] if x.get("word")})
        ids = [x.strip() for x in (args.ids or "").split(",") if x.strip()]
        if not ids:
            raise SystemExit("--mode unique 需要 --ids")
        texts = [it["text"] for it in items]
        base = strict_set(words, texts)
        for it in items:
            if it["id"] not in ids:
                continue
            rest = [t for t in texts if t != it["text"]]
            lost = sorted(base - strict_set(words, rest))
            g = it["grammar"][0] if it.get("grammar") else "—"
            print(f"{it['id']}｜{g}｜{it['text']}｜独家覆盖: {'、'.join(lost) or '（无）'}")
        return 0

    if args.mode == "pinyin":
        bad, poly = [], {}
        for it in items:
            hs = HAN.findall(it["text"])
            ts = tokens(it["pinyin"])
            if len(ts) != len(hs):
                bad.append((it["id"], f"音节 {len(ts)} ≠ 汉字 {len(hs)}"))
                continue
            for c, p in zip(hs, ts):
                if not re.fullmatch(r"[a-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+|r", p):
                    bad.append((it["id"], f"异常音节 {p}"))
                poly.setdefault(c, set()).add(p)
        print(f"音节数/格式异常：{len(bad)}")
        for b in bad[:args.limit]:
            print("  ", b)
        multi = {c: sorted(v) for c, v in poly.items() if len(v) > 1}
        print(f"同字多读音：{len(multi)}")
        for c, v in list(multi.items())[:20]:
            print(f"  {c}: {'/'.join(v)}")
        return 0 if not bad else 1

    if args.mode == "redundant":
        vocab = load_vocabulary(lvl)
        if not vocab:
            raise SystemExit("该等级没有配置词表")
        words = sorted({x["word"] for x in vocab["items"] if x.get("word")})
        texts = [it["text"] for it in items]
        base = strict_set(words, texts)
        removable = []
        for k, it in enumerate(items):
            rest = texts[:k] + texts[k + 1:]
            if strict_set(words, rest) == base:
                removable.append(it["id"])
        print(f"删除后不影响严格词汇覆盖的题：{len(removable)} / {len(items)}")
        print("  ", "、".join(removable[:60]))
        print("注意：这些题通常承担语法操练与汉字复现，删除前先确认语法点每点仍 ≥ grammar_freq_min。")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
