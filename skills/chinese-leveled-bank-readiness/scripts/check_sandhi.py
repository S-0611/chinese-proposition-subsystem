# -*- coding: utf-8 -*-
"""一/不 变调检查（带例外）。

规则：一 在四声前读 yí，在一二三声前读 yì；不 在四声前读 bú，其余读 bù。
例外（词表读音，不按变调硬改）：第一、万一 的「一」读本调 yī；不读轻声的词——差不多/对不起/来不及/了不起/受不了/说不定/看不起/离不开/是不是/能不能；A不A（如对不对）的「不」也是轻声。
改拼音时必须保留原字符串的标点与空格骨架，否则会丢句末标点。

用法：python check_sandhi.py --level 2 [--fix]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.environ.get('BANK_ROOT') or os.path.abspath(os.path.join(HERE, '..', '..', '..'))

CJK = re.compile(r'[\u4e00-\u9fff]')
T = {4: 'àèìòùǜ', 3: 'ǎěǐǒǔǚ', 2: 'áéíóúǘ', 1: 'āēīōūǖ'}
SEP = r'([\s，。？！、；：]+)'
# 「一」保持本调的词；「不」读轻声的词（依据国标词表读音）
LEXICAL_ONE = {'第一', '万一'}
NEUTRAL_BU = {'差不多', '对不起', '来不及', '了不起', '受不了', '说不定', '用不着', '不得了',
              '不好意思', '看不起', '离不开', '是不是', '能不能'}


def tone(s):
    for k, v in T.items():
        if any(c in v for c in s):
            return k
    return 5


def scan(items):
    bad = []
    for it in items:
        chars = CJK.findall(it['text'])
        toks = [t for t in re.split(SEP, it['pinyin']) if t and not re.fullmatch(SEP, t)]
        text = ''.join(chars)
        for i, (c, t) in enumerate(zip(chars, toks)):
            if c not in '一不' or i + 1 >= len(chars):
                continue
            if i >= 1 and chars[i - 1] + c in LEXICAL_ONE:
                continue
            if c == '不' and t == 'bu' and (
                    text[i - 1:i + 2] in NEUTRAL_BU or
                    (i >= 1 and chars[i - 1] == chars[i + 1])):
                continue
            nt = tone(toks[i + 1])
            if nt not in (1, 2, 3, 4):
                continue
            want = ('yí' if nt == 4 else 'yì') if c == '一' else ('bú' if nt == 4 else 'bù')
            if t != want:
                bad.append([it['id'], i, c, t, want])
    return bad


def rebuild(original, new_tokens):
    parts = re.split(SEP, original)
    idx, out = 0, []
    for p in parts:
        if not p:
            continue
        if re.fullmatch(SEP, p):
            out.append(p)
        else:
            out.append(new_tokens[idx] if idx < len(new_tokens) else p)
            idx += 1
    return ''.join(out)


if __name__ == '__main__':
    level = int(sys.argv[sys.argv.index('--level') + 1]) if '--level' in sys.argv else 2
    path = os.path.join(B, 'banks', 'level%d' % level, 'final.json')
    items = json.load(open(path, encoding='utf-8'))['items']
    bad = scan(items)
    print('L%d 一/不变调不符 %d 处' % (level, len(bad)))
    for b in bad:
        print('  ', b)
    if '--fix' in sys.argv and bad:
        byid = {}
        for iid, pos, c, cur, want in bad:
            byid.setdefault(iid, []).append((pos, want))
        for it in items:
            if it['id'] not in byid:
                continue
            toks = [t for t in re.split(SEP, it['pinyin']) if t and not re.fullmatch(SEP, t)]
            for pos, want in byid[it['id']]:
                toks[pos] = want
            it['pinyin'] = rebuild(it['pinyin'], toks)
        json.dump({'items': items}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('已修正 %d 处（标点骨架保留）' % len(bad))
