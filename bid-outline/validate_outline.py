#!/usr/bin/env python3
"""校验 bid-outline.yaml：章节编号唯一且有序、评分点全覆盖、骨架章齐全、字数加总合理。"""
import argparse
import sys
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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--outline", required=True, help="bid-outline.yaml 路径")
    ap.add_argument("-t", "--tender", required=True, help="tender-analysis.yaml 路径")
    args = ap.parse_args()

    outline = yaml.safe_load(Path(args.outline).read_text(encoding="utf-8")) or {}
    tender = yaml.safe_load(Path(args.tender).read_text(encoding="utf-8")) or {}
    errors, warnings = [], []

    chapters = flatten(outline.get("chapters"))
    if not chapters:
        errors.append("chapters 为空")

    # 1) 章节 id 唯一、必填字段
    ids = []
    for ch in chapters:
        cid = str(ch.get("id", "")).strip()
        if not cid:
            errors.append(f"章节缺少 id: {ch.get('title')}")
        else:
            ids.append(cid)
        if not ch.get("title"):
            errors.append(f"章节 {cid} 缺少 title")
        if not isinstance(ch.get("target_words"), (int, float)) and not ch.get("children"):
            warnings.append(f"章节 {cid} {ch.get('title')} 无 target_words 且无子章节")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"章节 id 重复: {dupes}")

    # 2) 评分点覆盖：技术类评分项每个至少挂一章
    tech_items = [it for it in (tender.get("scoring") or {}).get("items", []) if it.get("category") == "技术"]
    covered = set()
    for ch in chapters:
        for s in ch.get("scoring") or []:
            covered.add(str(s))
    for it in tech_items:
        if str(it.get("id")) not in covered:
            errors.append(f"技术评分项 {it.get('id')}（{it.get('item')}）未挂到任何章节")

    # 3) 骨架章齐全：structure_requirements 每条有对应章
    reqs = tender.get("structure_requirements") or []
    covered_reqs = {str(ch.get("source_req")) for ch in chapters if ch.get("source_req")}
    for r in reqs:
        if str(r.get("id")) not in covered_reqs:
            errors.append(f"结构要求 {r.get('id')}（{(r.get('requirement_original') or '')[:30]}…）无对应章节")

    # 4) 骨架章顺序：大纲骨架须按 structure_requirements 顺序出现（允许在其间/尾部插入附加章）
    req_order = [str(r.get("id")) for r in reqs]
    outline_skeleton = [str(ch.get("source_req")) for ch in outline.get("chapters", []) if ch.get("source_req")]
    positions = [req_order.index(r) for r in outline_skeleton if r in req_order]
    if positions != sorted(positions):
        errors.append(f"骨架章顺序与招标文件结构要求不一致: 大纲{outline_skeleton} vs 要求{req_order}")

    # 5) 字数加总
    total = outline.get("target_total_words")
    leaf_words = sum(ch.get("target_words") or 0 for ch in chapters if not ch.get("children"))
    if total and leaf_words:
        if abs(leaf_words - total) / total > 0.05:
            warnings.append(f"叶章节字数加总 {leaf_words} 与 target_total_words {total} 偏差超 5%")

    # 6) 技术需求覆盖提示（warning 级，一条可挂多章也可由方案整体响应）
    tech_reqs = {str(t.get("id")) for t in tender.get("tech_requirements") or []}
    covered_tr = set()
    for ch in chapters:
        for t in ch.get("tech_reqs") or []:
            covered_tr.add(str(t))
    missing_tr = tech_reqs - covered_tr
    if missing_tr:
        warnings.append(f"以下技术需求未显式挂到章节（起草时须在相关章节响应）: {sorted(missing_tr)}")

    # 摘要
    print(f"项目: {outline.get('project')}")
    print(f"章节: {len([c for c in outline.get('chapters', [])])} 个一级章 / {len(chapters)} 个节点；目标总字数 {total}，叶章节加总 {leaf_words}")
    print(f"技术评分项 {len(tech_items)} 项全部覆盖: {'是' if all(str(i.get('id')) in covered for i in tech_items) else '否'}")
    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        print()
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)
    print("校验通过 ✅")


if __name__ == "__main__":
    main()
