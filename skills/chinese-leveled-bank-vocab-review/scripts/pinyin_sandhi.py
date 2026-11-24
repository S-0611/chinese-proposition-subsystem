# -*- coding: utf-8 -*-
"""Convert a bank's pinyin to context readings: 一/不 sandhi, neutral tones, 儿化 → r.

Usage:
    python pinyin_sandhi.py --level 3                  # dry run, prints the diff
    python pinyin_sandhi.py --level 3 --apply          # writes the bank (timestamped backup)

After --apply: re-import (backend/import_bank.py --force) and re-publish.
Requires `pypinyin`; the importer must accept the `r` syllable.
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from pypinyin import pinyin, Style
from pypinyin.contrib.tone_convert import to_tone

HAN = re.compile(r"[\u4e00-\u9fff]")
PUNC = "，。？！、：；"
# 儿化的前一字（按需扩充）
ERHUA_PREV = set("点会这玩孩事条哪空头那怎好一会下个偷伙同")


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


def readings_t3(text):
    res = pinyin(text, style=Style.TONE3, neutral_tone_with_five=True, errors="default")
    return [item[0] for ch, item in zip(text, res) if HAN.match(ch)]


def tone_of(s):
    m = re.search(r"([1-5])$", s)
    return int(m.group(1)) if m else 0


def apply_sandhi(sylls, chars):
    out = list(sylls)
    for i, ch in enumerate(chars):
        if ch == "一":
            if i > 0 and chars[i - 1] == "第":
                out[i] = "yi1"
                continue
            nxt = next((tone_of(out[j]) for j in range(i + 1, len(out))), None)
            out[i] = "yi2" if nxt == 4 else "yi4" if nxt in (1, 2, 3) else "yi1"
        elif ch == "不":
            nxt = next((tone_of(out[j]) for j in range(i + 1, len(out))), None)
            out[i] = "bu2" if nxt == 4 else "bu4"
    return out


def build(text):
    chars = [c for c in text if HAN.match(c)]
    t3 = apply_sandhi(readings_t3(text), chars)
    pieces = ["r" if (c == "儿" and i > 0 and chars[i - 1] in ERHUA_PREV) else t3[i]
              for i, c in enumerate(chars)]
    return chars, pieces


def render(text, pieces):
    out, k = [], 0
    for ch in text:
        if HAN.match(ch):
            tok = pieces[k] if pieces[k] == "r" else to_tone(pieces[k])
            k += 1
            if out and out[-1][-1] not in PUNC:
                out.append(" ")
            out.append(tok)
        elif ch in PUNC:
            out.append(ch)
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    repo = resolve_repo(args.repo)
    path = Path(args.bank) if args.bank else repo / f"banks/level{args.level}/final.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    items = bank["items"]

    changed, bad = [], []
    for it in items:
        chars, pieces = build(it["text"])
        if len(chars) != len(HAN.findall(it["text"])):
            bad.append(it["id"])
            continue
        new = render(it["text"], pieces)
        if new != it["pinyin"]:
            changed.append((it["id"], it["text"], it["pinyin"], new))

    print(f"总题 {len(items)}，拼音将变化 {len(changed)}，异常 {len(bad)}")
    for r in changed[:args.limit]:
        print(f"  {r[0]} {r[1]}")
        print(f"     旧: {r[2]}")
        print(f"     新: {r[3]}")

    if not args.apply:
        print("\n（未写入；加 --apply 生效）")
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(path.name + f".bak_{ts}_before_sandhi")
    if backup.exists():
        raise SystemExit(f"备份已存在，拒绝覆盖：{backup}")
    shutil.copy2(path, backup)
    for it in items:
        if it["id"] in {c[0] for c in changed}:
            it["pinyin"] = next(c[3] for c in changed if c[0] == it["id"])
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {path}，备份 {backup.name}")
    print("下一步：python backend/import_bank.py --bank <bank> --level N --force，再 publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
