# bid-skills 安装指南

技术标书 skill 家族（7 个）：`bid-parse` → `bid-outline` → `bid-recall`（历史标书召回）→ `bid-draft`（改写引擎）→ `bid-check` → `bid-export`，外加 `company-knowledge` 素材入库。详见 `SUMMARY.md`（项目总结）与 `README.md`（家族约定）。

## 1. 环境要求

- Python 3.9+
- 安装依赖：

  ```bash
  pip install -r requirements.txt
  ```

- **中文字体**（配图用，缺了图上中文会变方框）：
  - Windows：自带 SimHei，无需操作
  - Linux：`sudo apt install fonts-noto-cjk` 或 `fonts-wqy-microhei`
  - macOS：自带 PingFang SC，无需操作

## 2. 安装 skill 到你的 AI 编程工具

skill 采用通用 `SKILL.md` 格式（YAML frontmatter + 正文），把 7 个文件夹放进你工具的 skills 目录即可，可复制或软链：

| 平台 | skills 目录 |
|---|---|
| ZCode | `~/.zcode/skills/` |
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.codex/skills/` |

Windows（junction，无需管理员权限）：

```powershell
cd %USERPROFILE%\.zcode\skills
for /d %d in (D:\bid-skills\bid-*) do mklink /j "%~nxd" "%d"
mklink /j company-knowledge D:\bid-skills\company-knowledge
```

Linux / macOS：

```bash
ln -s /path/to/bid-skills/bid-* /path/to/bid-skills/company-knowledge ~/.zcode/skills/
```

重启工具后生效，调用 `/bid-parse`、`/bid-outline` 等。

## 3. 初始化素材库（敏感数据，不随包分发）

`company-knowledge` 的素材库默认在 `~/Documents/company-knowledge/`，**安装包里没有**——每台机器自己入库：

```
/company-knowledge            # 在对话中触发，把公司资信文件 docx 解析成素材卡片
```

硬约束：公司事实（业绩/人员/资质）只准引用素材库，禁止编造；缺素材的章节会标 `[待补：…]` 等人工补。

## 4. 使用流程（每个新标）

```
mkdir 标书/项目名 && 把招标文件放进去
/bid-parse      # → tender-analysis.yaml + 招标项目分析报告.docx（人工核对）
/bid-outline    # → bid-outline.yaml（人工审阅，status 改 confirmed —— 唯一确认点）
/bid-draft      # → chapters/*.md + figures/*.png（断点续作）
/bid-check      # → check-report.md
/bid-export     # → 技术文件.docx 终稿
```

## 5. 平台差异说明

- 脚本均为 Python 标准跨平台，路径用 `pathlib`，无 Windows 专属依赖
- PDF/docx 读写、matplotlib 出图在三大平台均可运行
- 每标一个工作区目录，阶段间靠文件系统交接，与工具平台无关
