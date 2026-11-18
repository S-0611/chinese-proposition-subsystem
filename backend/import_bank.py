# -*- coding: utf-8 -*-
"""题库导入脚本（成员B 任务2/3 交付物）。

把 banks/level1/final.json 导入 SQLite：
  - 生成统一字段：id / level / text / tokens / grammar / status / rec_count / last_selected_at
  - tokens 以题库自带的 pinyin 字段为权威（人工复核过的多音字优先），按拼音音节切分逐字绑定；
    切分失败时回退 pypinyin 逐字生成，并在摘要里提示差异，供成员A 人工复核。
  - 初始 rec_count=0，last_selected_at=null，status='ready'（入库控制：仅已达标题库可导入）。

用法（项目根目录）：
    python backend/import_bank.py
    python backend/import_bank.py --bank banks/level1/round2.json --level 1
    python backend/import_bank.py --force   # 已存在的题也整体覆盖（重置运行字段）
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import hanzi_of, load_bank  # noqa: E402
import db  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# ── 拼音音节切分（tone-mark 风格）────────────────────────────
INITIALS = "zh|ch|sh|b|p|m|f|d|t|n|l|g|k|h|j|q|x|r|z|c|s|y|w"
_VOWEL = {
    "a": "aāáǎà", "o": "oōóǒò", "e": "eēéěè",
    "i": "iīíǐì", "u": "uūúǔù", "ü": "üǖǘǚǜ",
}
FINALS_LONGEST_FIRST = [
    "iong", "iang", "uang", "ueng", "uan", "uai", "ian", "iao",
    "ang", "eng", "ing", "ong", "ai", "ei", "ao", "ou", "an", "en",
    "er", "ia", "ie", "iu", "ui", "un", "ua", "uo", "üe", "ue",
    "a", "o", "e", "i", "u", "ü", "v",
]


def _final_re(s: str) -> str:
    out = []
    for ch in s:
        out.append(f"[{_VOWEL.get(ch, ch)}]" if ch in _VOWEL else ch)
    return "".join(out)


_FINAL_ALT = "|".join(_final_re(f) for f in FINALS_LONGEST_FIRST)
_SYL_RE = re.compile(rf"(?:{INITIALS})?(?:{_FINAL_ALT})")


def segment_pinyin(py_str: str):
    """把 pinyin 字段按音节切成列表；失败返回 None。"""
    if not py_str:
        return None
    chunks = re.split(r"[^A-Za-züÜǖǘǚǜ]+", py_str)
    syllables = []
    for chunk in chunks:
        if not chunk:
            continue
        low = chunk.lower()
        pos, seg = 0, []
        while pos < len(low):
            m = _SYL_RE.match(low, pos)
            if not m or m.end() == pos:
                return None
            seg.append(m.group(0))
            pos = m.end()
        if pos != len(low):
            return None
        syllables.extend(seg)
    return syllables


def build_tokens(text: str, pinyin_field: str):
    """返回 (tokens, note)。tokens 逐字对应；note 说明多音字差异（供人工复核）。"""
    from pypinyin import Style, pinyin as py_pinyin
    hs = hanzi_of(text)
    seg = segment_pinyin(pinyin_field or "")
    if seg and len(seg) == len(hs):
        tokens = [{"c": c, "py": s} for c, s in zip(hs, seg)]
    else:
        py = py_pinyin(text, style=Style.TONE, errors="default")
        # 按汉字位置取 pypinyin 结果（非汉字符号会原样出现在结果里，需过滤）
        hs_set = set(hs)
        hanzi_py = [p[0] for p, ch in zip(py, text) if ch in hs_set]
        tokens = [{"c": c, "py": p} for c, p in zip(hs, hanzi_py)]
    # 多音字提示：pinyin 字段与 pypinyin 默认读音不一致的位置
    py_ref = py_pinyin(text, style=Style.TONE, errors="default")
    hanzi_ref = [p[0] for p, ch in zip(py_ref, text) if ch in set(hs)]
    diffs = [
        f"{t['c']}: 题库={t['py']} / pypinyin={r}"
        for t, r in zip(tokens, hanzi_ref)
        if t["py"].lower() != r.lower()
    ]
    return tokens, "；".join(diffs) if diffs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=str(ROOT / "banks" / "level1" / "final.json"))
    ap.add_argument("--level", type=int, default=None)
    ap.add_argument("--db", default=str(db.DB_PATH))
    ap.add_argument("--force", action="store_true",
                    help="覆盖已有题目（包括重置 rec_count / last_selected_at / status）")
    args = ap.parse_args()

    items = load_bank(args.bank)
    conn = db.connect(args.db)
    db.init_schema(conn)

    imported = updated = skipped = 0
    poly_notes = []
    bad_items = []
    for it in items:
        level = args.level or it.get("level") or 1
        text = (it.get("text") or "").strip()
        hs = hanzi_of(text)
        if not it.get("id") or not text:
            bad_items.append(f"{it.get('id','?')}: 缺 id 或 text")
            skipped += 1
            continue
        if "tokens" in it and len(it.get("tokens") or []) == len(hs):
            tokens = it["tokens"]
            note = None
        else:
            tokens, note = build_tokens(text, it.get("pinyin", ""))
        if len(tokens) != len(hs):
            bad_items.append(f"{it['id']}: tokens({len(tokens)}) 与汉字数({len(hs)})不一致，已跳过")
            skipped += 1
            continue
        if note:
            poly_notes.append(f"{it['id']} {note}")

        exists = conn.execute("SELECT id FROM questions WHERE id=?", (it["id"],)).fetchone()
        if exists and not args.force:
            updated += 1
            continue  # 保留已入库题的运行字段，避免覆盖 rec_count 等
        row = (
            it["id"], level, text,
            json.dumps(tokens, ensure_ascii=False),
            json.dumps(it.get("grammar") or [], ensure_ascii=False),
            it.get("status", "ready") if args.force else "ready",
            0 if args.force else (exists and _keep(conn, it["id"])[0] or 0),
            None if args.force else (exists and _keep(conn, it["id"])[1] or None),
        )
        conn.execute(
            "INSERT INTO questions (id, level, text, tokens, grammar, status, rec_count, last_selected_at) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET level=excluded.level, text=excluded.text, "
            "tokens=excluded.tokens, grammar=excluded.grammar, status=excluded.status, "
            "rec_count=excluded.rec_count, last_selected_at=excluded.last_selected_at",
            row)
        imported += 1
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    lv1 = conn.execute("SELECT COUNT(*) FROM questions WHERE level=1").fetchone()[0]
    db.add_run(conn, "import", args.level or 1,
               {"bank": str(args.bank), "source_items": len(items),
                "imported": imported, "updated_kept": updated,
                "skipped": skipped, "bad_items": bad_items})

    print(f"[import] 源题库：{args.bank}，共 {len(items)} 题")
    print(f"[import] 新导入 {imported} 题，已存在且保留运行字段 {updated} 题，跳过 {skipped} 题")
    if bad_items:
        print("[import] 跳过明细：")
        for b in bad_items:
            print("  - " + b)
    print(f"[import] 数据库现有 {total} 题，其中一级 {lv1} 题")
    if poly_notes:
        print(f"[import] 多音字提示（{len(poly_notes)} 题，建议人工复核）：")
        for p in poly_notes[:20]:
            print("  - " + p)
        if len(poly_notes) > 20:
            print(f"  … 其余 {len(poly_notes) - 20} 题略")
    else:
        print("[import] 无多音字差异提示")
    if skipped:
        sys.exit(1)


def _keep(conn, qid):
    row = conn.execute("SELECT rec_count, last_selected_at FROM questions WHERE id=?", (qid,)).fetchone()
    return (row["rec_count"], row["last_selected_at"]) if row else (0, None)


if __name__ == "__main__":
    main()
