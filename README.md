# bid-skills — 技术标书写作 skill 家族

一套用于编写**技术标书（技术文件卷）**的 AI 编程助手 skill 集合。输入一份招标文件（docx/pdf），输出一份逐点响应评分标准、有真实公司素材支撑、排版规范的 `技术文件.docx` 终稿。

核心理念：**标书 = 逐点响应评分标准 + 真实素材支撑**。评分点对照表是贯穿全流程的中枢契约——解析阶段从招标文件拆出评分点，大纲阶段挂到每章，起草阶段逐点响应，检查阶段机器核对覆盖率，没有一处评分点能被静默漏掉。

采用通用 `SKILL.md` 格式（YAML frontmatter + Markdown 正文），**与平台无关**：任何支持 SKILL.md 的 AI 编程工具（ZCode、Claude Code、Codex CLI 等）均可加载，脚本均为跨平台 Python。

## 家族成员

| skill | 阶段 | 输出 |
|---|---|---|
| `bid-parse` | 解析招标文件（pdfplumber PDF 直读含表格还原 / docx） | `tender-analysis.yaml` + `招标项目分析报告.docx` |
| `bid-outline` | 设计应答大纲（**全流程唯一人工确认点**） | `bid-outline.yaml` |
| `bid-recall` | 从历史标书（人工真实投标 docx）召回相似章节与图片：章节全文 md 化 + 图片库 + 两段式召回（脚本粗筛 + LLM 精筛），**含人工确认点** | `recall-pack.yaml`（打底章节 + 替换表 + 图片清单） |
| `company-knowledge` | 公司素材入库（资信/业绩/人员/专利 → 素材卡片） | 素材库 + `index.yaml` |
| `bid-draft` | **改写引擎**：有召回打底的章节按新招标要求微调修改历史真实稿（替换表 + 技术需求逐条差异核对 + 历史真实图落地），无召回才从零生成，断点续作 | `chapters/*.md` + `figures/*.png` |
| `bid-check` | 评分点覆盖率 / 废标风险 / 格式核对 / **串味扫描**（`--fix` 自动修低风险项） | `check-report.md` |
| `bid-export` | docx 终稿导出（标题层级/表格/目录/图片嵌入/待补高亮） | `技术文件.docx` |

流水线：

```
招标文件 → bid-parse → bid-outline(人工确认) → bid-recall(人工确认) → bid-draft(改写为主) → bid-check → bid-export → 技术文件.docx
                          ▲                        ▲                    ↑
           company-knowledge(素材库) ───────────────┼────────────────────┘
                                 标书/历史标书/(人工真实投标稿，召回库) ─┘
```

**起草哲学**：召回+复用为主——人写的真实投标稿是正文主体与技术深度的来源，AI 是编辑/适配器（按新招标要求替换旧值、逐条核对技术需求差异）；历史库覆盖不到的章节才从零生成。**图片内容以召回为主**（历史真实图+现场照片），不生成示意图。

## 快速开始

```bash
# 1. 获取代码
git clone git@github.com:HUAN2022A/bid-skills.git
cd bid-skills && pip install -r requirements.txt

# 2. 把 7 个 skill 文件夹链接/复制到你的工具 skills 目录（见 INSTALL.md）
#    ZCode: ~/.zcode/skills/   Claude Code: ~/.claude/skills/   Codex CLI: ~/.codex/skills/

# 3. 准备召回库（可选但强烈建议）：把人工完成、真实投标过的历史标书 docx 放入 ~/Documents/标书/历史标书/
#    python bid-recall/build_index.py   # 建索引（章节全文 md + 图片库，可删重建的缓存）

# 4. 每个新标
/bid-parse      # 解析招标文件 → 人工核对分析报告
/bid-outline    # 生成大纲 → 人工审阅，status 改 confirmed（确认点一）
/bid-recall     # 召回历史标书打底章节+图片 → 人工勾选确认（确认点二）
/bid-draft      # 逐章改写（召回打底优先，断点续作）
/bid-check      # 自查（含串味扫描；--fix 自动修低风险项）
/bid-export     # 导出技术文件.docx 终稿
```

详细安装与平台差异说明见 **[INSTALL.md](INSTALL.md)**；项目总结与验证结果见 **[SUMMARY.md](SUMMARY.md)**；未来优化方向见 **[ROADMAP.md](ROADMAP.md)**。

## 约定

- **范围**：只写技术文件卷。商务、价格卷由人工完成——`bid-parse` 打分卷标签，`bid-check` 列「人工处理清单」，防止排除变成静默遗忘。
- **工作区**：每标一个 `{项目名}/` 目录，内含 `tender-analysis.yaml`、`bid-outline.yaml`、`chapters/` 等；阶段之间纯靠文件系统交接，与工具平台无关。
- **素材库**：默认 `~/Documents/company-knowledge/`（公司敏感数据，**不随本仓库分发**，每台机器自行入库）。公司事实（业绩/人员/资质）**只准引用素材库、不准编造**；缺素材显式标 `[待补：…]`。
- **联网**：起草阶段可联网查外部技术资料（行业规范、等保、信创目录、产品参数），查询内容**不得携带公司敏感信息**；解析阶段纯本地。
- **硬约束**：技术卷禁含报价信息；大纲未经确认（`status: confirmed`）不起草。

## 已验证

金标准项目（某央企电厂火车车厢智能解复列机器人，招标文件 + 95MB 中标标书 + 人工分析文档三方对照）全流程跑通：评分办法 10 项与人工分析完全一致，24 章 5.4 万字，5/5 技术评分项全覆盖，导出 docx 含 6 张嵌入插图。PDF 直读在 92 页真实招标 PDF 上验证（131 个表格全部还原行列结构）。

## 环境要求

- Python 3.9+，依赖见 `requirements.txt`（python-docx / PyYAML / pdfplumber / pypdf / matplotlib）
- 中文字体（配图用）：Windows 自带 SimHei；Linux 装 `fonts-noto-cjk`；macOS 自带 PingFang SC
