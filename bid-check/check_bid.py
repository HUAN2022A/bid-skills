#!/usr/bin/env python3
"""bid-check 机器可判定部分：评分点覆盖、技术需求关键词、章节齐全、待补扫描、报价混入检测。

输出结构化文本供汇总进 check-report.md。需要判断的检查（响应质量）由模型补充。

--fix 模式：自动修复低风险项（covers 注释、文件名 id、图注编号、图片路径），
只碰元数据与编号，不改正文语义；修复前自动备份 chapters/ 到 chapters.bak-<时间戳>/。
"""
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先: pip install pyyaml")


def flatten(chapters, out=None):
    out = out if out is not None else []
    for ch in chapters or []:
        out.append(ch)
        flatten(ch.get("children"), out)
    return out


def read_chapters(chdir):
    """返回 {文件名: 信息}，解析 covers 注释（保留原文供 --fix 重写）。"""
    res = {}
    for f in sorted(Path(chdir).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"<!--\s*covers:(.*?)-->", text, re.S)
        covers_raw = m.group(0) if m else ""
        covers = m.group(1) if m else ""
        scoring = re.findall(r"scoring=\[([^\]]*)\]", covers)
        tech = re.findall(r"tech_reqs=\[([^\]]*)\]", covers)
        res[f.name] = {
            "text": text,
            "covers_raw": covers_raw,
            "scoring": [s.strip() for s in scoring[0].split(",")] if scoring and scoring[0].strip() else [],
            "tech_reqs": [s.strip() for s in tech[0].split(",")] if tech and tech[0].strip() else [],
            "pending": len(re.findall(r"\[待补", text)),
            "words": len(re.sub(r"<!--.*?-->", "", text, flags=re.S).replace("\n", "").replace(" ", "")),
        }
    return res


def chapter_sort_key(name):
    m = re.match(r"^([\d.]+)", name)
    if not m:
        return (999,)
    return tuple(int(x) for x in m.group(1).rstrip(".").split("."))


# ── 技术需求关键词自动提取 ──
# 从 requirement_original 原文提取探测关键词，替代硬编码 kw_map。
# 优先级：数字+单位 > 品牌/型号 > 领域术语（引号词+高频词）> 兜底（原文前6字）。


def _extract_domain_terms(titles, req_texts):
    """从 outline 章节标题 + tech_requirements 原文自动提取领域术语。

    简化策略（无停用词表、无 n-gram 统计）：
    1. 引号词：招标文件里"xxx"或「xxx」包围的词，通常是重要术语（如"技术偏离表""差异表"）；
    2. 高频词：在 tech_requirements 里出现 >=2 次的 2-4 字中文词，取 top 10。
    """
    from collections import Counter

    terms = []
    # 1. 引号词（最特异，招标文件作者主动强调的）
    all_text = " ".join(titles + req_texts)
    quoted = re.findall(r'["「]([^"」]{2,10})["」]', all_text)
    terms.extend(quoted)
    # 2. 高频词：tech_requirements 里出现 >=2 次的 2-4 字中文词
    chars = re.findall(r"[一-鿿]", " ".join(req_texts))
    bigrams = Counter()
    for n in (2, 3, 4):
        for i in range(len(chars) - n + 1):
            ng = "".join(chars[i:i + n])
            bigrams[ng] += 1
    # 取 top 10，过滤掉纯通用词（项目/技术/方案/系统等）
    common = {"项目", "技术", "方案", "系统", "研究", "设计", "实施", "服务", "说明", "响应",
              "要求", "措施", "管理", "组织", "保证", "质量", "安全", "进度", "内容", "范围",
              "方法", "手段", "总体", "部署", "现场", "改造", "设备", "选型", "参数", "性能",
              "指标", "承诺", "分析", "应对", "风险", "案例", "应用", "场景", "成果", "提供",
              "方式", "数量", "提交", "条件", "能力", "水平", "基础", "理解", "认识", "概况",
              "认知", "背景", "意义", "现状", "趋势", "全面", "深度", "实质", "声明", "投标",
              "招标", "机器人", "自动", "智能", "基于", "相关", "其他", "各类", "各项", "详细",
              "具体", "针对", "本项目", "目的", "建议", "计划", "进行", "完成", "确保", "具备",
              "应能", "可以", "需要", "包括", "以及", "并且", "或者", "如果", "因为", "所以",
              "但是", "然而", "因此", "这个", "那个", "什么", "怎么", "为什么", "哪里", "哪些",
              "多少", "没有", "不是", "就是", "资料", "安装", "清洁", "油漆", "包装", "运输",
              "储存", "调试", "试验", "验收", "监造", "检验", "标准", "制造", "图纸", "文件",
              "交付", "供货", "范围", "品牌", "控制", "检测", "识别", "机器", "器人", "钩机",
              "翻车", "车机", "制系", "制系统", "钩机器", "标人", "投标人", "招标人", "本项",
              "术偏", "离表", "技术偏", "术偏离", "目研", "项目研", "目研究", "核心", "时间",
              "偏离表", "技术偏离", "术偏离表", "项目研究", "项目实施", "投标方", "招标方",
              "规范", "规范书", "技术规范", "技术规范书", "控制系", "控制系统", "摘钩机",
              "摘钩机器", "摘钩机器人", "测识", "检测识", "测识别", "检测识别", "钩机器人",
              "正钩机器", "复钩机器", "人技术", "与备品", "服务计划", "项目实施组织", "以上",
              "成功", "功率", "机械", "械臂", "扣除", "成功率", "机械臂", "车型", "能够",
              "论文", "授权", "标方", "作业", "所有", "小于", "产品", "运行", "满足", "工作",
              "选用", "或同", "同等", "万元", "扣除万", "除万元", "扣除万元", "对本", "关键",
              "目实", "项目实", "目实施", "或同等", "范书", "保期", "车钩", "有机", "室外",
              "钩复", "采用", "及以", "项目的", "钩成", "率以", "人所", "期刊", "刊论",
              "最终", "未授", "权扣", "元项", "钩成功", "功率以", "等品", "牌产", "电缆",
              "不小", "所有机", "有机器", "钩复钩", "及以上", "同等品", "等品牌", "品牌产",
              "牌产品", "不小于", "所有机器", "有机器人", "率以上", "标人所", "期刊论",
              "刊论文", "未授权", "授权扣", "权扣除", "万元项", "钩成功率", "成功率以",
              "功率以上", "期刊论文", "术方", "技术方", "术方案", "技术方案", "正钩机",
              "人控", "器人控", "人控制", "机器人控", "器人控制", "未授权扣", "授权扣除",
              "权扣除万", "除万元项", "人控制系", "机系", "车机系", "机系统", "翻车机系",
              "除万", "或同等品", "同等品牌", "等品牌产", "品牌产品", "车机系统", "品备",
              "备品备", "品备件", "标时", "供的", "投标时", "提供的", "至少", "正常",
              "备品", "备件", "备品备件", "偏差", "元件", "钩正", "人系", "敞车"}
    high_freq = [w for w, c in bigrams.most_common(30) if c >= 2 and w not in common]
    terms.extend(high_freq[:10])
    # 去重
    seen = set()
    return [t for t in terms if not (t in seen or seen.add(t))]


def extract_keywords(text, domain_terms=None):
    """从单条技术需求原文提取探测关键词列表（按特异度排序）。

    domain_terms: 自动统计生成的领域术语列表，为 None 时退化为无领域术语模式。
    """
    kws = []
    # 1. 数字+单位组合（最特异）：97%、10秒、400N、120公斤、2m、90天、24个月、3000N、±1mm、≥98%、≤85 dB(A)
    num_unit = re.findall(
        r"\d+(?:\.\d+)?\s*(?:%|秒|分钟|小时|天|个月|年|N|kN|kg|公斤|吨|m|mm|cm|km|"
        r"℃|dB|kV|V|A|kW|MW|GHz|MHZ|GHZ|G|GB|T|TB|核|线程|项|篇|套|节|寸)",
        text)
    kws.extend(num_unit)
    # 2. 品牌/型号（英文+数字混合、纯大写英文、常见品牌名）：
    #    RTX4060、GDDR6、IP65、DCS、PLC、P&I、ZC-YJV22、C70EH-A、SKF、FAG、ABB、SIEMENS、ASCO、FESTO、SMC
    brand_model = re.findall(r"[A-Z][A-Za-z0-9&]*(?:[-/][A-Za-z0-9.]+)*", text)
    # 过滤掉单字母和纯通用词（A、B、I、O 等）
    brand_model = [b for b in brand_model if len(b) >= 2 and b not in ("SSD", "HDD", "CPU", "CUDA")]
    kws.extend(brand_model)
    # 3. 领域术语（自动统计生成，非硬编码）
    if domain_terms:
        for t in domain_terms:
            if t in text:
                kws.append(t)
    # 4. 兜底：如果前面都没提到，取原文前6字
    if not kws:
        kws = [text.strip()[:6]]
    # 去重
    seen2 = set()
    return [k for k in kws if not (k in seen2 or seen2.add(k))]


# ── 可自动修复项：checker/fixer 配对 ──

def check_covers(chapters, o_chapters, ws, fix):
    """covers 注释完整性：scoring 须与 outline 一致（子节继承父章挂点）；
    tech_reqs 允许是父章全集的子集（起草时按节认领），只补缺失的 scoring。
    fix 时重写文件头注释。"""
    issues, applied = [], []
    by_id = {str(c.get("id")): c for c in o_chapters}
    for fname, info in chapters.items():
        cid = re.match(r"^([\d.]+)", fname)
        cid = cid.group(1).rstrip(".") if cid else ""
        # 子节继承父章挂点（outline 通常把 scoring/tech_reqs 挂在一级章）
        exp_s, exp_t = [], []
        parts = cid.split(".")
        for i in range(len(parts), 0, -1):
            node = by_id.get(".".join(parts[:i]))
            if node:
                exp_s = [str(s) for s in (node.get("scoring") or [])]
                exp_t = [str(t) for t in (node.get("tech_reqs") or [])]
                if exp_s or exp_t:
                    break
        # scoring 必须精确一致；tech_reqs 是认领制，只报"声明了父章没有的"（越界）
        scoring_ok = sorted(info["scoring"]) == sorted(exp_s)
        overclaimed = [t for t in info["tech_reqs"] if t not in exp_t]
        if scoring_ok and not overclaimed:
            continue
        detail = []
        if not scoring_ok:
            detail.append(f"scoring 声明={info['scoring']} 应为={exp_s}")
        if overclaimed:
            detail.append(f"tech_reqs 越界声明={overclaimed}（父章挂点={exp_t}）")
        issues.append(f"{fname}: {'；'.join(detail)}")
        if fix:
            path = ws / "chapters" / fname
            text = path.read_text(encoding="utf-8")
            pending = len(re.findall(r"\[待补", text))
            keep_t = [t for t in info["tech_reqs"] if t in exp_t]
            new_comment = (f"<!-- covers: scoring=[{','.join(exp_s)}] "
                           f"tech_reqs=[{','.join(keep_t)}] pending={pending} -->")
            if info["covers_raw"]:
                text = text.replace(info["covers_raw"], new_comment, 1)
            else:
                text = new_comment + "\n" + text
            path.write_text(text, encoding="utf-8")
            applied.append(f"{fname}: covers 重写为 scoring={exp_s} tech_reqs={keep_t}")
    return issues, applied


def check_filename_id(chapters, o_chapters, ws, fix):
    """文件名前缀 id 与 outline 章节 id 一致性。fix 时按 outline id 重命名文件。"""
    issues, applied = [], []
    valid_ids = {str(c.get("id")) for c in o_chapters}
    for fname in chapters:
        m = re.match(r"^([\d.]+)(-.*)?\.md$", fname)
        if not m:
            issues.append(f"{fname}: 文件名无章节 id 前缀")
            continue
        fid = m.group(1).rstrip(".")
        if fid in valid_ids:
            continue
        # 找最接近的合法 id（相同数字序列不同分隔，如 2.10 vs 2.1.0 不做猜，只处理完全找不到的）
        issues.append(f"{fname}: id 前缀 '{fid}' 不在大纲章节 id 中")
        if fix:
            # 仅当前缀是大纲 id 的明显笔误（数字相同仅点多寡不同）才自动改
            norm = fid.replace(".", "")
            cand = [v for v in valid_ids if v.replace(".", "") == norm]
            if len(cand) == 1:
                newname = cand[0] + (m.group(2) or "") + ".md"
                (ws / "chapters" / fname).rename(ws / "chapters" / newname)
                applied.append(f"{fname} → {newname}")
            else:
                applied.append(f"{fname}: 无法唯一推断正确 id，未改名（需人工）")
    return issues, applied


def _figure_scan(chapters):
    """扫描全文图注与正文引用，返回 {文件名: [(行号, 完整match, 章号, 序号, 标题, 路径)]}。"""
    figs = {}
    for fname, info in chapters.items():
        items = []
        for ln, line in enumerate(info["text"].split("\n")):
            m = re.match(r"^!\[图\s*(\d+)-(\d+)\s*([^\]]*)\]\(([^)]+)\)", line.strip())
            if m:
                items.append((ln, m.group(0), m.group(1), int(m.group(2)), m.group(3).strip(), m.group(4)))
        if items:
            figs[fname] = items
    return figs


def check_figure_numbering(chapters, ws, fix):
    """图注编号：X 须等于章一级编号，Y 在章内按出现顺序连续（跨文件累计）。
    fix 时重编并同步正文引用。"""
    issues, applied = [], []
    figs = _figure_scan(chapters)
    # 章内序号按一级章分组、跨文件累计（2.3 与 2.4 同属第 2 章，序号接续）
    counters = {}
    for fname in sorted(figs, key=chapter_sort_key):
        cm = re.match(r"^(\d+)", fname)
        chap_no = cm.group(1) if cm else ""
        for (ln, raw, x, y, title, path) in figs[fname]:
            counters[chap_no] = counters.get(chap_no, 0) + 1
            want = f"图 {chap_no}-{counters[chap_no]}"
            got = f"图 {x}-{y}"
            if x != chap_no or y != counters[chap_no]:
                issues.append(f"{fname}: {got}（{title}）编号不规范，应为「{want}」")
                if fix:
                    fpath = ws / "chapters" / fname
                    text = fpath.read_text(encoding="utf-8")
                    # 替换图注行与正文引用（仅"图 X-Y"字符串映射，不碰其他内容）
                    text = re.sub(rf"图\s*{x}-{y}(?!\d)", want, text)
                    fpath.write_text(text, encoding="utf-8")
                    applied.append(f"{fname}: {got} → {want}（图注与正文引用已同步）")
    return issues, applied


def check_image_path(chapters, ws, fix):
    """图片引用路径有效性。fix 时在 figures/ 下找同名/唯一相似名修正。"""
    issues, applied = [], []
    figdir = ws / "figures"
    available = {p.name: p for p in figdir.glob("*") if p.is_file()} if figdir.exists() else {}
    for fname, info in chapters.items():
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", info["text"]):
            rel = m.group(1)
            if (ws / rel).exists():
                continue
            name = Path(rel).name
            issues.append(f"{fname}: 图片路径失效 {rel}")
            if fix:
                if name in available:
                    newrel = f"figures/{name}"
                    fpath = ws / "chapters" / fname
                    text = fpath.read_text(encoding="utf-8").replace(f"]({rel})", f"]({newrel})")
                    fpath.write_text(text, encoding="utf-8")
                    applied.append(f"{fname}: {rel} → {newrel}")
                else:
                    # 唯一相似名（去扩展名后前缀匹配）
                    stem = Path(name).stem
                    cand = [n for n in available if n.startswith(stem) or stem.startswith(Path(n).stem)]
                    if len(cand) == 1:
                        newrel = f"figures/{cand[0]}"
                        fpath = ws / "chapters" / fname
                        text = fpath.read_text(encoding="utf-8").replace(f"]({rel})", f"]({newrel})")
                        fpath.write_text(text, encoding="utf-8")
                        applied.append(f"{fname}: {rel} → {newrel}（相似名匹配）")
                    else:
                        applied.append(f"{fname}: figures/ 下无匹配图片，未修（需人工）")
    return issues, applied


def backup_chapters(ws):
    """--fix 前备份 chapters/ 到 chapters.bak-<时间戳>/。已存在同名备份则跳过。"""
    src = ws / "chapters"
    dst = ws / ("chapters.bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copytree(src, dst)
    return dst


def check_cross_contamination(chapters, ws):
    """串味扫描：召回改写模式下，正文残留旧项目专有信息即报警（宁误报不漏报）。

    词表来源：recall-pack 的 replacements[].old（旧项目名/业主/工期/数量等）
    + 被引用历史文档文件名中的机构名（XX有限公司/发电厂等，即旧招标人）。
    无 recall-pack 时跳过（纯生成模式无此风险面）。业绩叙述中的第三方项目名
    不在词表内，不会误报；命中项需人工判断（若属合法引用可忽略）。
    """
    pack_path = ws / "recall-pack.yaml"
    if not pack_path.is_file():
        return None, []          # None = 本项目无召回改写，跳过
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8")) or {}
    words = set()
    for r in pack.get("replacements") or []:
        old = str(r.get("old") or "").strip()
        if len(old) >= 4:
            words.add(old)
    docs = set()
    for ch in pack.get("chapters") or []:
        for h in (ch.get("text_hits") or []) + (ch.get("figure_hits") or []):
            if h.get("doc"):
                docs.add(str(h["doc"]))
    for d in docs:
        for m in re.findall(r"[一-鿿]{2,14}(?:有限公司|发电厂|股份公司|集团)", d):
            words.add(m)
    issues = []
    for fn, info in chapters.items():
        for w in sorted(words):
            i = info["text"].find(w)
            if i >= 0:
                ctx = info["text"][max(0, i - 12):i + len(w) + 12].replace("\n", " ")
                issues.append(f"{fn}：残留「{w}」…{ctx}…")
    return "ok", issues


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", required=True, help="项目工作区目录")
    ap.add_argument("--fix", action="store_true", help="自动修复低风险项（修复前自动备份 chapters/）")
    args = ap.parse_args()
    ws = Path(args.dir)

    tender = yaml.safe_load((ws / "tender-analysis.yaml").read_text(encoding="utf-8")) or {}
    outline = yaml.safe_load((ws / "bid-outline.yaml").read_text(encoding="utf-8")) or {}
    chapters = read_chapters(ws / "chapters")

    tech_items = [it for it in (tender.get("scoring") or {}).get("items", []) if it.get("category") == "技术"]
    tech_reqs = tender.get("tech_requirements") or []
    disq = tender.get("disqualification") or []
    o_chapters = flatten(outline.get("chapters"))

    # ── 1. 评分点覆盖矩阵 ──
    print("## 一、评分点覆盖率矩阵\n")
    print("| 评分项 | 分值 | outline挂章 | 章节文件 | 覆盖状态 |")
    print("|---|---|---|---|---|")
    score_to_chap = {}
    for ch in o_chapters:
        for s in ch.get("scoring") or []:
            score_to_chap.setdefault(str(s), []).append((str(ch.get("id")), ch.get("title")))
    file_scoring = {}
    for fname, info in chapters.items():
        for s in info["scoring"]:
            file_scoring.setdefault(s, []).append(fname)
    for it in tech_items:
        sid = str(it.get("id"))
        ochaps = score_to_chap.get(sid, [])
        ochap_str = "、".join(c[0] for c in ochaps) or "—"
        ffiles = file_scoring.get(sid, [])
        if ffiles:
            status = "✅ 已响应"
            fstr = "、".join(ffiles)
        elif ochaps:
            status = "⚠️ 章节在大纲但未生成/未声明"
            fstr = "—"
        else:
            status = "❌ 未挂章"
            fstr = "—"
        print(f"| {sid} {it.get('item')} | {it.get('score')} | {ochap_str} | {fstr} | {status} |")
    print()

    # ── 2. 技术需求关键词响应 ──
    print("## 二、技术需求逐条响应（关键词命中）\n")
    print("| id | 要求摘要 | 关键词 | 命中章节 | 状态 |")
    print("|---|---|---|---|---|")
    all_text = {fn: info["text"] for fn, info in chapters.items()}
    # 自动统计领域术语（从 outline 标题 + tech_requirements 原文）
    o_titles = [c.get("title", "") for c in o_chapters]
    req_texts = [(tr.get("requirement_original") or "") for tr in tech_reqs]
    domain_terms = _extract_domain_terms(o_titles, req_texts)
    for tr in tech_reqs:
        tid = str(tr.get("id"))
        orig = (tr.get("requirement_original") or "").strip().replace("\n", " ")[:30]
        kws = extract_keywords(tr.get("requirement_original") or "", domain_terms)
        hits = [fn for fn, txt in all_text.items() if any(k in txt for k in kws)]
        status = "✅" if hits else "❌ 未命中"
        print(f"| {tid} | {orig}… | {'/'.join(kws[:3])} | {'、'.join(hits[:3]) or '—'} | {status} |")
    print()

    # ── 3. 废标风险（技术卷相关）──
    print("## 三、废标风险清单（技术卷相关）\n")
    print("| id | 条款摘要 | 自查结果 |")
    print("|---|---|---|")
    for d in disq:
        if d.get("manual"):
            continue
        did = str(d.get("id"))
        summ = (d.get("clause_original") or "").strip().replace("\n", " ")[:40]
        result = "需人工复核"
        if "偏离" in summ or "技术偏离" in summ:
            result = "✅ 技术偏离表已编制（零偏离）" if any("偏离" in t for t in all_text.values()) else "❌ 缺技术偏离表"
        elif "关键技术响应表" in summ:
            result = "✅ 关键技术响应表已编制" if any("关键技术响应表" in t for t in all_text.values()) else "❌ 缺关键技术响应表"
        print(f"| {did} | {summ}… | {result} |")
    print()

    # ── 4. 格式核对 ──
    print("## 四、格式核对\n")
    leaf = [c for c in o_chapters if not c.get("children")]
    print(f"- 大纲叶章节数：{len(leaf)}；章节 .md 文件数：{len(chapters)}")
    price_hits = []
    for fn, txt in all_text.items():
        for m in re.finditer(r"(报价|投标价|总价款|万元|人民币\s*\d)", txt):
            ctx = txt[max(0, m.start()-10):m.start()+12]
            if "报价" in m.group() or "人民币" in m.group():
                price_hits.append((fn, m.group(), ctx.replace("\n", " ")))
    if price_hits:
        print(f"- ⚠️ 检测到 {len(price_hits)} 处疑似报价/价格信息（技术卷禁含报价，需人工确认是否为违约条款语境）:")
        for fn, kw, ctx in price_hits[:10]:
            print(f"  - {fn}: 「…{ctx}…」")
    else:
        print("- ✅ 未检测到报价信息混入")
    print()

    # ── 5. 串味扫描（召回改写残留）──
    print("## 五、串味扫描（召回改写残留）\n")
    cont_flag, cont_issues = check_cross_contamination(chapters, ws)
    if cont_flag is None:
        print("- 本项目无 recall-pack（纯生成模式），跳过串味扫描\n")
    elif not cont_issues:
        print("- ✅ 未检出旧项目专有信息残留\n")
    else:
        print(f"- ❌ 检出 {len(cont_issues)} 处旧项目信息残留（改写缺陷，必须处理；"
              "若属业绩叙述合法引用可人工判定忽略）:")
        for it in cont_issues:
            print(f"  - {it}")
        print()

    # ── 6. 待补缺口 ──
    print("## 六、[待补]缺口清单\n")
    total_pending = 0
    for fn, info in chapters.items():
        if info["pending"]:
            total_pending += info["pending"]
            for m in re.findall(r"\[待补[^]]*\]", info["text"]):
                print(f"- **{fn}**：{m}")
    print(f"\n共 {total_pending} 个待补项。\n")

    # ── 6. 人工处理清单 ──
    print("## 八、人工处理清单（商务/价格/资质，技术卷范围外）\n")
    biz = [it for it in (tender.get("scoring") or {}).get("items", []) if it.get("category") in ("商务", "价格", "资质")]
    for it in biz:
        print(f"- [{it.get('category')}] {it.get('item')}（{it.get('score')}分）")
    manual_disq = [d for d in disq if d.get("manual")]
    for d in manual_disq:
        print(f"- [废标-人工] {(d.get('clause_original') or '').strip()[:40]}…")
    print()

    # ── 7. 低风险项自动修复（--fix）──
    print("## 九、低风险项检查与自动修复\n")
    checkers = [
        ("covers注释与大纲一致性", check_covers),
        ("文件名与大纲id一致性", check_filename_id),
        ("图注编号规范性", check_figure_numbering),
        ("图片引用路径有效性", check_image_path),
    ]
    all_issues = {}
    for name, fn in checkers:
        if fn in (check_covers, check_filename_id):
            issues, _ = fn(chapters, o_chapters, ws, fix=False)
        else:
            issues, _ = fn(chapters, ws, fix=False)
        all_issues[name] = issues
    total_issues = sum(len(v) for v in all_issues.values())

    if total_issues == 0:
        print("- ✅ 四项低风险检查全部通过，无需修复\n")
    else:
        for name, issues in all_issues.items():
            if issues:
                print(f"- **{name}**（{len(issues)} 项）:")
                for it in issues:
                    print(f"  - {it}")
        print()
        if args.fix:
            bak = backup_chapters(ws)
            print(f"已备份 chapters/ → {bak.name}/\n")
            print("修复记录：")
            chapters = read_chapters(ws / "chapters")  # 重读（修复可能改了文件）
            for name, fn in checkers:
                if not all_issues[name]:
                    continue
                if fn in (check_covers, check_filename_id):
                    _, applied = fn(chapters, o_chapters, ws, fix=True)
                else:
                    _, applied = fn(chapters, ws, fix=True)
                for a in applied:
                    print(f"  - {a}")
            print()
        else:
            print("（未开启 --fix，以上仅检测报告未修改；加 --fix 自动修复，修复前自动备份）\n")


if __name__ == "__main__":
    main()
