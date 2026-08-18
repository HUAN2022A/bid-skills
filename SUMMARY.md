# 技术标书 skill 家族 — 项目总结

> 版本：v1.0（2026-08-17）
> 仓库：`C:\Users\huan2\Documents\Skills`
> 状态：6 个 skill 全部建成，金标准项目（某央企电厂智能解复列机器人）全流程跑通并导出图文并茂的技术文件终稿。

---

## 一、这是什么

一套用 ZCode skill 实现的**技术标书（技术文件卷）半自动写作流水线**。输入一份招标文件（docx/pdf），输出一份逐点响应评分标准、带真实公司素材支撑、排版规范的 `技术文件.docx` 终稿。

核心理念一句话：**标书 = 逐点响应评分标准 + 真实素材支撑**。评分点对照表是贯穿全流程的中枢契约——解析阶段从招标文件拆出评分点，大纲阶段把评分点挂到每章，起草阶段逐点响应，检查阶段机器核对覆盖率，没有一处评分点能被静默漏掉。

## 二、家族成员与流水线

```
招标文件 ──► bid-parse ──► bid-outline ──► bid-draft ──► bid-check ──► bid-export ──► 技术文件.docx
              (解析)        (大纲)         (起草)        (自查)        (导出)
                              ▲              ▲
              company-knowledge ┘              │
              (素材入库) ── 素材卡片 ──────────┘
```

| skill | 职责 | 输入 → 输出 |
|---|---|---|
| `bid-parse` | 解析招标文件：评分办法逐条拆解、技术参数表、废标条款、资格门槛、商务要点、格式要求；另产出严格按人工模板的分析报告 | 招标文件 docx/pdf → `tender-analysis.yaml` + `招标项目分析报告.docx` |
| `bid-outline` | 设计应答大纲：章节树、每章挂评分点/素材引用/目标字数。**全流程唯一人工确认点** | `tender-analysis.yaml` → `bid-outline.yaml`（status: confirmed 后才放行起草） |
| `company-knowledge` | 公司素材入库：资信文件/历史标书 → 结构化素材卡片（案例/人员/资质/专利/能力） | 资信 docx → `~/Documents/company-knowledge/` 卡片库 + `index.yaml` |
| `bid-draft` | 逐章起草 markdown：上下文组装（大纲节点+评分原文+素材卡）、断点续作、配图 | → `chapters/*.md` + `figures/*.png` |
| `bid-check` | 自查：评分点覆盖矩阵、技术需求关键词命中、废标风险、格式核对、待补清单、人工处理清单 | → `check-report.md` |
| `bid-export` | 导出 docx 终稿：封面/自动目录/标题层级/表格/图片嵌入/待补高亮 | → `技术文件.docx` |

**硬性边界**：只写技术文件卷。商务卷、价格卷由人工完成——`bid-parse` 给评分项打「技术|商务|价格|资质」标签，`bid-check` 报告末尾固定输出「人工处理清单」，防止"不做"变成"忘了做"。

## 三、金标准验证结果

用真实项目全程验收：**某央企电厂「基于数字识别技术的火车车厢智能解复列机器人系统的研究与应用」**（招标文件 + 95MB 中标技术文件 + 用户人工分析文档）。

- **bid-parse**：评分办法 10 项与用户人工分析完全一致；第一版漏的限价/保证金/业绩资格/职称/联合体/付款条款经对照后补入 schema（新增 `qualification`、`commercial_notes` 段），支持「总分制」和「分卷百分制+权重」（10%/70%/20%）两种评分模式。
- **bid-outline**：10 个一级章 / 45 节点 / 18 万字规划，与中标文件 9 个 H2 章目录 diff 通过。
- **company-knowledge**：140 条业绩 → 11 张同类摘复钩案例卡、10 人员卡、26 获奖、353 专利软著；入库即暴露资格缺口（含正钩案例缺金额与验收证明）。
- **bid-draft**：24 章 markdown 全部完成，约 5.4 万字，7 处 `[待补]`（全部是公司事实缺口，等用户补材料）。配图扩至 **6 种内置图型**（架构/部署/甘特/识别流程/安全联锁逻辑/网络拓扑）。
- **bid-check**：5/5 技术评分项全覆盖、16/16 技术需求关键词命中、2 处"报价"字样经核为违约条款语境（误报排除）。
- **bid-export**：`技术文件.docx` = 封面 + 自动目录（打开自动更新页码）+ 10 个一级章 + 34 张表格 + **6 张嵌入插图** + 7 处待补黄色高亮。
- **PDF 直读（2026-08-17 补齐）**：`extract_pdf.py`（pdfplumber）在真实招标 PDF（某电厂电厂翻车机机器人，92 页）上验证——131 个表格全部还原行列结构，评分表（条款号|评分因素|满分值|评分标准）列归属精确；对比 pypdf 纯文本流（条款号游离、单元格错位）质量显著更优。

## 四、如何打包

skill 家族是纯文件目录，无构建步骤，打包即复制：

```bash
# 方式 1：直接压缩整个仓库（推荐，含 README）
cd C:\Users\huan2\Documents
tar -czf bid-skills-v1.0.tar.gz Skills/          # Git Bash
# 或 PowerShell: Compress-Archive Skills bid-skills-v1.0.zip

# 方式 2：git 仓库化（适合长期迭代与多机同步）
cd C:\Users\huan2\Documents\Skills
git init && git add -A && git commit -m "bid-* skill family v1.0"
git remote add origin <你的私有仓库> && git push -u origin main
```

打包内容 = 6 个 skill 文件夹（每个含 `SKILL.md` + 脚本）+ `README.md`，总共约 1850 行，无任何二进制依赖。

**注意：素材库 `~/Documents/company-knowledge/` 不在包内**——那是公司敏感数据（业绩/人员/资质），与 skill 代码刻意分离，绝不随包分发。

## 五、如何在其他地方复用

### 5.1 安装（新机器/新环境）

```bash
# 1. 解包到任意目录
tar -xzf bid-skills-v1.0.tar.gz        # 得到 Skills/

# 2. 把 6 个 skill 链接到 ZCode skills 目录（Windows 用 junction，无需管理员权限）
cd C:\Users\<用户名>\.zcode\skills
for d in bid-parse bid-outline bid-draft bid-check bid-export company-knowledge; do
  cmd //c mklink //J "$d" "C:\路径\到\Skills\$d"
done
# Linux/macOS 用软链：ln -s /路径/到/Skills/$d $d

# 3. 安装 Python 依赖
pip install python-docx pyyaml pypdf pdfplumber matplotlib
```

重启 ZCode 后，6 个 skill 即可通过 `/bid-parse`、`/bid-outline` 等调用，也会在对话中被自动触发。

### 5.2 每做一个新标

```bash
mkdir "标书/<项目名>" && cd "标书/<项目名>"    # 每标一个工作区
# 放入招标文件 docx
/bid-parse        # → tender-analysis.yaml + 招标项目分析报告.docx，人工核对
/bid-outline      # → bid-outline.yaml，人工审阅后把 status 改为 confirmed（唯一确认点）
/bid-draft        # → chapters/*.md + figures/*.png（可中断续作）
/bid-check        # → check-report.md，按报告修正
/bid-export       # → 技术文件.docx 终稿
```

素材库只需建一次（`/company-knowledge` 入库公司资信文件），之后所有标共用、增量补充。

## 六、使用条件

**环境依赖：**
- ZCode 客户端（skill 机制），Python 3.9+
- Python 包：`python-docx`、`pyyaml`、`pdfplumber`（PDF 招标文件表格还原，首选）、`pypdf`（兜底）、`matplotlib`（配图，需中文字体如 SimHei）
- Windows 上建 junction 用 `mklink /J`（无需管理员）；类 Unix 用 `ln -s`

**数据前提：**
- 招标文件电子版（docx 最佳，pdf 可走 pypdf 提取）
- 公司素材库：至少一份资信文件（业绩表/人员表/资质/知识产权清单）——**没有素材库，涉及公司事实的章节只能全部 `[待补]`**
- 有官方技术标模板 docx 时效果最好（`bid-export` 会复刻模板格式）

**人工必须承担的部分（不可省）：**
1. **大纲确认**——`bid-outline.yaml` 的 status 改为 confirmed，这是全流程唯一确认点，确认前不起草；
2. **公司事实补料**——`[待补]` 处（业绩证明、人员证书等）只能人工补真实材料；
3. **商务/价格卷**——家族刻意不做；
4. **终稿盖章、签字、上传投标系统**。

**红线（写进 skill 的硬约束）：**
- 公司事实（业绩/人员/资质）只准引用素材库，**禁止编造**；缺素材显式标 `[待补：…]`；
- 联网查外部技术资料（行业规范/等保/信创/产品参数）允许，但查询**不得携带公司敏感信息**；
- 技术卷中禁止出现报价信息（`bid-check` 会扫描）。

## 七、后续完善方向

按价值排序（1、2 已于 2026-08-17 完成）：

1. ~~**批量配图**~~ ✅ 已完成：`make_figures.py` 扩至 6 种图型（新增识别流程图、安全联锁逻辑图、网络拓扑图，含 `diamond` 判断菱形、`zone` 分区背景两个新绘图原语）。可继续：数据对比图（识别率/成功率 bar chart）、更多图型按项目需要往 `FIGS` 注册表加。
2. ~~**PDF 招标文件直读**~~ ✅ 已完成：`bid-parse/extract_pdf.py`（pdfplumber），表格还原为与 docx 提取一致的 `[表格]` 格式，正文与表格按版面位置交错输出；已在 92 页真实招标 PDF 上验证（131 表全还原）。遗留：无表格线的表格 `find_tables` 依赖线框，遇到漏表需调参或人工核对。
3. **官方模板复刻的自动化**：`bid-export` 已定义「模板优先」三级格式策略，但模板章节占位的自动识别还需人工指认；可做模板结构分析（按标题样式匹配章节锚点）减少手工映射。
4. **素材卡语义匹配**：升级为按评分点语义筛选（如"业绩≥200万"自动匹配 amount_wan≥200 且 has_正钩 的案例卡）。
5. **历史中标标书反向学习**：把中标标书入库为「范文卡」，按章节类型索引做风格参照（只学结构写法，不抄内容）。
6. **多标并行与复用**：同招标单位系列项目做"章节级复用推荐"。
7. **check 联动修复**：`bid-check` 加 `--fix` 模式，低风险格式项自动修，废标风险保持人工。
8. **协作流程**：chapters/ 按章拆分多人分工 + git 版本管理。

---

## 附：文件清单

```
Skills/
├── README.md                      # 家族总览与约定
├── bid-parse/                     # 招标文件解析（155 行 SKILL + 4 脚本）
│   ├── SKILL.md
│   ├── extract_docx.py            # docx 全文提取（段落+表格按文档顺序）
│   ├── extract_pdf.py             # pdfplumber PDF 提取（表格结构还原，正文表格按版面交错）
│   ├── validate_tender.py         # schema 校验（总分/权重两种评分模式）
│   └── generate_report.py         # 渲染严格模板版分析报告 docx
├── bid-outline/                   # 应答大纲（89 行 SKILL + 校验脚本）
│   ├── SKILL.md                   # 8 条大纲设计规则
│   └── validate_outline.py        # id 唯一/评分点全覆盖/骨架完整/字数加总
├── bid-draft/                     # 逐章起草（91 行 SKILL + 配图脚本）
│   ├── SKILL.md                   # 前置检查/上下文组装/6 条硬约束/配图规则
│   └── make_figures.py            # matplotlib 图型注册表（架构/部署/甘特/流程/联锁/拓扑）
├── bid-check/                     # 自查（62 行 SKILL + 检查脚本）
│   ├── SKILL.md
│   └── check_bid.py               # 覆盖矩阵/关键词命中/废标风险/待补清单
├── bid-export/                    # docx 导出（54 行 SKILL + 导出脚本）
│   ├── SKILL.md                   # 三级格式优先级（模板>招标要求>通用）
│   └── export_docx.py             # md→docx：目录域/标题映射/表格/图片嵌入
└── company-knowledge/             # 素材入库（109 行 SKILL + 入库脚本）
    ├── SKILL.md
    └── ingest.py                  # 资信 docx → 案例/人员/资质/专利卡片
```
