# -*- coding: utf-8 -*-
"""严格口径词汇覆盖检查：词的每次出现都不能被更长的词表词包含。

用法：
    python scripts/check_vocab_strict.py --level 4 [--bank banks/level4/final.json] [--tag precheck]
输出：
    reports/levelN/vocab_strict_<tag>.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import load_bank, load_level, load_vocabulary, out_dir  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')


def analyze(level_no, bank, tag):
    level = load_level(level_no)
    vocab = load_vocabulary(level) or {}
    words = sorted({x['word'] for x in (vocab.get('items') or []) if x.get('word')})
    texts = [it['text'] for it in load_bank(bank)]

    occ_by_text = []
    for t in texts:
        occ = []
        for w in words:
            s = 0
            while (i := t.find(w, s)) >= 0:
                occ.append((i, i + len(w), w))
                s = i + 1
        occ_by_text.append(occ)

    strict, parasit, absent = set(), {}, []
    for w in words:
        n = len(w)
        standalone = 0
        hosts = {}
        seen = False
        for t, occ in zip(texts, occ_by_text):
            s = 0
            while (i := t.find(w, s)) >= 0:
                seen = True
                cover = [(a, b, v) for a, b, v in occ if a <= i and i + n <= b and (b - a) > n]
                if cover:
                    for _, _, v in cover:
                        hosts.setdefault(v, []).append(t)
                else:
                    standalone += 1
                s = i + 1
        if standalone:
            strict.add(w)
        elif not seen:
            absent.append(w)
        else:
            parasit[w] = {k: v[:2] for k, v in list(hosts.items())[:3]}

    single = [w for w in parasit if len(w) == 1]
    multi = [w for w in parasit if len(w) > 1]
    report = {
        'level': level_no,
        'bank': str(bank),
        'tag': tag,
        'words_total': len(words),
        'strict_covered': len(strict),
        'strict_coverage': round(len(strict) / len(words) * 100, 2) if words else 0.0,
        'parasitic_count': len(parasit),
        'absent_count': len(absent),
        'parasitic_single': sorted(single),
        'parasitic_multi': sorted(multi),
        'parasitic_detail': parasit,
        'absent': sorted(absent),
        'uncovered': sorted(set(parasit) | set(absent)),
    }
    d = out_dir(level_no)
    path = d / ('vocab_strict_%s.json' % tag)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print('[严格口径] 词表 %d，严格覆盖 %d（%.1f%%），寄生 %d（单字 %d / 多字 %d），从未出现 %d' % (
        len(words), len(strict), report['strict_coverage'],
        len(parasit), len(single), len(multi), len(absent)))
    print('报告：', path)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=4)
    ap.add_argument('--bank', default=None)
    ap.add_argument('--tag', default='precheck')
    a = ap.parse_args()
    from lib import default_bank
    analyze(a.level, a.bank or str(default_bank(a.level)), a.tag)
