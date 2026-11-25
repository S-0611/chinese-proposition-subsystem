# -*- coding: utf-8 -*-
"""分级题库「人工复核准入」门禁。

用法：
    python gate.py --level 2 [--out 输出目录]

检查 20 项：结构、形式、字表、拼音、标注、覆盖、重复、体例。
全部通过才输出"可以进入人工复核"；同时生成复核台账 CSV。
"""
import argparse
import collections
import csv
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get('BANK_ROOT') or os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(BASE, 'scripts'))
from lib import load_level, load_bank, load_vocabulary  # noqa: E402
import stats as S  # noqa: E402

CJK = re.compile(r'[\u4e00-\u9fff]')
T = {4: 'àèìòùǜ', 3: 'ǎěǐǒǔǚ', 2: 'áéíóúǘ', 1: 'āēīōūǖ'}
LEX_PATH = os.path.join(BASE, 'deliver', '复核2026-11-25', 'strict', 'pinyin_lexicon.json')
TRUE_POLY = set('假干数空发长重行觉差教量便得地着了过乐的分种还扫背倒弹调难处相将没哪那')
# 「一」保持本调的词（词表读音 yī，不参与变调）
LEXICAL_ONE = {'第一', '万一'}
# 「不」读轻声的词（词表读音 bu）；A不A 疑问式另按前后同字判定
NEUTRAL_BU = {'差不多', '对不起', '来不及', '了不起', '受不了', '说不定', '用不着', '不得了',
              '不好意思', '看不起', '离不开', '是不是', '能不能'}


def tone(s):
    for k, v in T.items():
        if any(c in v for c in s):
            return k
    return 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--prev-bank', default=None, help='用于跨级重复比对，缺省为本级前一级')
    args = ap.parse_args()
    lv = args.level
    out = args.out or os.path.join(BASE, 'deliver', '准入_L%d' % lv)
    os.makedirs(out, exist_ok=True)

    lvl = load_level(lv)
    items = load_bank(os.path.join(BASE, 'banks', 'level%d' % lv, 'final.json'))
    cons = lvl['constraints']
    allowed = set(lvl['chars']['all'])
    gmap = {g['id']: g for g in lvl['grammar']}
    prefix = 'L%d-' % lv

    checks = []

    def add(sev, name, ok, detail=''):
        checks.append((sev, name, ok, detail))

    lo, hi = cons['bank_target_items']
    add('FAIL', '题量在区间内', lo <= len(items) <= hi, '%d 题（要求 %d–%d）' % (len(items), lo, hi))
    ids = [it['id'] for it in items]
    add('FAIL', '编号唯一且连续', ids == ['%s%03d' % (prefix, i) for i in range(1, len(items) + 1)],
        '首个 %s / 末个 %s' % (ids[0], ids[-1]))
    add('FAIL', 'level 一致', all(it['level'] == lv for it in items))
    add('FAIL', 'round 在 1–9', all(1 <= (it.get('round') or 0) <= 9 for it in items),
        '轮次 %s' % sorted({it.get('round') for it in items}))
    dup = [t for t, c in collections.Counter(it['text'] for it in items).items() if c > 1]
    add('FAIL', '文本无重复', not dup, '重复 %d 句' % len(dup))

    lens = [len(CJK.findall(it['text'])) for it in items]
    add('FAIL', '句长在区间内', all(cons['min_chars'] <= n <= cons['max_chars'] for n in lens),
        '最短 %d / 最长 %d（要求 %d–%d）' % (min(lens), max(lens), cons['min_chars'], cons['max_chars']))
    add('FAIL', '无字母数字', not any(re.search(r'[A-Za-z0-9]', it['text']) for it in items))
    add('FAIL', '句末标点合规', all(it['text'][-1] in '。？！' for it in items))

    bad_char = [(it['id'], c) for it in items for c in CJK.findall(it['text']) if c not in allowed]
    add('FAIL', '无超纲字', not bad_char, '越界 %d 处' % len(bad_char))

    mism = [it['id'] for it in items
            if len([t for t in re.split(r'[\s，。？！、；：]+', it['pinyin']) if t]) != len(CJK.findall(it['text']))]
    add('FAIL', '汉字与音节一一对应', not mism, '不符 %d 题' % len(mism))
    add('FAIL', '拼音带句末标点', all(it['pinyin'][-1:] in '。？！' for it in items),
        '缺标点 %d 题' % sum(1 for it in items if it['pinyin'][-1:] not in '。？！'))

    bad_sandhi = 0
    for it in items:
        chars = CJK.findall(it['text'])
        toks = [t for t in re.split(r'[\s，。？！、；：]+', it['pinyin']) if t]
        text = ''.join(chars)
        for i, (c, t) in enumerate(zip(chars, toks)):
            if c in '一不' and i + 1 < len(chars) and toks[i + 1]:
                if i >= 1 and chars[i - 1] + c in LEXICAL_ONE:
                    continue
                if c == '不' and t == 'bu' and (
                        text[i - 1:i + 2] in NEUTRAL_BU or
                        (i >= 1 and chars[i - 1] == chars[i + 1])):
                    continue
                nt = tone(toks[i + 1])
                if nt in (1, 2, 3, 4):
                    want = ('yí' if nt == 4 else 'yì') if c == '一' else ('bú' if nt == 4 else 'bù')
                    if t != want:
                        bad_sandhi += 1
    add('FAIL', '一/不变调正确', bad_sandhi == 0, '不符 %d 处' % bad_sandhi)

    # 词汇/汉字跟读题只承担覆盖任务，lib.py 本来就不要求它们绑语法点；
    # 这里必须用同一口径，否则纯词汇题会被误判成“空标注”。
    plain = [it for it in items if it.get('kind') in ('vocabulary', 'character')]
    empty = [it['id'] for it in items
             if not it.get('grammar') and it.get('kind') not in ('vocabulary', 'character')]
    add('FAIL', '无空标注', not empty,
        '空标 %d 题（词汇/汉字跟读 %d 题不要求语法点）' % (len(empty), len(plain)))
    bad_tag = []
    for it in items:
        for gid in it['grammar']:
            g = gmap.get(gid)
            p = (g or {}).get('pattern')
            if g is None:
                bad_tag.append((it['id'], gid, '不属于本级'))
            elif p and not re.search(p, it['text']):
                bad_tag.append((it['id'], gid, '未命中'))
    add('FAIL', '标注与句子相符', not bad_tag, '不符 %d 处' % len(bad_tag))

    s, _ = S.compute(lvl, items)
    add('FAIL', '字覆盖 100%', s['char']['coverage'] == 100.0, '%.1f%%' % s['char']['coverage'])
    add('FAIL', '词汇覆盖 100%', s['vocabulary']['coverage'] == 100.0, '%.1f%%' % s['vocabulary']['coverage'])
    add('FAIL', '语法点全覆盖', s['grammar']['coverage'] == 100.0, '%.1f%%' % s['grammar']['coverage'])

    if lv > 1:
        prev = args.prev_bank or os.path.join(BASE, 'banks', 'level%d' % (lv - 1), 'final.json')
        if os.path.exists(prev):
            t_prev = {it['text'] for it in load_bank(prev)}
            cross = [it['id'] for it in items if it['text'] in t_prev]
            add('FAIL', '无跨级重复', not cross, '与上一级重复 %d 题' % len(cross))

    norm = [re.sub(r'[^\u4e00-\u9fff]', '', it['text']) for it in items]
    near = 0
    for i in range(len(norm)):
        for j in range(i + 1, min(len(norm), i + 400)):
            if abs(len(norm[i]) - len(norm[j])) <= 2 and \
               difflib.SequenceMatcher(None, norm[i], norm[j]).quick_ratio() >= 0.85:
                near += 1
    add('WARN', '近似句比例', True, '%d 对（≥85%%）' % near)

    syl = lvl.get('syllables') or {}
    if syl.get('status') == 'official':
        add('WARN', '音节覆盖已声明', True,
            '%s/%s = %s%%' % (syl.get('covered'), syl.get('unique'), syl.get('coverage')))

    print('=' * 66)
    print('L%d 题库 · 人工复核准入检查' % lv)
    print('=' * 66)
    for sev, name, ok, detail in checks:
        mark = '通过' if ok else ('阻断' if sev == 'FAIL' else '提示')
        print('[%s] %-20s %s' % (mark, name, detail))
    fails = [c for c in checks if c[0] == 'FAIL' and not c[2]]
    warns = [c for c in checks if c[0] == 'WARN' and not c[2]]
    print('-' * 66)
    print('阻断项 %d，提示项 %d' % (len(fails), len(warns)))
    print('准入结论：%s' % ('可以进入人工复核' if not fails else '不可进入，需先修阻断项'))

    json.dump([{'severity': a, 'item': b, 'ok': c, 'detail': d} for a, b, c, d in checks],
              open(os.path.join(out, 'L%d_准入检查.json' % lv), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    amb, single = {}, {}
    if os.path.exists(LEX_PATH):
        lex = json.load(open(LEX_PATH, encoding='utf-8'))
        amb, single = lex['ambiguous'], lex['single']

    rows = []
    for it in items:
        chars = CJK.findall(it['text'])
        toks = [t for t in re.split(r'[\s，。？！、；：]+', it['pinyin']) if t]
        poly = ['%s(%s)' % (c, t) for c, t in zip(chars, toks)
                if c in TRUE_POLY and c in amb and t != single.get(c)]
        rows.append({'编号': it['id'], '正文': it['text'], '拼音': it['pinyin'],
                     '语法点': '、'.join(it['grammar']),
                     '必看多音字': ' '.join(poly) or '—',
                     '词表外词': '', '复核结论（合格/修改/剔除）': '', '精查结论': '', '备注': ''})
    with open(os.path.join(out, 'L%d_复核台账.csv' % lv), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('复核台账：%d 行 → %s' % (len(rows), os.path.join(out, 'L%d_复核台账.csv' % lv)))
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
