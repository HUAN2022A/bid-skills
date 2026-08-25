#!/usr/bin/env python3
"""构建历史标书召回索引（章节全文 md + 图片，纯图注匹配版）。

扫描 标书/历史标书/*.docx（人为完成的真实投标终稿）：
- 按 Heading 样式切章节（最细到 H3，H4/H5 归并入最近的祖先节并保留标题行）
- 章节全文导出为 md（正文 + 表格还原 + 图片引用），落盘到 标书/_recall-sections/<docslug>/
  —— 供 bid-draft 改写引擎直接读取打底
- 抽取全部内嵌图片（含表格内），落盘到 标书/_recall-figures/<docslug>/
- 图注取图片后第一个非空段落（"图：xxx" / "图 X-X xxx" 格式）
- 跨文档按图片内容 SHA256 去重，同图多文档标 shared_by
- 章节关键词：数字+单位 / 品牌型号 / 引号词+高频领域术语（自动提取，无硬编码词表）

写 标书/_recall-index.yaml。索引与导出物均为可再生缓存：删掉重跑即重建，
不产生第二份外部状态；原始 docx 永不修改。
"""
import argparse
import hashlib
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先: pip install pyyaml")

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
W_TBL = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"
A_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

MAX_DEPTH = 3          # 章节条目最细到 Heading 3
FIRST_TEXT_LEN = 240   # 索引内摘要长度（精筛看，全文读 md）
DOC_FIRST_TEXT_LEN = 600
FIG_REF = "../../_recall-figures/{fname}"   # md 内图片相对引用（相对 md 所在目录）


# ── 关键词自动提取（复制自 bid-check/check_bid.py，停用词表精简为纯通用功能词，
#    领域词交给统计自动得出——召回场景下领域词是高区分度信号，不应被停用） ──

_STOPWORDS = {
    "项目", "技术", "方案", "系统", "研究", "设计", "实施", "服务", "说明", "响应",
    "要求", "措施", "管理", "组织", "保证", "质量", "安全", "进度", "内容", "范围",
    "方法", "总体", "部署", "现场", "设备", "选型", "参数", "性能", "指标", "承诺",
    "分析", "应对", "风险", "应用", "场景", "提供", "方式", "数量", "条件", "能力",
    "水平", "基础", "理解", "认识", "概况", "背景", "意义", "现状", "全面", "实质",
    "投标", "招标", "相关", "其他", "详细", "具体", "针对", "目的", "建议", "计划",
    "进行", "完成", "确保", "具备", "应能", "可以", "需要", "包括", "以及", "并且",
    "或者", "如果", "因为", "所以", "但是", "然而", "因此", "这个", "那个", "哪些",
    "没有", "不是", "就是", "资料", "安装", "运输", "标准", "文件", "交付", "供货",
    "以上", "以下", "所有", "采用", "满足", "工作", "运行", "产品", "正常", "核心",
    "关键", "时间", "本项", "对本", "最终", "情况", "如下", "同时", "其中",
}


def extract_domain_terms(headings, body_texts):
    """从历史标书标题 + 正文自动统计领域术语：引号词 + 高频 2-4 字词。"""
    all_text = " ".join(headings + body_texts)
    terms = list(dict.fromkeys(re.findall(r'["「]([^"」]{2,10})["」]', all_text)))
    chars = re.findall(r"[一-鿿]", all_text)
    ngrams = Counter()
    for n in (2, 3, 4):
        for i in range(len(chars) - n + 1):
            ngrams["".join(chars[i:i + n])] += 1
    high_freq = [w for w, c in ngrams.most_common(60) if c >= 3 and w not in _STOPWORDS]
    terms.extend(high_freq[:15])
    terms = [t for t in terms if t not in _STOPWORDS]
    # 去碎片：短 n-gram 是另一更长术语的子串时丢弃（"机器"/"器人" 让位于"机器人"）
    return [t for t in terms if not any(t != t2 and t in t2 for t2 in terms)]


def extract_keywords(text, domain_terms=None):
    """从文本提取关键词（按特异度排序）：数字+单位 > 品牌/型号 > 领域术语。"""
    kws = re.findall(
        r"\d+(?:\.\d+)?\s*(?:%|秒|分钟|小时|天|个月|年|N|kN|kg|公斤|吨|m|mm|cm|km|"
        r"℃|dB|kV|V|A|kW|MW|GHz|G|GB|T|TB|核|线程|项|篇|套|节|寸)", text)
    brands = [b for b in re.findall(r"[A-Z][A-Za-z0-9&]*(?:[-/][A-Za-z0-9.]+)*", text)
              if len(b) >= 2 and b not in ("SSD", "HDD", "CPU", "CUDA")]
    kws.extend(brands)
    if domain_terms:
        kws.extend(t for t in domain_terms if t in text)
    return list(dict.fromkeys(kws))


# ── docx 解析 ──

def heading_level(para):
    """段落是 Heading N / 标题 N 时返回级别 int，否则 None。"""
    name = (para.style.name or "")
    m = re.match(r"(?:Heading|标题)\s*(\d+)", name)
    return int(m.group(1)) if m else None


FIG_TYPES = [
    ("架构图", r"架构|框架|结构图"),
    ("网络拓扑图", r"拓扑|网络图"),
    ("流程图", r"流程|工艺图"),
    ("甘特图", r"甘特|进度图|计划图"),
    ("联锁逻辑图", r"联锁|闭锁|逻辑图"),
    ("部署图", r"部署|布置图"),
    ("曲线图", r"曲线|波形"),
    ("示意图", r"示意|原理图|运动|仿真|插补"),
    ("现场照片", r"现场|实物|照片|实景|设备图"),
    ("表格截图", r"表格|清单图"),
]


def classify_fig(caption):
    for ftype, pat in FIG_TYPES:
        if re.search(pat, caption):
            return ftype
    return "其他"


def slug_filename(text, maxlen=40):
    s = re.sub(r'[\\/:*?"<>|\s…]+', "", text)[:maxlen]
    return s or "untitled"


def extract_images(el, doc, fig_dir, fig_counter):
    """抽取元素（段落或表格）内全部图片，返回 [(hash, extracted_path, orig, size)]。"""
    out = []
    for blip in el.findall(".//" + A_BLIP):
        rid = blip.get(R_EMBED)
        try:
            part = doc.part.related_parts[rid]
        except KeyError:
            continue
        blob = part.blob
        h = hashlib.sha256(blob).hexdigest()[:16]
        fname = f"{fig_counter[0]:03d}-{Path(str(part.partname)).name}"
        (fig_dir / fname).write_bytes(blob)
        fig_counter[0] += 1
        out.append((h, fig_dir / fname, str(part.partname), len(blob)))
    return out


def table_to_md(tbl):
    """表格 → md 表格文本；单元格内图片以 [图] 占位（图片本体由上层抽取）。"""
    has_img = bool(tbl._tbl.findall(".//" + A_BLIP))
    rows = []
    for r in tbl.rows:
        cells = []
        for c in r.cells:
            txt = " ".join(p.text.strip() for p in c.paragraphs if p.text.strip())
            cells.append(txt.replace("|", "/") or " ")
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(rows[0] + [" "] * (width - len(rows[0]))) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r + [" "] * (width - len(r))) + " |")
    md = "\n".join(lines)
    if has_img:
        md += "\n\n（本表含图片，见图片库）"
    return md


def parse_docx(path, fig_dir, sec_dir):
    """一次文档顺序遍历（段落 + 表格）：产出章节条目（含 md 全文）+ 图片条目。

    章节按"最近 level<=3 标题"归属聚合；H4/H5 标题以 #### 行并入祖先节。
    """
    doc = Document(str(path))
    body_els = [(el, Paragraph(el, doc)) if el.tag == W_P else (el, None)
                for el in doc.element.body]

    sections = {}          # path(tuple) -> dict
    order = []             # path 出现顺序
    figures = []           # 全部图片（含表格内）
    fig_counter = [0]
    doc_first_paras = []
    stack = []             # (level, heading) 标题栈

    def current_key():
        return tuple(h for lv, h in stack if lv <= MAX_DEPTH)

    def caption_after(idx):
        """图片段之后第一个非空段落文字（图注候选）。"""
        for j in range(idx + 1, min(idx + 5, len(body_els))):
            el, p = body_els[j]
            if p is None:
                continue
            if p.text.strip():
                return p.text.strip()
        return ""

    for idx, (el, p) in enumerate(body_els):
        key = current_key()
        if p is not None:
            text = p.text.strip()
            lv = heading_level(p)
            if lv:
                if not text:      # 空标题（常出现在文档封面/分隔页）不入章节树
                    continue
                while stack and stack[-1][0] >= lv:
                    stack.pop()
                stack.append((lv, text))
                key = current_key()
                if not key:
                    continue
                if key not in sections:
                    sections[key] = {
                        "level": lv, "heading": text, "path": " / ".join(key),
                        "md_parts": [], "text_parts": [], "fig_hashes": [],
                    }
                    order.append(key)
                if lv > MAX_DEPTH:
                    sections[key]["md_parts"].append(
                        "\n" + "#" * (min(lv, 5) + 1) + " " + text)
                else:
                    sections[key]["md_parts"].append("#" * (lv + 1) + " " + text)
            else:
                imgs = extract_images(el, doc, fig_dir, fig_counter)
                if imgs and key:
                    cap = caption_after(idx)
                    cap = cap if re.match(r"^图\s*[：:．.\d]", cap) and len(cap) <= 80 else ""
                    for h, fpath, orig, size in imgs:
                        ref = FIG_REF.format(fname=f"{fig_dir.name}/{fpath.name}")
                        sections[key]["md_parts"].append(
                            f"![{cap or Path(orig).stem}]({ref})")
                        figures.append({
                            "hash": h, "extracted": str(fpath), "orig": orig,
                            "caption": cap, "size": size,
                            "in_path": " / ".join(key),
                        })
                        sections[key]["fig_hashes"].append(h)
                if text:
                    if key:
                        sections[key]["md_parts"].append(text)
                        sections[key]["text_parts"].append(text)
                    elif len(doc_first_paras) < 8:
                        doc_first_paras.append(text)
        else:  # 表格（w:sdt/w:sectPr 等其他元素忽略）
            if el.tag != W_TBL:
                continue
            tbl = Table(el, doc)
            for h, fpath, orig, size in extract_images(el, doc, fig_dir, fig_counter):
                figures.append({
                    "hash": h, "extracted": str(fpath), "orig": orig,
                    "caption": "", "size": size, "in_path": " / ".join(key) if key else "",
                })
            md = table_to_md(tbl)
            if md and key:
                sections[key]["md_parts"].append(md)
                sections[key]["text_parts"].append(
                    " ".join(c.text.strip() for r in tbl.rows for c in r.cells))

    return sections, order, figures, doc_first_paras, [p.text.strip() for _, p in body_els if p is not None and heading_level(p)]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-w", "--workspace", default=str(Path.home() / "Documents" / "标书"),
                    help="标书工作区根目录（历史标书在其下的 历史标书/ 子目录）")
    args = ap.parse_args()
    ws = Path(args.workspace)
    src = ws / "历史标书"
    if not src.is_dir():
        sys.exit(f"找不到历史标书目录: {src}")

    docx_files = sorted(src.glob("*.docx"))
    if not docx_files:
        sys.exit(f"历史标书目录下没有 docx: {src}")

    fig_root = ws / "_recall-figures"
    sec_root = ws / "_recall-sections"
    fig_root.mkdir(exist_ok=True)
    sec_root.mkdir(exist_ok=True)

    all_sections, all_figures, docs_meta = [], [], []
    for f in docx_files:
        print(f"解析: {f.name}")
        slug = re.sub(r'[\\/:*?"<>|…\s]+', "", f.stem)[:24] or "doc"
        doc_fig_dir = fig_root / slug
        doc_sec_dir = sec_root / slug
        doc_fig_dir.mkdir(exist_ok=True)
        doc_sec_dir.mkdir(exist_ok=True)
        try:
            sections, order, figures, first_paras, headings = parse_docx(
                f, doc_fig_dir, doc_sec_dir)
        except Exception as e:
            print(f"  解析失败（跳过）: {e}")
            continue

        project = f.stem
        body_texts = [" ".join(s["text_parts"]) for s in sections.values()]
        domain_terms = extract_domain_terms(headings, body_texts)

        for n, key in enumerate(order):
            s = sections[key]
            body = " ".join(s["text_parts"])
            cn_words = len(re.findall(r"[一-鿿]", body))
            md_name = f"{n:03d}-{slug_filename(s['heading'])}.md"
            md_path = doc_sec_dir / md_name
            md_path.write_text("\n\n".join(s["md_parts"]) + "\n", encoding="utf-8")
            kws = extract_keywords(s["heading"] + " " + body, domain_terms)
            for fh in figures:
                if fh["in_path"] == s["path"] and fh["caption"]:
                    kws.extend(extract_keywords(fh["caption"], domain_terms))
            all_sections.append({
                "doc": f.name, "project": project, "slug": slug,
                "level": min(s["level"], MAX_DEPTH),
                "heading": s["heading"], "path": s["path"], "words": cn_words,
                "md": str(md_path.relative_to(ws)),
                "keywords": list(dict.fromkeys(kws))[:40],
                "figures": s["fig_hashes"],
                "first_text": body[:FIRST_TEXT_LEN],
            })
        for fh in figures:
            fh.update({"doc": f.name, "project": project,
                       "fig_type": classify_fig(fh["caption"] or fh["orig"])})
        all_figures.extend(figures)
        docs_meta.append({
            "file": f.name, "project": project, "slug": slug,
            "sections": len(order), "figures": len(figures),
            "first_text": " ".join(first_paras)[:DOC_FIRST_TEXT_LEN],
        })
        print(f"  章节 {len(order)}（全文已导出 md），图片 {len(figures)}"
              f"（图注命中 {sum(1 for x in figures if x['caption'])}）")

    # 跨文档图片去重：同 hash 聚合 shared_by
    by_hash = defaultdict(list)
    for fh in all_figures:
        by_hash[fh["hash"]].append(fh)
    dedup_figures = []
    for h, group in by_hash.items():
        head = dict(group[0])
        head["shared_by"] = sorted({g["doc"] for g in group})
        for g in group[1:]:
            if g["caption"] and not head["caption"]:
                head["caption"], head["in_path"] = g["caption"], g["in_path"]
                head["fig_type"] = classify_fig(g["caption"])
        dedup_figures.append(head)
    dedup_figures.sort(key=lambda x: -len(x["shared_by"]))

    index = {
        "built_at": date.today().isoformat(),
        "source_dir": str(src),
        "docs": docs_meta,
        "sections": all_sections,
        "figures": dedup_figures,
    }
    out = ws / "_recall-index.yaml"
    out.write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    shared = sum(1 for x in dedup_figures if len(x["shared_by"]) > 1)
    print()
    print(f"索引完成：文档 {len(docs_meta)}，章节 {len(all_sections)}（全文 md 已导出），"
          f"图片 {len(dedup_figures)}（跨文档通用图 {shared}）")
    print(f"索引: {out}")
    print(f"全文: {sec_root}")
    print(f"图片: {fig_root}")


if __name__ == "__main__":
    main()
