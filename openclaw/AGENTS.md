# AGENTS.md — 运行指令

## 标书流水线（本工作区主业）

bid-* skill 家族：输入一份招标文件，输出逐点响应评分标准的技术文件.docx。

```
招标文件 ─► bid-parse ─► bid-outline ─► 【人工确认】 ─► bid-draft ─► bid-check ─► bid-export ─► 技术文件.docx
                             ▲                                  ▲
         company-knowledge（素材入库，建一次反复用）─────────────┘
```

执行规则：

- **阶段不可跳、不可连跑到底**。bid-outline.yaml 的 `status` 被人工改为 `confirmed` 之前不得起草——用户只丢一份招标文件说"做标书"时，跑到大纲就停，汇报摘要后等确认。这是全流程唯一确认点。
- **文件即交接**：阶段之间只靠 `{项目名}/` 目录里的产物交接（tender-analysis.yaml → bid-outline.yaml → chapters/*.md → check-report.md → 技术文件.docx），不靠对话记忆。
- **每标一个独立目录**：默认 `~/标书/{项目名}/`，项目名从文件名或招标文件首页提取（去非法字符，可用中文）。
- check 报告里的问题回 bid-draft 修正文；bid-check 只列清单不改文件。
- 商务/价格/资质项：bid-parse 打分卷标签、bid-check 出「人工处理清单」——本家族不代写这些卷，但不许静默遗忘。

## 素材双层架构（公司事实从哪来）

| 层 | 载体 | 职责 |
|---|---|---|
| **结构化事实层** | 素材库卡片 `~/Documents/company-knowledge/`（index.yaml + cases/people/...） | 资格判断与精确过滤（金额≥X、含正钩、职称副高以上）——语义召回做不了这种"一个不漏"的筛选，**硬事实以卡片为单一事实源** |
| **原文召回层** | RAGFlow 知识库（资信文件、历史标书全文；经 MCP 工具 `ragflow_retrieval` 调用） | 语义召回原文段落（同义/跨表述，如"摘钩"↔"车钩摘解"）、溯源证据、叙述性细节（公司简介、案例背景、技术路线描述） |

**检索顺序**：先 index.yaml 结构化过滤（本章 `materials` 关键词）→ 卡片覆盖不足时再 `ragflow_retrieval` 语义召回（question 用评分点/章节关键词，dataset 限定资信库，keyword=true 补术语精确匹配）。

**引用纪律：**

- 资格硬事实（金额、职称、数量、日期）以卡片为准；召回发现卡片缺失的新硬事实，**先回填卡片再写进正文**（保住单一事实源，bid-check 才核对得动）；两边都没有 → `[待补：…]`。
- 叙述性素材（简介、案例细节、技术路线措辞）可直接引用召回原文，注明来源文档；**数字原样照抄，不换算、不四舍五入**。
- 卡片与召回原文冲突：以原文为准，回写卡片。
- RAGFlow 不可用（故障/未配置）时回退纯卡片模式继续干活，但要在汇报里说明召回层缺失、[待补] 可能偏多。

## 红线（标书场景，违反即事故）

1. 公司事实（业绩/人员/资质/获奖/专利）**只准引用素材库卡片或召回层原文**（分工见「素材双层架构」）；硬事实先落卡再引用；禁止编造或"合理推测"；缺素材标 `[待补：…]`。
2. 技术卷正文**禁止出现报价信息**（bid-check 会扫描；"报价"字样仅允许出现在逐字引用的违约条款等原文语境）。
3. 联网查外部技术资料（行业规范/等保/信创/产品参数）允许，但**查询内容不得携带公司敏感信息**。自部署内网 RAGFlow 不算外联，可以用公司信息检索；**云端托管的 RAG/检索服务禁止放入或查询公司素材**。
4. 素材库、标书工作区、RAGFlow 数据集三者同级敏感：不进公开仓库、不外发、不放进会与其他 agent 共享的上下文。

## 记忆

- 过程记录写 `memory/YYYY-MM-DD.md`：今天在哪个标、跑到哪个阶段、`[待补]` 清单有无新增。
- 跨标 durable 的事实（常用招标单位、用户偏好的报告口径、素材库缺口）沉淀进 MEMORY.md。
- USER.md 只放用户偏好与沟通风格；写前先读，条目带 `<!-- observed: YYYY-MM-DD | status: active -->`，偏好变更时把旧条目标 superseded。

## 红线（通用）

- 破坏性命令（整目录删除、force push、覆盖大段文件）先问再动。
- 对外发送任何内容（邮件、给第三方的消息、上传）一律先确认。
- 改配置文件前先读现状，默认保留/合并已有内容，不整文件覆盖。

## Tools

Skills 定义工具怎么用；本节只记**本机环境特有**的信息。

### Local notes

- Python：3.9+，依赖 `pip install -r <Skills 仓库>/requirements.txt`（python-docx / pyyaml / pdfplumber / pypdf / matplotlib），装在网关宿主机上。
- matplotlib 中文字体已做多平台回退；Linux 宿主机若无中文字体，先装 `fonts-noto-cjk` 再跑配图。
- 素材库（卡片层）：`~/Documents/company-knowledge/`（敏感数据；按部署机器实际路径调整，WSL 下形如 `/mnt/c/Users/<用户名>/Documents/company-knowledge/`）。
- RAGFlow（召回层）：自部署 `http://<内网地址>:9380`，dataset「资信库」；经 MCP 挂载（工具 `ragflow_retrieval` / `ragflow_list_datasets`，接入配置见 Skills 仓库 `openclaw/README.md`）。
- 检索参数建议：`similarity_threshold` 0.2 起步、`top_k` 8~12、`keyword: true`；召回段落进上下文时必须带来源文档名。
- 标书项目根目录：`~/标书/`。
- 交付：docx / check-report.md 报文件路径 + 统计摘要；渠道支持附件就直接发文件，不支持就给路径。

### 平台格式

- WhatsApp / Telegram / Discord 等聊天渠道：用列表不用 Markdown 表格；长报告拆条或直接发文件。
