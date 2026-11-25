# -*- coding: utf-8 -*-
"""阶段 1：把国标一致性复核结果写进 data/levels/level1.json。

- 备份到 data/levels/level1.json.bak_20261125_before_readiness（已存在则不覆盖，直接退出）
- 字表：chars.verified
- 词表：vocabulary.verification（只核数量与来源，明确“尚未逐词比对”）
- 语法：grammar[i].standard_id = 【一01】…【一48】
- 音节：syllables（官方 4.1 表 269 条 + 实测覆盖）

用法：
    python deliver/准入_L1/apply_stage1.py --dry-run   # 只打印将要写的内容
    python deliver/准入_L1/apply_stage1.py --apply
"""
import argparse
import json
import os
import shutil

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(BASE, 'data', 'levels', 'level1.json')
SYL = os.path.join(BASE, 'deliver', '准入_L1', '一级音节表_官方.json')
BAK = CFG + '.bak_20261125_before_readiness'
DATE = '2026-11-25'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    cfg = json.load(open(CFG, encoding='utf-8'))
    syl_meta = json.load(open(SYL, encoding='utf-8'))
    table = syl_meta['table']
    assert len(table) == 269 and len(set(table)) == 269, (len(table), len(set(table)))

    # ---- 字节覆盖率实测（与 gate.py / syllable_coverage.py 同口径：题库 pinyin 按标点切分后的音节）----
    import re
    bank = json.load(open(os.path.join(BASE, 'banks', 'level1', 'final.json'), encoding='utf-8'))['items']
    SEP = r'[\s，。？！、；：]+'
    got = set()
    for it in bank:
        for tok in re.split(SEP, it['pinyin']):
            if tok:
                got.add(tok)
    covered = sorted(set(table) & got)
    missing = sorted(set(table) - got)

    cfg['chars']['verified'] = {
        'against': 'GF 0025—2021 5.1 一级汉字表（内页 15—17 / PDF 21—23）逐格识别结果 work/chars_levels.json 第 1 级',
        'method': '逐字集合比对（双向差集），并核对数量',
        'result': '300/300 一致，无多出、无缺失、无重复；配置为拼音序，标准页序不同，不计为差异',
        'date': DATE,
    }
    v = cfg.setdefault('vocabulary', {})
    v['verification'] = {
        'against': 'GF 0025—2021 词汇表 一级：500 个词条',
        'method': '只核条目数与同形异音重复，未与标准 PDF 逐词比对',
        'result': '条目 500 / 词形 497；重复 3 条：地（de/dì）、干（gān/gàn）、还（hái/huán），'
                  '为同形异音同形多义，属标准本身的收词方式，不是漏词',
        'status': '尚未逐词比对',
        'date': DATE,
    }
    for i, g in enumerate(cfg['grammar'], 1):
        g['standard_id'] = '【一%02d】' % i

    syl = {
        'status': 'official',
        'standard': syl_meta['standard'],
        'source': syl_meta['source'],
        'entries': len(table),
        'unique': len(set(table)),
        'duplicates_to_verify': {},
        'table': table,
        'covered': len(covered),
        'coverage': round(100.0 * len(covered) / len(table), 1),
        'missing': missing,
        'missing_note': '6 个缺口全部为同一音节的不同声调/轻声变体，无音节整体缺失',
        'missing_vocab_support': {
            'dé': ['得到'],
            'guò': ['过'],
            'huán': ['还（huán）'],
            'jiāo': ['教（jiāo）'],
            'qīng': [],
            'zǐ': [],
        },
        'acceptance': '覆盖率 %d/%d = %.1f%%；整音节缺失 0；dé/guò/huán/jiāo 有词表依据，'
                      '阶段 2 先查题库是否已有该读音可修正；qīng、zǐ 无词表依据，列为验收条款不硬补。'
                      % (len(covered), len(table), 100.0 * len(covered) / len(table)),
        'date': DATE,
    }
    cfg['syllables'] = syl

    note = cfg.get('source_note', '')
    if '2026-11-25' not in note:
        cfg['source_note'] = note + ' ｜ 2026-11-25：完成国标一致性复核（字表/词表/语法编号/官方音节表），详见 deliver/准入_L1/。'

    if not args.apply:
        print('[dry-run] 将写入：chars.verified / vocabulary.verification / grammar.standard_id / syllables')
        print('[dry-run] 音节覆盖 %d/%d = %.1f%%，缺口 %s' % (len(covered), len(table), syl['coverage'], missing))
        return

    if os.path.exists(BAK):
        raise SystemExit('备份已存在，拒绝覆盖：%s' % BAK)
    shutil.copy2(CFG, BAK)
    json.dump(cfg, open(CFG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写入 %s' % CFG)
    print('备份 %s' % BAK)


if __name__ == '__main__':
    main()
