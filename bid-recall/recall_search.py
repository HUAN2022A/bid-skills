#!/usr/bin/env python3
"""召回粗筛：新项目大纲章节 × 历史标书索引，确定性计分，输出候选清单。

输入：{项目}/bid-outline.yaml（须 status: confirmed）+ tender-analysis.yaml
      + 标书/_recall-index.yaml（build_index.py 产物）
计分（各路归一化 0-1 加权）：
  章节 = 标题字符 bigram Dice×0.4 + 关键词命中×0.35 + 评分点/需求关键词命中×0.25
       （无评分点/需求的章节退化为 0.5/0.5）
  图片 = 图注命中×0.6 + 所属章节得分传导×0.4
输出：{项目}/recall-candidates.yaml（每章 top-8 章节 + top-12 图），供 LLM 精筛。
"""
import argparse
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).parent))
from build_index import extract_keywords, extract_domain_terms

W_TITLE, W_KW, W_CRIT = 0.4, 0.35, 0.25
TOP_SECTIONS, TOP_FIGURES = 8, 12


def flatten(chapters, out=None):
    if out is None:
        out = []
    for c in chapters or []:
        children = c.get("children") or []
        if children:
            flatten(children, out)
        else:
            out.append(c)
    return out


def bigrams(s):
    s = re.sub(r"[^\w一-鿿]", "", s)
    if len(s) < 2:
        return Counter({s: 1}) if s else Counter()
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def dice(c1, c2):
    if not c1 or not c2:
        return 0.0
    inter = sum((c1 & c2).values())
    return 2 * inter / (sum(c1.values()) + sum(c2.values()))


def hit_ratio(query_kws, target_text):
    if not query_kws:
        return 0.0
    return sum(1 for k in query_kws if k in target_text) / len(query_kws)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", required=True, help="新项目工作区目录")
    ap.add_argument("-w", "--workspace", default=str(Path.home() / "Documents" / "标书"),
                    help="标书工作区根目录（读其下 _recall-index.yaml）")
    args = ap.parse_args()
    ws = Path(args.dir)
    root = Path(args.workspace)

    outline_path = ws / "bid-outline.yaml"
    if not outline_path.is_file():
        sys.exit(f"找不到 {outline_path}，请先跑 bid-outline")
    outline = yaml.safe_load(outline_path.read_text(encoding="utf-8")) or {}
    if outline.get("status") != "confirmed":
        sys.exit("bid-outline.yaml 的 status 不是 confirmed，请先确认大纲（bid-outline 阶段）")

    index_path = root / "_recall-index.yaml"
    if not index_path.is_file():
        sys.exit(f"找不到召回索引 {index_path}，请先跑 build_index.py")
    index = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    sections = index.get("sections") or []
    figures = index.get("figures") or []
    if not sections:
        sys.exit("召回索引为空，请先跑 build_index.py")

    ta = {}
    ta_path = ws / "tender-analysis.yaml"
    if ta_path.is_file():
        ta = yaml.safe_load(ta_path.read_text(encoding="utf-8")) or {}

    # 新项目侧领域术语 + S/T id → 关键词展开（跨项目编号不可比，按原文关键词对齐）
    leaves = flatten(outline.get("chapters") or [])
    titles = [str(c.get("title") or "") for c in leaves]
    scoring_items = ta.get("scoring") or {}
    if isinstance(scoring_items, dict):          # schema: {total, mode, items: [...]}
        scoring_items = scoring_items.get("items") or []
    req_texts = [str(s.get("criteria_original") or "") for s in scoring_items]
    req_texts += [str(t.get("requirement_original") or "") for t in (ta.get("tech_requirements") or [])]
    domain_terms = extract_domain_terms(titles, req_texts)

    scoring_kws = {}
    for s in scoring_items:
        scoring_kws[str(s.get("id"))] = extract_keywords(
            f"{s.get('item', '')} {s.get('criteria_original', '')}", domain_terms)
    tech_kws = {}
    for t in ta.get("tech_requirements") or []:
        tech_kws[str(t.get("id"))] = extract_keywords(str(t.get("requirement_original") or ""), domain_terms)

    sec_bg_cache = [{"heading_bg": bigrams(s["heading"]), "path_bg": bigrams(s["path"]),
                     "match_text": " ".join([s["heading"], s["path"], " ".join(s.get("keywords") or []),
                                             s.get("first_text") or ""])} for s in sections]
    sec_by_docpath = {(s["doc"], s["path"]): i for i, s in enumerate(sections)}

    chapters_out = []
    for c in leaves:
        cid = str(c.get("id"))
        title = str(c.get("title") or "")
        crit_kws = []
        for sid in c.get("scoring") or []:
            crit_kws.extend(scoring_kws.get(str(sid), []))
        for tid in c.get("tech_reqs") or []:
            crit_kws.extend(tech_kws.get(str(tid), []))
        crit_kws = list(dict.fromkeys(crit_kws))
        title_kws = extract_keywords(f"{title} {c.get('notes') or ''}", domain_terms)
        q_kws = list(dict.fromkeys(title_kws + crit_kws))
        title_bg = bigrams(title)

        scored = []
        for i, s in enumerate(sections):
            bg = sec_bg_cache[i]
            s_title = max(dice(title_bg, bg["heading_bg"]), dice(title_bg, bg["path_bg"]))
            s_kw = hit_ratio(q_kws, bg["match_text"])
            if crit_kws:
                s_crit = hit_ratio(crit_kws, bg["match_text"])
                score = W_TITLE * s_title + W_KW * s_kw + W_CRIT * s_crit
            else:
                score = 0.5 * s_title + 0.5 * s_kw
            if score > 0.02:
                scored.append((score, i))

        scored.sort(reverse=True)
        # 去重：heading 相同（跨文档——同项目多版本/同型结构章只留一个代表），
        # 或同文档内路径嵌套（父章与子节都命中时留分高的），保留分数最高者
        picked = []
        for score, i in scored:
            s = sections[i]
            dup = False
            for _, j in picked:
                t = sections[j]
                if t["heading"] == s["heading"] or (
                        t["doc"] == s["doc"] and (
                        t["path"].startswith(s["path"] + " / ")
                        or s["path"].startswith(t["path"] + " / "))):
                    dup = True
                    break
            if not dup:
                picked.append((score, i))
            if len(picked) >= TOP_SECTIONS:
                break
        text_hits = []
        for score, i in picked:
            s = sections[i]
            text_hits.append({
                "doc": s["doc"], "project": s["project"], "level": s["level"],
                "heading": s["heading"], "path": s["path"], "words": s["words"],
                "md": s.get("md"),          # 全文 md（相对标书根），改写引擎直接读
                "figures": len(s.get("figures") or []),
                "score": round(score, 3),
                "first_text": s.get("first_text") or "",
            })

        # 图片：图注命中 + 所属章节得分传导
        fig_scored = []
        for f in figures:
            cap = f"{f.get('caption') or ''} {f.get('fig_type') or ''} {f.get('in_path') or ''}"
            s_cap = hit_ratio(q_kws, cap)
            cond = 0.0
            si = sec_by_docpath.get((f["doc"], f.get("in_path")))
            if si is not None:
                for score, i in scored:
                    if i == si:
                        cond = score
                        break
            fscore = 0.6 * s_cap + 0.4 * cond
            if fscore > 0.05:
                fig_scored.append((fscore, f))
        fig_scored.sort(key=lambda x: -x[0])
        figure_hits = []
        for fscore, f in fig_scored[:TOP_FIGURES]:
            figure_hits.append({
                "hash": f["hash"], "doc": f["doc"], "project": f["project"],
                "caption": f.get("caption") or "", "fig_type": f.get("fig_type"),
                "in_path": f.get("in_path"), "shared_by": f.get("shared_by"),
                "extracted": f["extracted"], "score": round(fscore, 3),
            })

        chapters_out.append({
            "id": cid, "title": title,
            "query": {"title_kws": title_kws[:15], "crit_kws": crit_kws[:15]},
            "text_hits": text_hits, "figure_hits": figure_hits,
        })
        best = text_hits[0] if text_hits else None
        bestfig = figure_hits[0] if figure_hits else None
        print(f"  {cid} {title[:24]} -> "
              + (f"[{best['score']}] {best['heading'][:26]}({best['doc'][:8]})" if best else "无命中")
              + (f" | 图: {bestfig['caption'][:20] or bestfig['fig_type']}" if bestfig else ""))

    out = {
        "project": outline.get("project"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "index_built_at": index.get("built_at"),
        "chapters": chapters_out,
    }
    out_path = ws / "recall-candidates.yaml"
    out_path.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
    n_hit = sum(1 for c in chapters_out if c["text_hits"])
    n_fig = sum(1 for c in chapters_out if c["figure_hits"])
    print()
    print(f"粗筛完成：{len(chapters_out)} 个叶章节，文本命中 {n_hit}，图片命中 {n_fig}")
    print(f"候选清单: {out_path}")
    print("下一步：按 bid-recall SKILL.md 做 LLM 精筛，产出 recall-pack.yaml")


if __name__ == "__main__":
    main()
