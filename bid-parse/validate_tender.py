#!/usr/bin/env python3
"""校验 tender-analysis.yaml：字段完整性 + 分值加总 + id 唯一性。"""
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先: pip install pyyaml")

VALID_CATEGORIES = {"技术", "商务", "价格", "资质", "其他"}
# 各集合的"原文逐字引用"字段
ORIG_FIELDS = {
    "scoring": "criteria_original",
    "tech_requirements": "requirement_original",
    "disqualification": "clause_original",
    "format_requirements": "requirement_original",
    "structure_requirements": "requirement_original",
    "qualification": "requirement_original",
    "commercial_notes": "requirement_original",
}


def section_items(data, section):
    if section == "scoring":
        return ((data.get("scoring") or {}).get("items")) or []
    return data.get(section) or []


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--file", required=True, help="tender-analysis.yaml 路径")
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"文件不存在: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    errors, warnings = [], []

    for key in ("project", "scoring"):
        if key not in data:
            errors.append(f"缺少顶层字段: {key}")

    all_ids = []
    for section, orig_field in ORIG_FIELDS.items():
        for i, it in enumerate(section_items(data, section)):
            tag = f"{section}[{i}]"
            if not it.get("id"):
                errors.append(f"{tag} 缺少 id")
            else:
                all_ids.append(str(it["id"]))
            orig = (it.get(orig_field) or "").strip()
            if not orig:
                errors.append(f"{tag} 缺少原文字段 {orig_field}")
            if "[待核实]" in orig:
                warnings.append(f"{tag} 原文含 [待核实] 标记")

    scoring = data.get("scoring") or {}
    items = scoring.get("items") or []
    for i, it in enumerate(items):
        tag = f"scoring.items[{i}]"
        if it.get("category") not in VALID_CATEGORIES:
            errors.append(f"{tag} category 非法: {it.get('category')}（合法值: {sorted(VALID_CATEGORIES)}）")
        if not isinstance(it.get("score"), (int, float)):
            errors.append(f"{tag} score 缺失或非数值")

    if len(all_ids) != len(set(all_ids)):
        dupes = sorted({d for d in all_ids if all_ids.count(d) > 1})
        errors.append(f"id 重复: {dupes}")

    if not items:
        errors.append("scoring.items 为空")
    else:
        weights = scoring.get("weights")
        if weights:
            # 加权模式：各分卷分别按 100 分制（或 category_totals 指定值）加总
            cat_totals = scoring.get("category_totals") or {}
            by_cat = {}
            for it in items:
                c = it.get("category", "?")
                by_cat[c] = by_cat.get(c, 0) + (it.get("score") or 0)
            for cat, w in weights.items():
                expect = cat_totals.get(cat, 100)
                got = by_cat.pop(cat, 0)
                if abs(got - expect) > 1e-9:
                    errors.append(f"分卷 [{cat}] 加总 {got} ≠ 该卷总分 {expect}，回原文核对，禁止改数字凑平")
            for cat, got in by_cat.items():
                errors.append(f"分卷 [{cat}] 有评分项 {got} 分但未在 weights 中声明权重")
            if abs(sum(weights.values()) - 1.0) > 1e-9:
                errors.append(f"weights 加总 {sum(weights.values())} ≠ 1.0")
        else:
            total = scoring.get("total")
            s = sum(it.get("score") or 0 for it in items)
            if total is not None and s != total:
                errors.append(f"分值加总 {s} ≠ 声称总分 {total}，回原文核对，禁止改数字凑平")

    # 统计摘要
    cats = {}
    for it in items:
        c = it.get("category", "?")
        cats[c] = (cats.get(c, 0) or 0) + (it.get("score") or 0)
    parts = ", ".join(
        f"{k} {v} 分/{sum(1 for i in items if i.get('category') == k)} 项" for k, v in sorted(cats.items())
    )
    print(f"项目: {data.get('project')}")
    print(f"评分项 {len(items)} 条（{parts}）")
    disq = data.get("disqualification") or []
    print(
        f"★技术参数 {len(data.get('tech_requirements') or [])} 条，"
        f"废标条款 {len(disq)} 条（人工处理 {sum(1 for d in disq if d.get('manual'))} 条），"
        f"格式要求 {len(data.get('format_requirements') or [])} 条，模板: {data.get('template_file')}"
    )
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
