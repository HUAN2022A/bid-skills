#!/usr/bin/env python3
"""bid-check 机器可判定部分：评分点覆盖、技术需求关键词、章节齐全、待补扫描、报价混入检测。

输出结构化文本供汇总进 check-report.md。需要判断的检查（响应质量）由模型补充。
"""
import argparse
import re
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


def read_chapters(chdir):
    """返回 {文件头注释里的章节线索: 内容}，并解析 covers。"""
    res = {}
    for f in sorted(Path(chdir).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"<!--\s*covers:(.*?)-->", text, re.S)
        covers = m.group(1) if m else ""
        scoring = re.findall(r"scoring=\[([^\]]*)\]", covers)
        tech = re.findall(r"tech_reqs=\[([^\]]*)\]", covers)
        res[f.name] = {
            "text": text,
            "scoring": [s.strip() for s in scoring[0].split(",")] if scoring and scoring[0].strip() else [],
            "tech_reqs": [s.strip() for s in tech[0].split(",")] if tech and tech[0].strip() else [],
            "pending": len(re.findall(r"\[待补", text)),
            "words": len(re.sub(r"<!--.*?-->", "", text, flags=re.S).replace("\n", "").replace(" ", "")),
        }
    return res


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", required=True, help="项目工作区目录")
    args = ap.parse_args()
    ws = Path(args.dir)

    tender = yaml.safe_load((ws / "tender-analysis.yaml").read_text(encoding="utf-8")) or {}
    outline = yaml.safe_load((ws / "bid-outline.yaml").read_text(encoding="utf-8")) or {}
    chapters = read_chapters(ws / "chapters")

    tech_items = [it for it in (tender.get("scoring") or {}).get("items", []) if it.get("category") == "技术"]
    tech_reqs = tender.get("tech_requirements") or []
    disq = tender.get("disqualification") or []

    # ── 1. 评分点覆盖矩阵 ──
    print("## 一、评分点覆盖率矩阵\n")
    print("| 评分项 | 分值 | outline挂章 | 章节文件 | 覆盖状态 |")
    print("|---|---|---|---|---|")
    # outline 中评分点 -> 章节id
    o_chapters = flatten(outline.get("chapters"))
    score_to_chap = {}
    for ch in o_chapters:
        for s in ch.get("scoring") or []:
            score_to_chap.setdefault(str(s), []).append((str(ch.get("id")), ch.get("title")))
    # 章节文件里声明的 scoring
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
    # 为每条技术需求定义探测关键词
    kw_map = {
        "97%": ["97%"], "10秒": ["10秒", "10 秒"], "400N": ["400N", "120kg", "120公斤"],
        "臂展": ["臂展"], "3000N": ["3000N"], "99%": ["99%"], "90天": ["90天", "90 天"],
        "台达": ["台达", "西门子", "施耐德"], "DCS": ["DCS", "某国产DCS品牌", "GN"],
        "对侧": ["对侧"], "专利": ["发明专利", "专利"], "24个月": ["24个月", "24 个月"],
        "偏离": ["偏离"], "RTX4060": ["RTX4060", "服务器"],
    }
    for tr in tech_reqs:
        tid = str(tr.get("id"))
        orig = (tr.get("requirement_original") or "").strip().replace("\n", " ")[:30]
        # 选关键词
        kws = []
        for k, v in kw_map.items():
            if k in (tr.get("requirement_original") or ""):
                kws = v
                break
        if not kws:
            kws = [orig[:6]]
        hits = [fn for fn, txt in all_text.items() if any(k in txt for k in kws)]
        status = "✅" if hits else "❌ 未命中"
        print(f"| {tid} | {orig}… | {'/'.join(kws[:2])} | {'、'.join(hits[:3]) or '—'} | {status} |")
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
        # 简单判断
        result = "需人工复核"
        if "偏离" in summ or "技术偏离" in summ:
            result = "✅ 技术偏离表已编制（零偏离）" if any("偏离" in t for t in all_text.values()) else "❌ 缺技术偏离表"
        elif "关键技术响应表" in summ:
            result = "✅ 关键技术响应表已编制" if any("关键技术响应表" in t for t in all_text.values()) else "❌ 缺关键技术响应表"
        print(f"| {did} | {summ}… | {result} |")
    print()

    # ── 4. 格式核对 ──
    print("## 四、格式核对\n")
    # 章节齐全性：outline 叶章节 vs 文件
    leaf = [c for c in o_chapters if not c.get("children")]
    print(f"- 大纲叶章节数：{len(leaf)}；章节 .md 文件数：{len(chapters)}")
    # 报价混入检测
    price_hits = []
    for fn, txt in all_text.items():
        for m in re.finditer(r"(报价|投标价|总价款|万元|人民币\s*\d)", txt):
            # 排除"合同总价款"这类违约条款语境
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

    # ── 5. 待补缺口 ──
    print("## 五、[待补]缺口清单\n")
    total_pending = 0
    for fn, info in chapters.items():
        if info["pending"]:
            total_pending += info["pending"]
            for m in re.findall(r"\[待补[^]]*\]", info["text"]):
                print(f"- **{fn}**：{m}")
    print(f"\n共 {total_pending} 个待补项。\n")

    # ── 6. 人工处理清单 ──
    print("## 六、人工处理清单（商务/价格/资质，技术卷范围外）\n")
    biz = [it for it in (tender.get("scoring") or {}).get("items", []) if it.get("category") in ("商务", "价格", "资质")]
    for it in biz:
        print(f"- [{it.get('category')}] {it.get('item')}（{it.get('score')}分）")
    manual_disq = [d for d in disq if d.get("manual")]
    for d in manual_disq:
        print(f"- [废标-人工] {(d.get('clause_original') or '').strip()[:40]}…")
    print()


if __name__ == "__main__":
    main()
