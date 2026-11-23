# -*- coding: utf-8 -*-
"""命题校验统计 pipeline 的公共库。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "levels"
REPORT_DIR = ROOT / "reports"

HANZI_RE = re.compile(r"[\u4e00-\u9fff]")
ALLOWED_PUNCT = "，。？！、：；""''—…《》（）"

# 九级题库统一支持范围（一级至九级）
SUPPORTED_LEVELS = range(1, 10)


def default_bank(level_no: int) -> Path:
    """按等级组织的题库默认位置：banks/levelN/final.json。"""
    return ROOT / "banks" / f"level{level_no}" / "final.json"


def load_level(level_no: int) -> dict:
    if level_no not in SUPPORTED_LEVELS:
        raise ValueError(f"等级 {level_no} 超出支持范围（1—9）")
    path = DATA_DIR / f"level{level_no}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"等级 {level_no} 的配置不存在：{path}\n"
            f"请先依据《国际中文教育中文水平等级标准》整理该等级字表/核心字/语法点，"
            f"生成 data/levels/level{level_no}.json（缺失内容标注“待标准确认”，不要用其他等级数据冒充）"
        )
    level = json.loads(path.read_text(encoding="utf-8"))
    # 七至九级按标准合并为同一个高等等级；8/9 级配置保留为别名，统一回落到 7 级。
    if level.get("merged_into"):
        return load_level(int(level["merged_into"]))
    # 二级及以上题目使用累计字表；配置文件仍保留本级标准字表，
    # 由这里统一合并低等级字表，避免把常用低等级字误判为越级字。
    if level.get("char_table_mode") == "cumulative" and level_no > 1:
        merged = []
        for n in range(1, level_no + 1):
            prev = DATA_DIR / f"level{n}.json"
            if prev.exists():
                chars = (json.loads(prev.read_text(encoding="utf-8")).get("chars") or {}).get("all") or []
                for ch in chars:
                    if ch not in merged:
                        merged.append(ch)
        if merged:
            level.setdefault("chars", {})["all"] = merged
    return level


def load_bank(path) -> list:
    """题库文件兼容两种格式：纯数组，或 {"items": [...]}。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"题库文件不存在：{p}（该等级题库可能尚未整理完成，请勿用其他等级题库代替）")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError(f"题库格式不对：{p}（应为数组或含 items 字段的对象）")


def load_vocabulary(level: dict) -> dict | None:
    """读取等级配置中声明的词汇表；没有词汇表时返回 None。"""
    cfg = level.get("vocabulary") or {}
    rel = cfg.get("list_path")
    if not rel:
        return None
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(f"词汇表不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def hanzi_of(text: str) -> list:
    return HANZI_RE.findall(text or "")


def validate_item(item: dict, level: dict) -> dict:
    """单题校验，返回 {"ok", "errors", "warnings"}。errors 不通过则该题不计入统计。"""
    cons = level.get("constraints") or {}
    min_chars = cons.get("min_chars", 1)
    max_chars = cons.get("max_chars", 10 ** 6)
    grammar_list = level.get("grammar") or []
    gmap = {g["id"]: g for g in grammar_list}
    all_chars = (level.get("chars") or {}).get("all") or []
    errors, warnings = [], []

    text = item.get("text", "")
    if not text or not text.strip():
        return {"ok": False, "errors": ["text 为空"], "warnings": warnings}

    hs = hanzi_of(text)
    if not hs:
        errors.append("没有任何汉字")

    # 长度
    n = len(hs)
    if n < min_chars or n > max_chars:
        errors.append(f"字数 {n} 超出范围 [{min_chars}, {max_chars}]")

    # 字表（out_of_list_mode=warn 时只告警，用于官方字表未齐前的过渡口径）
    if all_chars:
        char_set = set(all_chars)
        unknown = sorted({c for c in hs if c not in char_set})
        if unknown:
            msg = "超出本等级字表：" + "、".join(unknown)
            if (level.get("chars") or {}).get("out_of_list_mode") == "warn":
                warnings.append(msg + "（警告，不阻断）")
            else:
                errors.append(msg)
    else:
        warnings.append("本等级字表待补，已跳过字表越界检查")

    # 字母数字
    if not cons.get("allow_ascii", False):
        bad = [c for c in text if c.isascii() and c.isalnum()]
        if bad and not cons.get("allow_digits", True):
            errors.append("文本含字母或阿拉伯数字，跟读文本应使用汉字数字")

    # 语法声明
    decl = item.get("grammar") or []
    # 词汇跟读/汉字跟读题只承担覆盖任务，不强行绑定语法点。
    if not decl and item.get("kind") not in {"vocabulary", "character"}:
        warnings.append("未声明任何语法点")
    if decl and not gmap:
        warnings.append("本等级语法点清单待补，已跳过语法点校验")
    for gid in decl:
        g = gmap.get(gid)
        if g is None:
            if gmap:
                errors.append(f"声明的语法点 {gid} 不属于本等级")
            continue
        pat = g.get("pattern")
        if level.get("grammar_validation") == "id_only":
            continue
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
    grammar_list = level.get("grammar") or []
    id_only = level.get("grammar_validation") == "id_only"
    freq = {g["id"]: 0 for g in grammar_list}
    for it in items:
        text = it.get("text", "")
        decl = set(it.get("grammar") or [])
        for g in grammar_list:
            pat = g.get("pattern")
            if g["id"] in decl or (not id_only and pat and re.search(pat, text)):
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
