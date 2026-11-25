# -*- coding: utf-8 -*-
"""词表反向检查：题目用的词是否都在该级（累计）词表内。

stats.py 只做单向覆盖（词表词是否都出现），本脚本补反向。
正向＋逆向最大匹配，两侧都判为表外的片段才计入，以消除切分歧义。

用法：python check_vocab_oov.py <level>
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.environ.get('BANK_ROOT') or os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(B, 'scripts'))
from lib import load_level, load_bank, load_vocabulary  # noqa: E402

CJK = re.compile(r'[\u4e00-\u9fff]')


def cumulative_words(level):
    words = set()
    for lv in range(1, level + 1):
        vd = load_vocabulary(load_level(lv)) or {}
        words |= {x['word'] for x in (vd.get('items') or []) if x.get('word')}
    return words


def run(text, words, maxlen, reverse=False):
    s = ''.join(CJK.findall(text))
    out, i = [], (len(s) if reverse else 0)
    while (i > 0) if reverse else (i < len(s)):
        hit = False
        for L in range(min(maxlen, len(s) if reverse else len(s) - i), 0, -1):
            frag = s[i - L:i] if reverse else s[i:i + L]
            if frag in words:
                out.append(frag)
                i -= L if reverse else -L
                hit = True
                break
        if not hit:
            if reverse:
                i -= 1
                out.append(s[i])
            else:
                out.append(s[i])
                i += 1
    return out[::-1] if reverse else out


if __name__ == '__main__':
    level = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    words = cumulative_words(level)
    maxlen = max(len(w) for w in words)
    items = load_bank(os.path.join(B, 'banks', 'level%d' % level, 'final.json'))
    rows, flags = [], collections.Counter()
    for it in items:
        a = {t for t in run(it['text'], words, maxlen) if t not in words}
        b = {t for t in run(it['text'], words, maxlen, reverse=True) if t not in words}
        both = a & b
        if both:
            flags.update(both)
            rows.append((it['id'], it['text'], '、'.join(sorted(both))))
    print('L%d：%d 题，累计词表 %d 条' % (level, len(items), len(words)))
    print('双向都判为表外：%d 题（%.1f%%），片段 %d 种'
          % (len(rows), 100 * len(rows) / len(items), len(flags)))
    print('高频：', flags.most_common(12))
    for r in rows[:10]:
        print(' ', r[0], r[1], '|', r[2])
