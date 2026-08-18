# Skills — 技术标书 skill 家族（bid-*）

核心理念：**标书 = 逐点响应评分标准 + 真实素材支撑**。评分点对照表是贯穿全流程的中枢契约：`bid-parse` 提取 → `bid-outline` 每章挂评分点 → `bid-draft` 逐点响应 → `bid-check` 机器核对覆盖率。

## 家族成员

| skill | 阶段 | 状态 |
|---|---|---|
| `bid-parse` | 解析招标文件（pdfplumber PDF 直读含表格还原 / docx）→ `tender-analysis.yaml` + `招标项目分析报告.docx` | ✅ |
| `bid-outline` | 应答大纲（**唯一人工确认点**）→ `bid-outline.yaml` | ✅ |
| `bid-draft` | 逐章起草 markdown（含配图：6 种内置图型），断点续作 → `chapters/*.md` + `figures/*.png` | ✅ |
| `bid-check` | 评分点覆盖率 / 废标风险 / 格式核对 → `check-report.md` | ✅ |
| `bid-export` | docx 终稿导出（标题层级/表格/目录/图片嵌入/待补高亮）→ `技术文件.docx` | ✅ |
| `company-knowledge` | 公司素材入库（资信/业绩/人员/专利 → 素材卡片 + index.yaml） | ✅ |

构建顺序（**测试先行**，用真实招标文件 + 中标标书做金标准逐阶段验收）：
`bid-parse` → `bid-outline` → `company-knowledge` → `bid-draft` → `bid-check` → `bid-export`

## 约定

- **范围**：只写技术文件卷。商务、价格卷由人工完成——`bid-parse` 打分卷标签，`bid-check` 列「人工处理清单」，防止排除变成静默遗忘。
- **工作区**：每标一个 `{项目名}/` 目录，内含 `tender-analysis.yaml`、`bid-outline.yaml`、`chapters/` 等；阶段之间纯靠文件系统交接（照 research 家族模式）。
- **素材库**：`~/Documents/company-knowledge/`（敏感数据，独立于本仓库）。公司事实（业绩/人员/资质）**只准引用素材库、不准编造**；缺素材显式标 `[待补：…]`。
- **联网**：起草阶段可联网查外部技术资料（行业规范、等保、信创目录、产品参数），查询内容**不得携带公司敏感信息**；解析阶段纯本地。
- **加载**：各 skill 文件夹以 junction 软链到 `~\.zcode\skills\`。
