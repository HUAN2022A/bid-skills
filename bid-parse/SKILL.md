---
name: bid-parse
description: 解析招标文件（pdf/docx），提取技术标书撰写所需的全部依据：评分办法逐条拆解并打技术/商务/价格分卷标签、★号技术参数、废标条款、技术卷格式要求。适用于用户给出招标文件要求开始做标书、解析评分办法、提取技术需求的场景。bid-* 家族第一阶段，输出 {项目}/tender-analysis.yaml，供 bid-outline 消费。PDF 用 pdfplumber 提取（表格结构还原）。
---

# bid-parse：解析招标文件

纯提取阶段：把几百页招标文件压缩成一份可核对、可被下游消费的 `tender-analysis.yaml`。**不做任何设计决策**（那是 bid-outline 的事），不猜测、不改写。

## 输入

用户给出招标文件路径（文件或目录——正文 + 附件可能是多个文件）。若未给出且当前目录只有一个明显的招标文件，可直接使用并向用户说明。

## 流程

### 1. 建项目工作区

从文件名或文档首页提取项目名称，创建 `{项目名}/` 工作区（目录名去掉 `\/:*?"<>|` 等非法字符，可用中文）。

### 2. 提取全文

- **pdf（首选 pdfplumber，保留表格结构）**：
  ```
  python <本skill目录>/extract_pdf.py 招标文件.pdf -o {项目名}/tender-fulltext.txt
  ```
  输出与 docx 提取同格式：每页 `=== 第 N 页 ===` 标记（供 location 字段回溯），表格还原为 `[表格]` 块、单元格 `|` 分隔——评分办法、参数表的行列归属精确可读（pypdf 纯文本流会把表格读散，仅作 pdfplumber 不可用时的兜底）。
- docx：优先 pandoc 转 markdown，或 python-docx 提取（`extract_docx.py`）。
- 上述工具不可用时，加载 document-skills:pdf / document-skills:docx 完成提取。
- **扫描版检查**：脚本自带告警（平均每页少于 100 字符）；pdfplumber 对无表格线的表格还原降级（`find_tables` 依赖线框），发现漏表时对该页用 `page.extract_table()` 调参或提示人工核对。
- 附件里的「技术标格式/模板」文件同样记录路径（写入 `template_file`），有条件就提取其格式说明。

### 3. 定位关键章节

在全文里搜以下关键词，读上下文确认章节边界：

- 评分依据：`评标办法`、`评分办法`、`评分标准`、`细则`
- 技术需求：`采购需求`、`技术需求`、`服务要求`、`委托人要求`、需求章节（常见第三/五章）
- 废标：`废标`、`无效投标`、`否决投标`、`视为`
- 资格与门槛：`资格要求`、`业绩要求`、`职称`、`资质要求`、`联合体`、`最高投标限价`、`拦标价`、`保证金`（限价/保证金/资格条件最容易漏，金标准测试的实际教训）
- 商务要点：`付款`、`支付`、`违约金`、`转包`、`分包`、`质保`
- 格式：`投标文件格式`、`编制要求`、`密封`、`份数`、`目录`
- 元数据：`项目名称`、`招标编号`、`开标时间`

### 4. 提取为 YAML

按下方 schema 写 `{项目名}/tender-analysis.yaml`。提取规则：

- **逐字引用**：`criteria_original` / `requirement_original` / `clause_original` 必须原文照抄（保留 ★▲ 和序号），禁止改写、总结、转述。这是下游逐点响应的对齐基准。
- **分卷标签**：每条评分项打 `category`。评分办法自带分组（如"技术分 40 分"）按分组；无分组按内容判断；判断不了打 `其他` 并加 `note: 待核实分卷`。
- **商务/价格/资质项浅提取**：只留 id/category/item/score/criteria_original，够 bid-check 列人工清单即可，不深加工。
- **不确定就标记**：任何拿不准的值写 `[待核实]`，不猜。

### 5. 校验

```
python <本skill目录>/validate_tender.py -f {项目名}/tender-analysis.yaml
```

校验不过就修到过。**分值加总 ≠ total 时回原文重新核对**，禁止改数字凑平。

### 6. 汇报并生成分析报告

先跑校验，再凝练报告数据，最后渲染并输出统计摘要。

**凝练层（精华中的精华）**：在工作区写 `report-data.yaml`，逐条从 `tender-analysis.yaml` 凝练。规则：

- **要点分号并列**，一条 = 3-6 个要点，每个要点一句话
- **硬指标全保留**：数字、金额、时间、成功率、分值档位一个不能丢
- **只写招标文件里有的内容**，不评价、不预测、不编造
- 策略性字段（备注列、预估得分、竞品、结论、销售/售前经理）**留空**，渲染为 `[待补：人工填写]`
- 同一要求出现在多处章节时（如违约条款在合同章和考核章各有一套），**两套都要**，并注明双轨

**渲染**（严格按人工分析模板版式：分节标题行、行名、合并单元格与模板一致）：

```
python <本skill目录>/generate_report.py -d {项目名}/report-data.yaml -o {项目名}/招标项目分析报告.docx
```

报告可重复生成（会覆盖），人工策略内容填在导出副本里。

统计摘要内容：

- 评分项总数与分值分布：技术 X 项/Y 分、商务 …、价格 …
- ★号技术参数 N 条、废标条款 M 条（其中需人工处理 K 条）
- 格式要求 L 条、技术标模板有/无
- `[待核实]` 清单
- 报告已生成：`{项目名}/招标项目分析报告.docx`，其中 `[待补]` 字段清单（需人工填写的策略信息）

然后提示下一阶段：`/bid-outline`。

## 输出 schema

```yaml
project: 项目名称
tender_no: 招标编号
source_files: [原文件路径列表]
parsed_at: 日期

scoring:
  # 两种模式二选一：
  # 1) 总分制：total: 100，所有 items 分值加总须等于 total
  # 2) 加权制（常见于央企：各分卷按100分制评分后加权合成）：
  #    weights: {商务: 0.10, 技术: 0.70, 价格: 0.20}   # 加总须为 1.0
  #    category_totals: {商务: 100, 技术: 100, 价格: 100}  # 各卷总分，默认 100
  total: 100            # 总分制时使用
  items:
    - id: S1
      category: 技术     # 技术|商务|价格|资质|其他
      item: 技术方案
      score: 10
      criteria_original: |  # 评分标准原文，逐字
      location: 第三章 评标办法 一、(2)  # 章节定位 + 页码
      response_hint: 一句话说明在技术卷哪里、用什么响应  # 仅技术项
      note: 可选备注（如商务项同时约束技术卷编写质量）

tech_requirements:
  - id: T1
    star: true          # ★/▲ 号条款
    requirement_original: |
    location: ...

qualification:          # 资格要求，浅提取（第一章招标公告）
  - id: Q1
    requirement_original: |
    location: ...
    note: 技术卷第（五）章能力说明需引用的资格门槛

commercial_notes:       # 付款/违约/质保等商务要点，浅提取，人工处理
  - id: C1
    requirement_original: |
    location: ...

disqualification:
  - id: D1
    clause_original: |
    location: ...
    applies_to: 技术卷   # 技术卷|全局
    manual: false        # true = 商务/资质类，人工处理

format_requirements:    # 技术卷相关格式（字体、份数、密封、页码、目录等）
  - id: F1
    requirement_original: |
    location: ...
template_file: null     # 附件中技术标模板路径，无则 null

structure_requirements: # 招标文件明确要求技术文件包含的内容
  - id: R1
    requirement_original: |
    location: ...
```

## 边界

- 只提取，不评价、不给建议。
- 商务/价格卷内容不深加工（家族 scope 只做技术卷）。
- 本阶段纯本地，不联网。
