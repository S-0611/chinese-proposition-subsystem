# 中文发音智能诊断与评价系统——命题子系统

## 一、项目简介

命题子系统负责为中文发音智能诊断与评价系统建设分级跟读题库，并向学生子系统提供题目抽取服务。

## 二、主要职责

本子系统负责：

- 分级跟读题库建设
- 题目出题
- 题目校验
- 题库统计
- 根据缺口补题
- 合格题目入库
- 按等级抽题
- 按历史覆盖程度推荐抽题

本子系统不负责：

- 学生注册
- 学生录音
- 语音识别
- 发音评分
- 偏误诊断
- 管理端录音导出

## 三、命题流水线

```text
出题
→ 校验
→ 统计
→ 补题
→ 再次校验和统计
→ 达标
→ 入库
→ 抽题
```

只有通过校验且统计达标的题目，才可以正式入库并提供给学生端使用。

## 四、当前进度

- 已完成一级题库基础数据整理
- 已有题库校验脚本
- 已有题库统计脚本
- 已有一级题库校验和统计报告
- 已建立题库、数据、脚本和报告目录
- 已完成 SQLite 数据库与题目表（backend/bank.db，256 题已入库）
- 已完成 FastAPI 查询/校验/统计/发布/抽题接口（详见 docs/接口说明初稿.md）
- 已完成按等级抽题与按覆盖程度抽题（权重 `w = max(0, C - rec_count)`）
- 正在开发命题人员端网页
- 正在准备与学生端和管理端联调

## 五、目录结构

```text
data/       等级配置、字表和语法点配置
banks/      各等级题库文件
scripts/    出题、校验、统计和流水线脚本
reports/    校验报告、统计报告和补题计划
docs/       项目说明、分工和联调文档
backend/    后端和数据库代码
frontend/   命题人员端网页代码
```

## 六、一级题库

当前已有一级题库，主要文件包括：

```text
banks/level1/final.json
data/levels/level1.json
reports/level1/
```

一级题库需要满足：

- 题目字段完整
- 文本和逐字拼音对应
- 无重复编号
- 无重复文本
- 字表范围符合要求
- 语法点标注与句子一致
- 校验不合格数量为零
- 统计指标达到要求

## 七、题目字段

题目数据主要包含：

```text
id                 题目唯一编号
level              题目等级
text               题目文本
tokens             汉字和逐字拼音
grammar            语法点编号
status             题目状态
rec_count          有效录音数量
last_selected_at   最近抽取时间
```

示例：

```json
{
  "id": "L1-001",
  "level": 1,
  "text": "我姓王，你姓什么？",
  "tokens": [
    {"c": "我", "py": "wǒ"},
    {"c": "姓", "py": "xìng"}
  ],
  "grammar": ["G1-04"],
  "status": "published",
  "rec_count": 0,
  "last_selected_at": null
}
```

## 八、运行一级题库流水线

在项目根目录执行：

```powershell
python scripts/pipeline.py --level 1 --bank banks/level1/final.json --tag check
```

也可以分别执行：

```powershell
python scripts/validate.py --level 1 --bank banks/level1/final.json --tag check
python scripts/stats.py --level 1 --bank banks/level1/final.json --tag check
```

## 九、三人分工

- 谷财佾：数据、题库、校验、统计和人工抽检
- 李勃霖：后端、数据库和题目抽取接口
- 何思颖：前端、联调、文档和进度统筹

## 十、协作流程

每天开始工作前：

```text
Fetch origin
→ Pull origin
```

完成修改后：

```text
Commit
→ Push origin
```

提交信息应说明本次完成的具体内容。
