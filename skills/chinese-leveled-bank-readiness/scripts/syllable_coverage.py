# -*- coding: utf-8 -*-
"""音节表与覆盖。

优先用配置里的官方音节表（syllables.table）；没有时由词表拼音派生（并标注口径）。
覆盖率 = 官方表中在题库读音里出现过的音节数 / 表音节数。

用法：python syllable_coverage.py --level 2
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.environ.get('BANK_ROOT') or os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(B, 'scripts'))
from lib import load_level, load_bank  # noqa: E402

INITIALS = ['zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
            'j', 'q', 'x', 'r', 'z', 'c', 's', 'y', 'w', '']
FINALS = ['iang', 'iong', 'uang', 'ueng', 'ian', 'iao', 'uai', 'uan', 'ang', 'eng',
          'ing', 'ong', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ia', 'ie', 'iu', 'in',
          'ua', 'uo', 'ui', 'un', 've', 'van', 'vn', 'a', 'o', 'e', 'i', 'u', 'v', 'er']
SYLSET = {i + f for i in INITIALS for f in FINALS}
TONE = str.maketrans('āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹ', 'aaaaeeeeiiiioooouuuuvvvvvnnn')
STRIP = re.compile(r'[^a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹv]')
SEP = r'[\s，。？！、；：]+'


def strip_tone(s):
    return s.translate(TONE).replace('ü', 'v')


def split_syllables(py):
    t = strip_tone(py)
    out, i = [], 0
    while i < len(t):
        for L in range(4, 0, -1):
            if t[i:i + L] in SYLSET:
                out.append(py[i:i + L])
                i += L
                break
        else:
            return None
    return out


def derived_table(level):
    """词表拼音派生：口径自证，仅在没有官方表时兜底。"""
    table = {}
    for lv in range(1, level + 1):
        vd = json.load(open(os.path.join(B, 'data', 'vocabulary', 'level%d.json' % lv), encoding='utf-8'))
        for x in vd.get('items') or []:
            p = split_syllables(STRIP.sub('', x.get('pinyin') or ''))
            if p and len(p) == len(x['word']):
                for s in p:
                    table.setdefault(s, x['word'])
    return table


def bank_syllables(level):
    out = set()
    for lv in range(1, level + 1):
        for it in load_bank(os.path.join(B, 'banks', 'level%d' % lv, 'final.json')):
            for tok in re.split(SEP, it['pinyin']):
                if tok:
                    out.add(tok)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, required=True)
    args = ap.parse_args()
    lvl = load_level(args.level)
    syl = lvl.get('syllables') or {}
    if syl.get('table'):
        table = list(dict.fromkeys(syl['table']))
        basis = '官方表（配置 syllables.table）'
    else:
        table = sorted(derived_table(args.level))
        basis = '词表派生（无官方表，口径自证，慎用）'
    got = bank_syllables(args.level)
    covered = set(table) & got
    missing = sorted(set(table) - got)
    pct = 100 * len(covered) / len(table) if table else 0
    print('口径：%s' % basis)
    print('音节表 %d 条（去重 %d）' % (len(table), len(set(table))))
    print('题库覆盖 %d（%.1f%%），整缺 %d' % (len(covered), pct, len(missing)))
    print('缺口：', ' '.join(missing[:40]))
