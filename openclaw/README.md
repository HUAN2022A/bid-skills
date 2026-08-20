# OpenClaw 部署指南

把 bid-* skill 家族迁移到 OpenClaw 网关。参照官方文档验证于 2026-08-18。

## 0. 机制速览

| 文件 | 作用 | 加载时机 |
|---|---|---|
| `SOUL.md` | 人设、价值观、语气 | 每次会话注入 |
| `AGENTS.md` | 运行指令 + `## Tools` 小节（环境特有信息） | 每次会话注入（Project Context，稳定可缓存） |
| `TOOLS.md` | **已弃用**。环境备注并入 AGENTS.md 的 `## Tools`；旧 workspace 遗留的跑 `openclaw doctor --fix` 自动迁移 | — |
| `skills/` | skill 目录，`SKILL.md` 兼容 AgentSkills 规范（name + description frontmatter，与现有格式一致，**无需改动**） | 只注入紧凑清单，模型按需 `read` SKILL.md |

单文件注入上限默认 20000 字符（`bootstrapMaxChars`），本目录两份配置远低于此。

## 1. 安装 skills（workspace 优先级最高）

```bash
# Git Bash (Windows)
mkdir -p ~/.openclaw/workspace/skills
cd /c/Users/huan2/Documents/Skills
for d in bid-parse bid-outline bid-draft bid-check bid-export company-knowledge; do
  cp -r "$d" ~/.openclaw/workspace/skills/
done

# Linux / WSL 网关（把仓库先同步过去）
mkdir -p ~/.openclaw/workspace/skills && cp -r bid-* company-knowledge ~/.openclaw/workspace/skills/
```

Windows 上也可用 junction 保持与本仓库单一来源：
`cmd //c mklink //J "%USERPROFILE%\.openclaw\workspace\skills\bid-parse" "C:\Users\huan2\Documents\Skills\bid-parse"`（每个 skill 一次）

## 2. 装 Python 依赖（网关宿主机）

```bash
pip install -r /c/Users/huan2/Documents/Skills/requirements.txt
# Linux 若缺中文字体：sudo apt install fonts-noto-cjk
```

## 3. 配 SOUL.md / AGENTS.md

拷贝或合并到 `~/.openclaw/workspace/`：

- 全新 workspace（未跑过 onboarding）：直接拷入两份文件。
- 已 onboarding 的 workspace：**合并而非覆盖**——把本目录 AGENTS.md 的「标书流水线」「红线（标书场景）」两节并进现有 AGENTS.md，`## Tools > ### Local notes` 里的路径按本机改；SOUL.md 与现有人设融合。

## 4. 验证

1. **新开一个会话**（skills 在会话启动时快照，热拷贝的 skill 下个 turn 才生效）。
2. 发一条招标文件路径 + "解析这份招标文件"，看是否自动触发 bid-parse。
3. 显式触发：消息里写 `$bid-parse`（OpenClaw 的显式引用语法）。
4. `user-invocable` 默认开启，聊天里 `/bid-parse` 等斜杠命令可用。

## 5. 接入 RAGFlow（召回后端）

素材库双层化：YAML 卡片管结构化事实（资格判断、精确过滤），RAGFlow 管原文召回（语义检索、溯源）。分工与引用纪律见 AGENTS.md「素材双层架构」。

1. **RAGFlow 侧**：自部署实例（内网）建 dataset「资信库」，上传资信文件——解析模板选带表格识别的（业绩/专利/人员都在表格里）；生成 API key。注意：RAGFlow 官方 MCP server 只有检索类工具（`ragflow_retrieval` / `ragflow_list_datasets` / `ragflow_list_chats`），**没有上传工具**，上传走 web 界面或 REST API。
2. **启动 RAGFlow MCP server**（RAGFlow 仓库 `mcp/server/server.py`，HTTP 传输，默认端口 9382）：
   ```bash
   python mcp/server/server.py \
     --base-url http://<ragflow内网地址>:9380 \
     --api-key <RAGFLOW_API_KEY> --mode self-host
   ```
3. **openclaw.json 挂载**（`mcp.servers`；工具以 `bundle-mcp` 插件暴露给 agent）：
   ```json5
   { mcp: { servers: { ragflow: { url: "http://<mcp地址>:9382/mcp" } } } }
   ```
   若你的 OpenClaw 版本 `mcp.servers` 只认 stdio，用桥接：
   ```json5
   { mcp: { servers: { ragflow: { command: "npx", args: ["-y", "mcp-remote", "http://<mcp地址>:9382/mcp"] } } } }
   ```
4. **沙箱注意**：sandbox mode 为 `all` / `non-main` 时，需在 `tools.sandbox.tools.alsoAllow` 里加 `"bundle-mcp"`（或精确到 `ragflow-*`），否则 MCP server 能加载但工具被静默过滤（`openclaw doctor` 可查）。
5. **验证**：新开会话，问「用 ragflow_retrieval 查素材库里含正钩的案例」——能召回原文段落并给出文档名即通；再发一份招标文件跑 `/bid-parse` 确认流水线不受影响。

## 6. 可选优化

- SKILL.md 正文里的 `<本skill目录>` 占位符保持不动也能用（模型会自行解析路径）；若想更稳，可批量替换为 OpenClaw 原生变量 `{baseDir}`（自动替换为 skill 实际路径）。
- frontmatter 可加 OpenClaw 门控，例如 `metadata.openclaw.requires.bins: [python]`（宿主机 PATH 无 python 时不注入该 skill）。注意 Windows 上可执行名是 `python`、Linux 上常是 `python3`，跨平台部署别加错。
- 素材库 `~/Documents/company-knowledge/` 与标书工作区**不要**放进公开仓库；workspace 本身建议放私有 git 仓库备份。
