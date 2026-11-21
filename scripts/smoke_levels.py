# -*- coding: utf-8 -*-
"""等级配置冒烟检查：确认 2—9 级配置能被 pipeline 正常读取、校验、统计。

不校验内容质量，只验证“接入题库时不会崩”。用每级字表前若干字拼 4 字短句，
故意不追求语义；语法点清单待补的等级会跳过语法校验并输出说明。

用法：
    python scripts/smoke_levels.py
退出码：0 全部等级可跑；1 有等级异常。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stats as stats_mod
from lib import load_level, validate_bank

sys.stdout.reconfigure(encoding="utf-8")


def make_items(chars):
    pool = list(chars) or list("山水风雨花鸟鱼虫天地人和日月星辰")
    items = []
    for i in range(0, min(len(pool) - 3, 24), 4):
        text = "".join(pool[i:i + 4]) + "。"
        items.append({"id": f"SMOKE-{i // 4 + 1:02d}", "text": text, "grammar": []})
    return items


def main():
    failed = []
    for n in range(2, 10):
        try:
            level = load_level(n)
            items = make_items((level.get("chars") or {}).get("all") or [])
            clean, results, _, _ = validate_bank(items, level)
            stats, plan = stats_mod.compute(level, items)
            notes = "；".join(stats.get("notes") or [])
            print(f"L{n}: 配置可读，题 {len(items)} 合格 {len(clean)}，"
                  f"结论 {stats['verdict']}，未达标项 {len(stats['failed_checks'])}"
                  + (f"，说明：{notes}" if notes else ""))
        except Exception as e:  # noqa: BLE001
            failed.append(n)
            print(f"L{n}: FAIL {type(e).__name__}: {e}")
    print(f"\n结果：{'全部等级可跑' if not failed else '异常等级 ' + str(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
