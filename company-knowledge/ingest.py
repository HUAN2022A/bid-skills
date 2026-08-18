#!/usr/bin/env python3
"""解析公司素材 docx，生成结构化素材卡片与 index.yaml。

当前实现聚焦资信文件（含业绩表、核心人员表、专利表、获奖表、部门人员构成）
与历史技术文件（提取项目案例）。只记录原始文件里有的信息，资格关键字段
缺失标 [待补]。
"""
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先: pip install pyyaml")

from docx import Document


def slug(text):
    s = re.sub(r"[^\w一-鿿-]", "", text)[:24]
    return s or "item"


def cells(row):
    return [c.text.strip() for c in row.cells]


def parse_zixin(path):
    """解析资信文件：返回 cases, people, credentials, ip, capability 原始数据。"""
    doc = Document(path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    tables = doc.tables

    data = {"cases": [], "people": [], "awards": [], "patents": [], "intro": ""}

    # 公司简介：取"公司简介"标题后的长段落
    full = "\n".join(paras)
    m = re.search(r"公司简介\s*\n(.{100,2000}?)\n公司部分资质", full, re.S)
    if m:
        data["intro"] = m.group(1).strip()

    # 表格识别（按表头）
    for t in tables:
        if not t.rows:
            continue
        header = "|".join(cells(t.rows[0]))
        body = [cells(r) for r in t.rows[1:]]

        if "项目名称" in header and ("合同签订单位" in header or "终端使用单位" in header):
            for c in body:
                if len(c) >= 5 and c[1]:
                    data["cases"].append({
                        "name": c[1], "contractor": c[2], "client": c[3],
                        "sign_date": c[4], "remark": c[5] if len(c) > 5 else "",
                    })
        elif "姓名" in header and "专业领域" in header:
            for c in body:
                if len(c) >= 4 and c[0] and c[0] != "姓名":
                    data["people"].append({
                        "name": c[0], "field": c[1], "title": c[2], "background": c[3],
                    })
        elif "奖项名称" in header or "获奖项目" in header:
            for c in body:
                if len(c) >= 3 and c[1] and not c[1].startswith(("1、", "2、", "3、")):
                    data["awards"].append({"name": c[1], "project": c[2],
                                           "issuer": c[3] if len(c) > 3 else ""})
        elif "专利申请名称" in header:
            for c in body:
                if len(c) >= 2 and c[1]:
                    data["patents"].append({"name": c[1], "source_type": c[2] if len(c) > 2 else ""})
        elif "软件著作登记名称" in header:
            for c in body:
                if len(c) >= 2 and c[1]:
                    data["patents"].append({"name": c[1], "type": "软著"})

    return data


SCOPE_KEYS = {"摘钩": "摘钩", "复钩": "复钩", "正钩": "正钩", "摘复": "摘钩", "摘挂钩": "摘钩"}


def classify_case(c):
    """判断案例是否翻车机摘复钩同类、覆盖范围、是否含正钩。"""
    name = c["name"]
    is_related = bool(re.search(r"翻车|摘钩|复钩|正钩|摘复|摘挂|车厢|摘管|风管", name))
    scope = []
    if re.search(r"摘钩|摘复|摘挂|解列", name):
        scope.append("摘钩")
    if re.search(r"复钩|摘复|复列", name):
        scope.append("复钩")
    if re.search(r"正钩|摘复正|扶正", name):
        scope.append("正钩")
    if re.search(r"风管|摘管", name):
        scope.append("摘风管")
    has_zheng = "正钩" in scope
    return is_related, scope, has_zheng


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="素材文件或目录")
    ap.add_argument("-k", "--knowledge", required=True, help="素材库目录")
    args = ap.parse_args()
    inpath = Path(args.input)
    kdir = Path(args.knowledge)
    for sub in ("cases", "people", "credentials", "ip", "capability", "raw"):
        (kdir / sub).mkdir(parents=True, exist_ok=True)

    files = [inpath] if inpath.is_file() else sorted(inpath.glob("*.docx"))
    stats = {"cases": 0, "related": 0, "people": 0, "awards": 0, "patents": 0}
    gaps = []

    for f in files:
        if f.suffix.lower() != ".docx":
            print(f"跳过（非 docx）: {f.name}")
            continue
        print(f"解析: {f.name}")
        try:
            data = parse_zixin(f)
        except Exception as e:
            print(f"  解析失败: {e}")
            continue

        # 案例卡
        for c in data["cases"]:
            is_rel, scope, has_zheng = classify_case(c)
            cid = "case-" + slug(c["client"] + c["name"])
            card = {
                "id": cid, "type": "case", "name": c["name"],
                "client": c["client"], "contractor": c["contractor"],
                "sign_date": c["sign_date"], "amount_wan": "[待补]",
                "scope": scope, "has_正钩": has_zheng, "is_同类摘复钩": is_rel,
                "proof": [], "proof_status": "缺证明材料",
                "source": f.name,
                "tags": ([t for t in ["翻车机", "摘复钩", "电厂", "港口"] if True]) if is_rel else ["其他"],
            }
            if is_rel:
                (kdir / "cases" / f"{cid}.yaml").write_text(
                    yaml.safe_dump(card, allow_unicode=True, sort_keys=False), encoding="utf-8")
                stats["related"] += 1
                if c["sign_date"] >= "2021-07" and has_zheng:
                    gaps.append(f"案例「{c['name'][:20]}」({c['client'][:14]}) 缺金额与证明材料")
            stats["cases"] += 1

        # 人员卡
        for p in data["people"]:
            pid = "person-" + slug(p["name"])
            card = {
                "id": pid, "type": "person", "name": p["name"], "field": p["field"],
                "title": p["title"], "degree": "[待补]", "background": p["background"],
                "project_experience": "[待补]", "certs": "[待补]", "source": f.name,
                "tags": [t for t in ["电力", "3D感知", "机器人", "AI", "冶金", "视觉"] if t in p["field"] + p["background"]],
            }
            (kdir / "people" / f"{pid}.yaml").write_text(
                yaml.safe_dump(card, allow_unicode=True, sort_keys=False), encoding="utf-8")
            stats["people"] += 1
            if "高级工程师" in p["title"] or "高级" in p["title"]:
                gaps.append(f"人员「{p['name']}」({p['title']}) 缺学历/项目经历/证书")

        # 获奖
        for a in data["awards"]:
            stats["awards"] += 1
        # 专利
        for pt in data["patents"]:
            stats["patents"] += 1

        # 汇总类（获奖/专利/简介）覆盖写入
        if data["awards"]:
            (kdir / "credentials" / "awards.yaml").write_text(
                yaml.safe_dump({"awards": data["awards"], "source": f.name}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if data["patents"]:
            (kdir / "ip" / "patents.yaml").write_text(
                yaml.safe_dump({"patents": data["patents"], "source": f.name}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if data["intro"]:
            (kdir / "capability" / "company-intro.yaml").write_text(
                yaml.safe_dump({"intro": data["intro"], "source": f.name}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 重建索引
    index = {"cases": [], "people": []}
    for cf in sorted((kdir / "cases").glob("*.yaml")):
        c = yaml.safe_load(cf.read_text(encoding="utf-8"))
        index["cases"].append({"id": c["id"], "name": c["name"], "client": c["client"],
                               "sign_date": c["sign_date"], "scope": c["scope"],
                               "has_正钩": c["has_正钩"], "proof_status": c["proof_status"]})
    for pf in sorted((kdir / "people").glob("*.yaml")):
        p = yaml.safe_load(pf.read_text(encoding="utf-8"))
        index["people"].append({"id": p["id"], "name": p["name"], "field": p["field"], "title": p["title"]})
    (kdir / "index.yaml").write_text(
        yaml.safe_dump(index, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print()
    print(f"入库完成：案例 {stats['cases']}（同类摘复钩 {stats['related']}）、人员 {stats['people']}、获奖 {stats['awards']}、专利/软著 {stats['patents']}")
    print(f"索引: {kdir / 'index.yaml'}")
    if gaps:
        print(f"\n资格缺口提示（{len(gaps)} 条，需补证明材料）:")
        for g in gaps[:20]:
            print("  - " + g)


if __name__ == "__main__":
    main()
