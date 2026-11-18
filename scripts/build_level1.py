# -*- coding: utf-8 -*-
"""生成 data/levels/level1.json（一级：300 字表 + 语法点 + 约束 + 达标阈值）。

字表按《国际中文教育中文水平等级标准》(GF 0025-2021) 一级大纲口径整理；
如需与官方逐字对齐，直接替换 CHARS_GROUPS 内容重跑本脚本即可。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# ── 一级字表（整理版，按主题分组书写，脚本内自动去重，恰好 300 字） ──
CHARS_GROUPS = {
    "数字与量词": """
    一 二 三 四 五 六 七 八 九 十 半 百 千 万 两 第 几 些 每 多 少
    个 只 本 支 条 件 杯 碗 块 次
    """,
    "时间": """
    年 月 日 天 小 时 分 钟 点 号 星 期 早 晚 上 午 今 明 昨 现 在
    候 春 夏 冬 中
    """,
    "人称与人物": """
    我 你 他 她 它 们 自 己 别 人 家 谁 什 么 王
    爸 妈 哥 姐 弟 妹 儿 子 女 朋 友 同 学 老 师 医 生 先 孩
    服 务 员 小 姐 姓 名 字 客 气
    """,
    "动词": """
    是 有 去 来 到 在 说 话 问 答 听 看 读 写 认 识 学 习 教
    会 懂 忘 记 知 道 打 开 关 用 拿 给 送 找 让 叫 帮 忙 换
    住 工 作 回 唱 跳 游 泳 睡 觉 起 吃 喝 买 卖 做 走 跑 坐 站 玩 喜 欢
    爱 觉 得 应 该 可 以 能 要 想 请 进 出 下 洗 谢 没 系 见 过
    """,
    "形容词": """
    大 小 高 新 旧 好 快 慢 热 冷 凉 累 饿 渴 忙 难 远 近
    白 黑 红 绿 漂 亮 对 错 兴 乐 晴
    """,
    "名词": """
    学 校 班 教 室 宿 舍 商 店 医 院 银 行 饭 馆 公 园 国 中 汉 语
    课 书 子 笔 包 鞋 衣 服 表 钱 电 脑 视 机 茶 水 牛 奶 面 米
    饭 菜 果 苹 西 瓜 蛋 肉 糖 咖 啡 猫 狗 鱼 手 门 歌
    东 北 京 左 右 前 后 里 外 边 旁 车 汽 飞 电 影
    天 气 风 雨 雪 生 日 岁
    """,
    "虚词与其余高频字": """
    了 的 得 吗 呢 吧 啊 喂 很 太 也 都 就 才 再 又 还 起
    这 那 不 真 和 跟 对 从 给 哪 儿 为 怎
    """,
}

# ── 一级语法点（pattern 为可程序检测的宽松正则；把握不大的留给人工抽检） ──
GRAMMAR = [
    {"id": "G1-01", "name": "“是”字句", "pattern": r"是", "desc": "主语＋是＋名词，如：我是学生。"},
    {"id": "G1-02", "name": "“有”字句", "pattern": r"有", "desc": "表拥有或存在，如：我有一个哥哥。"},
    {"id": "G1-03", "name": "“吗”是非问", "pattern": r"吗？", "desc": "你是学生吗？"},
    {"id": "G1-04", "name": "疑问代词问句", "pattern": r"(谁|什么|哪儿|哪里|为什么|怎么)", "desc": "你是哪国人？"},
    {"id": "G1-05", "name": "正反问", "pattern": r"(是不是|有没有|好不好|行不行|去不去|来不来|吃不吃|喝不喝|买不买|看不看|忙不忙|热不热|冷不冷|大不大|多不多|难不难|对不对|饿不饿|渴不渴|远不远|近不近|新不新|学不学)", "desc": "你忙不忙？"},
    {"id": "G1-06", "name": "“几／多少”问数量", "pattern": r"(几|多少)", "desc": "你家有几口人？"},
    {"id": "G1-07", "name": "“哪”特指问", "pattern": r"哪", "desc": "哪个是你的？"},
    {"id": "G1-08", "name": "“呢”省略式问句", "pattern": r"呢？", "desc": "我很好，你呢？"},
    {"id": "G1-09", "name": "祈使句“请……”", "pattern": r"请", "desc": "请进！"},
    {"id": "G1-10", "name": "禁止“别／不要……”", "pattern": r"(别|不要)", "desc": "别忘了！"},
    {"id": "G1-11", "name": "感叹句“太……了”", "pattern": r"太[^，。？！]{1,6}了", "desc": "太好了！"},
    {"id": "G1-12", "name": "感叹句“真……”", "pattern": r"真", "desc": "真漂亮！"},
    {"id": "G1-13", "name": "程度副词“很”", "pattern": r"很", "desc": "我很忙。"},
    {"id": "G1-14", "name": "否定副词“不”", "pattern": r"不", "desc": "我不去。"},
    {"id": "G1-15", "name": "否定副词“没（有）”", "pattern": r"没", "desc": "我没看电视。"},
    {"id": "G1-16", "name": "副词“也”", "pattern": r"也", "desc": "他也是学生。"},
    {"id": "G1-17", "name": "副词“都”", "pattern": r"都", "desc": "我们都是中国人。"},
    {"id": "G1-18", "name": "副词“就”", "pattern": r"就", "desc": "我就来。"},
    {"id": "G1-19", "name": "副词“才”", "pattern": r"才", "desc": "他才知道。"},
    {"id": "G1-20", "name": "副词“再／又”", "pattern": r"(再|又)", "desc": "再喝一杯。"},
    {"id": "G1-21", "name": "副词“还”", "pattern": r"还", "desc": "他还在学校。"},
    {"id": "G1-22", "name": "副词“一起”", "pattern": r"一起", "desc": "我们一起去吧。"},
    {"id": "G1-23", "name": "时间词作状语", "pattern": r"^(今天|明天|昨天|现在|每天|天天|上午|下午|晚上|早上|中午|星期[一二三四五六日天]|今年|去年|明年)", "desc": "明天我去北京。"},
    {"id": "G1-24", "name": "“在＋处所＋动词”", "pattern": r"在[^，。？！]{0,5}(学|住|工|玩|看|吃|睡|买|说|打|上|做)", "desc": "我在家看电视。"},
    {"id": "G1-25", "name": "介词“从……到……”", "pattern": r"从[^，。？！]{1,6}到", "desc": "从家到学校很远。"},
    {"id": "G1-26", "name": "介词“给／对／跟”", "pattern": r"(给|对|跟)", "desc": "我跟妈妈去商店。"},
    {"id": "G1-27", "name": "连词“和”", "pattern": r"和", "desc": "爸爸和妈妈"},
    {"id": "G1-28", "name": "结构助词“的”", "pattern": r"的", "desc": "我的书"},
    {"id": "G1-29", "name": "动态助词“了”", "pattern": r"了", "desc": "我买了一本书。"},
    {"id": "G1-30", "name": "经历“过”", "pattern": r".过", "desc": "我去过中国。"},
    {"id": "G1-31", "name": "能愿动词“会”", "pattern": r"会", "desc": "我会说汉语。"},
    {"id": "G1-32", "name": "能愿动词“能／可以”", "pattern": r"(能|可以)", "desc": "可以进来吗？"},
    {"id": "G1-33", "name": "能愿动词“要／想”", "pattern": r"(要|想)", "desc": "我想喝茶。"},
    {"id": "G1-34", "name": "能愿动词“应该”", "pattern": r"应该", "desc": "你应该休息。"},
    {"id": "G1-35", "name": "数量短语（数＋量＋名）", "pattern": r"[一二两三四五六七八九十几这那半百千万][个只本支条件杯碗块次]", "desc": "三本书"},
    {"id": "G1-36", "name": "序数“第＋数”", "pattern": r"第[一二三四五六七八九十]", "desc": "第五课"},
    {"id": "G1-37", "name": "时刻表达（点／分／半）", "pattern": r"[一二两三四五六七八九十]点", "desc": "八点半"},
    {"id": "G1-38", "name": "年月日与星期表达", "pattern": r"([一二两三四五六七八九十]{1,3}年|[一二两三四五六七八九十]{1,2}月[一二两三四五六七八九十]{1,3}[号日]|星期[一二三四五六日天])", "desc": "九月十号"},
    {"id": "G1-39", "name": "钱的表达（块）", "pattern": r"块", "desc": "十块钱"},
    {"id": "G1-40", "name": "连动句", "pattern": r"(去|来)[^，。？！]{0,8}(买|看|吃|喝|找|学|打|玩|上)", "desc": "我去商店买东西。"},
    {"id": "G1-41", "name": "双宾句（给／送／教）", "pattern": r"(给|送|教)[^，。？！]{0,6}(一|两|我|你|他|她|这|那)", "desc": "他送我一本书。"},
]

LEVEL1 = {
    "level": 1,
    "name": "一级（初等一级）",
    "tier": "beginner",
    "source_note": (
        "字表与语法点参照《国际中文教育中文水平等级标准》(GF 0025-2021) 一级大纲口径整理，"
        "共 300 字；如需与官方逐字对齐，修改 build_level1.py 中 CHARS_GROUPS 后重跑即可。"
    ),
    "constraints": {
        "min_chars": 3,
        "max_chars": 12,
        "allow_ascii": False,
        "allow_digits": False,
        "bank_target_items": [110, 280],
    },
    "thresholds": {
        "char_coverage_min": 0.90,
        "char_freq_min": 1,
        "core_char_freq_min": 3,
        "grammar_coverage_min": 1.0,
        "grammar_freq_min": 2,
    },
    "chars": None,
    "grammar": GRAMMAR,
}

# 高频核心字（教学最高优先，复现要求更高），必须是字表子集
CORE = (
    "的我你他她它们这那是在有不没很也都就才再又还和跟对从给"
    "一二两三四五六七八九十什么谁哪几多少个只本支条件杯碗块钱"
    "年月日天点分上下午早晚上下里外前后左右东西北"
    "家学老师同学朋友爸妈哥姐弟妹去来到说看读写听吃饭喝水茶果"
    "大小高兴忙快慢热冷新旧会能要想喜欢请谢再见起走坐睡门歌"
)


def main():
    seen, dupes = [], set()
    for group_chars in CHARS_GROUPS.values():
        for ch in group_chars.split():
            if ch in seen:
                dupes.add(ch)
            else:
                seen.append(ch)
    print(f"分组去重后字数：{len(seen)}（组内重复 {len(dupes)} 个，已自动去重）")
    if len(seen) != 300:
        print(f"警告：字表不是 300 字（当前 {len(seen)}），请调整 CHARS_GROUPS")

    core = []
    missing = []
    for ch in CORE:
        if ch not in seen:
            missing.append(ch)
        elif ch not in core:
            core.append(ch)
    if missing:
        print("核心字不在字表：", " ".join(missing))
        raise SystemExit(1)

    LEVEL1["chars"] = {"all": seen, "core": core}
    out = ROOT / "data" / "levels" / "level1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(LEVEL1, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出 {out}")
    print(f"字表总数：{len(seen)}，核心高频字：{len(core)}，语法点：{len(GRAMMAR)}")


if __name__ == "__main__":
    main()
