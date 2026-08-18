---
name: bid-outline
description: 根据 tender-analysis.yaml 设计技术标书应答大纲：章节树挂评分点映射、目标字数、素材引用，输出 {项目}/bid-outline.yaml 供人工确认。适用于招标文件已解析（bid-parse 已跑）、需要规划技术文件章节结构、把评分点分配到章节的场景。bid-* 家族第二阶段，大纲未经确认不得进入 bid-draft。
---

# bid-outline：应答大纲设计

把 `tender-analysis.yaml` 变成一份可拍板的章节树。**这是设计决策阶段，不是提取**——章节怎么切、评分点往哪挂、字数怎么分，都需要判断。产出 `bid-outline.yaml`，是全流程**唯一的人工确认点**。

## 输入

当前目录（或用户指定目录）下的 `tender-analysis.yaml`（bid-parse 产物）。找不到就提示先跑 `/bid-parse`。

## 大纲设计规则

1. **骨架 = 招标文件规定的技术文件结构**（`structure_requirements`），顺序和章名原样保留——格式评分（如 S4"按格式、顺序编制"）直接扣分，不允许自由发挥章节顺序。
2. **评分点必须全挂**：每个 `category: 技术` 的评分项至少挂到一个章节；`structure_requirements` 里有 `maps_to_scoring` 的优先按它挂。挂不上的评分项 = 设计缺陷，必须加章或在汇报中说明。
3. **技术需求分配到章节**：`tech_requirements` 每条挂到响应它的章节（一条可挂多章），起草时逐条响应。
4. **目标字数按分值加权**：技术评分项分值占比决定篇幅占比；无分值的必写章（建议、协助条件、承诺书）给固定小份额。金标准参考：95MB 中标技术文件约 142 个标题、正文约 15-20 万字，其中"技术方案及说明"（25 分）约占 40%。
5. **素材引用**：需要公司事实的章节（业绩、人员、设备、获奖）在 `materials` 里列出素材库检索关键词，**不引用素材库不存在的事实**。
6. **章节编号稳定**：`id` 用 `1`、`1.1`、`1.1.1` 形式，一旦确认不再变——关键技术响应表要引用章节号（见 tender-analysis 的 F7 类格式要求）。
7. **尾部固定章节**：关键技术响应表、技术偏离表（若 tender-analysis 显示需要）必须在大纲里占位。
8. 允许在骨架章下自由设计子章节（这是"优于招标要求"的发挥空间），但子章节必须服务于该章挂的评分点。

## 流程

### 1. 读输入

读 `tender-analysis.yaml`：structure_requirements（骨架）、scoring 中技术项（分值权重）、tech_requirements（逐条响应清单）、format_requirements（格式约束）、qualification（能力章节要引用的资格门槛）。

### 2. 检查素材库

若 `~/Documents/company-knowledge/` 存在，浏览其索引，把可用素材（案例卡、简历卡、资质）的标识记入相关章节的 `materials`。不存在则在汇报中提示：能力/业绩章节将标记 `[待补]`。

### 3. 设计章节树

按上述规则设计，写 `{项目}/bid-outline.yaml`（schema 见下）。

### 4. 校验

```
python <本skill目录>/validate_outline.py -o {项目}/bid-outline.yaml -t {项目名}/tender-analysis.yaml
```

校验不过就修到过。

### 5. 汇报并等待确认（唯一人工确认点）

向用户展示：

- 章节树（含每章挂的评分点、目标字数）
- 评分点覆盖情况：每个技术评分项 → 挂在哪章
- 素材缺口：哪些章节需要素材库没有的内容（将标 `[待补]`）
- 与招标文件结构要求的偏差说明（应为零偏差，有则说明理由）

**明确告诉用户：确认后才可运行 `/bid-draft`。** 用户提出修改就改完重新校验、重新展示。

## 输出 schema

```yaml
project: 项目名称
based_on: tender-analysis.yaml
created_at: 日期
status: draft        # draft | confirmed（用户确认后改 confirmed）

target_total_words: 180000   # 全卷目标字数

chapters:
  - id: "1"
    title: 对本招标项目的理解和认识
    source_req: R1              # 对应的 structure_requirements id，骨架章必填
    scoring: [S5]               # 本章响应的评分项 id
    tech_reqs: []               # 本章响应的 tech_requirements id
    target_words: 25000
    materials: []               # 素材库引用（案例卡/简历卡 id 或检索关键词）
    notes: 写作要点提示（可选）
    children:
      - id: "1.1"
        title: 项目基本概况认知
        target_words: 3000
        notes: ...
```

## 边界

- 只设计结构，不写正文（那是 bid-draft）。
- 章节顺序/章名不动招标文件规定的骨架；发挥空间在子章节。
- 公司事实只引用素材库，缺口标 `[待补]`，不编造。
- 大纲未确认（status 不是 confirmed）时，bid-draft 应拒绝开写。
