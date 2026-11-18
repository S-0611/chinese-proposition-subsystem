# -*- coding: utf-8 -*-
"""命题校验统计 pipeline 的公共库。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "levels"
REPORT_DIR = ROOT / "reports"

HANZI_RE = re.compile(r"[\u4e00-\u9fff]")
ALLOWED_PUNCT = "，。？！、：；”“’‘—…《》（）"


def load_level(level_no: int) -> dict:
    path = DATA_DIR / f"level{level_no}.json"
    if not path.exists():
        raise FileNotFoundError(f"等级数据不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_bank(path) -> list:
    """题库文件兼容两种格式：纯数组，或 {"items": [...]}。"""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError(f"题库格式不对：{p}（应为数组或含 items 字段的对象）")


def hanzi_of(text: str) -> list:
    return HANZI_RE.findall(text or "")


def validate_item(item: dict, level: dict) -> dict:
    """单题校验，返回 {"ok", "errors", "warnings"}。errors 不通过则该题不计入统计。"""
    cons = level["constraints"]
    gmap = {g["id"]: g for g in level["grammar"]}
    errors, warnings = [], []

    text = item.get("text", "")
    if not text or not text.strip():
        return {"ok": False, "errors": ["text 为空"], "warnings": warnings}

    hs = hanzi_of(text)
    if not hs:
        errors.append("没有任何汉字")

    # 长度
    n = len(hs)
    if n < cons["min_chars"] or n > cons["max_chars"]:
        errors.append(f"字数 {n} 超出范围 [{cons['min_chars']}, {cons['max_chars']}]")

    # 字表
    char_set = set(level["chars"]["all"])
    unknown = sorted({c for c in hs if c not in char_set})
    if unknown:
        errors.append("超出本等级字表：" + "、".join(unknown))

    # 字母数字
    if not cons.get("allow_ascii", False):
        bad = [c for c in text if c.isascii() and c.isalnum()]
        if bad and not cons.get("allow_digits", True):
            errors.append("文本含字母或阿拉伯数字，跟读文本应使用汉字数字")

    # 语法声明
    decl = item.get("grammar") or []
    if not decl:
        warnings.append("未声明任何语法点")
    for gid in decl:
        g = gmap.get(gid)
        if g is None:
            errors.append(f"声明的语法点 {gid} 不属于本等级")
            continue
        pat = g.get("pattern")
        if pat and not re.search(pat, text):
            errors.append(f"声明的语法点 {gid}（{g['name']}）与文本不符（未命中规则 {pat}）")

    # 收尾标点
    if text and text[-1] not in "。？！":
        warnings.append("未以句号、问号或叹号收尾")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_bank(items: list, level: dict) -> tuple:
    """整库校验。返回 (合格题列表, 每题校验结果列表, 重复id, 重复text)。"""
    seen_ids, seen_texts = {}, {}
    dup_ids, dup_texts = set(), set()
    for it in items:
        iid = it.get("id", "")
        txt = it.get("text", "")
        if iid in seen_ids:
            dup_ids.add(iid)
        if txt in seen_texts:
            dup_texts.add(txt)
        seen_ids.setdefault(iid, True)
        seen_texts.setdefault(txt, True)

    results, clean = [], []
    for it in items:
        r = validate_item(it, level)
        results.append({"item": it, **r})
        if r["ok"]:
            clean.append(it)
    return clean, results, sorted(dup_ids), sorted(dup_texts)


def detect_grammar_freq(items: list, level: dict) -> dict:
    """统计语法点使用频次：正则命中或声明过的题各计一次。"""
    freq = {g["id"]: 0 for g in level["grammar"]}
    for it in items:
        text = it.get("text", "")
        decl = set(it.get("grammar") or [])
        for g in level["grammar"]:
            pat = g.get("pattern")
            if g["id"] in decl or (pat and re.search(pat, text)):
                freq[g["id"]] += 1
    return freq


def char_freq(items: list) -> dict:
    freq = {}
    for it in items:
        for c in hanzi_of(it.get("text", "")):
            freq[c] = freq.get(c, 0) + 1
    return freq


def out_dir(level_no: int) -> Path:
    d = REPORT_DIR / f"level{level_no}"
    d.mkdir(parents=True, exist_ok=True)
    return d
