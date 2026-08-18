#!/usr/bin/env python3
"""bid-draft 配图脚本：matplotlib 生成技术标书示意图（中文、风格统一）。

图型注册表 FIGS：architecture 架构图、deployment 部署图、gantt 甘特图、
flowchart 识别作业流程图、interlock 安全联锁逻辑图、topology 网络拓扑图。
统一风格：SimHei 字体、蓝灰配色、圆角框 + 箭头。
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from matplotlib import font_manager

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

# 统一配色
C_BOX = "#2E5A88"      # 主框蓝
C_BOX2 = "#3D7AB5"     # 次框蓝
C_LIGHT = "#EAF1F8"    # 浅底
C_ACCENT = "#C0504D"   # 强调红
C_GREEN = "#4F7A5B"    # 绿
C_GRAY = "#666666"


def box(ax, x, y, w, h, text, fc=C_LIGHT, ec=C_BOX, fs=11, bold=False, tc="#1a1a1a"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                       linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", zorder=3, wrap=True)


def arrow(ax, x1, y1, x2, y2, color=C_BOX, style="-|>", lw=1.6):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                        lw=lw, color=color, zorder=1)
    ax.add_patch(a)


def diamond(ax, cx, cy, w, h, text, fc="#FDF2F2", ec=C_ACCENT, fs=10):
    """判断节点（菱形）。坐标为中心点。"""
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    p = Polygon(pts, closed=True, linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=2)
    ax.add_patch(p)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color="#1a1a1a", zorder=3)


def zone(ax, x, y, w, h, label, fc="#FAFBFD", ec="#B8C4D0"):
    """分区背景框（虚线，用于拓扑图分层）。"""
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.08",
                       linewidth=1.2, edgecolor=ec, facecolor=fc,
                       linestyle="--", zorder=0)
    ax.add_patch(p)
    ax.text(x + 0.18, y + h - 0.32, label, fontsize=11, color=C_GRAY, fontweight="bold")


def new_ax(w=10, h=7):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    return fig, ax


def save(fig, out, title):
    ax = fig.axes[0]
    ax.set_title(title, fontsize=16, fontweight="bold", color=C_BOX, pad=14)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  生成: {out}")


# ============ 1. 系统架构图（四层） ============
def fig_architecture(out):
    fig, ax = new_ax(10, 7.5)
    layers = [
        ("监控层", "人机界面HMI · 视频监控 · 声光报警 · 远端集控显示 · 语音播报", C_ACCENT),
        ("决策层", "工控机/服务器 · 智能识别算法 · 运动规划控制 · 3D感知决策", C_BOX),
        ("执行层", "摘钩机器人 · 复钩机器人 · 正钩机器人\n（多轴机械臂+直线运动装置+末端执行器）", C_GREEN),
        ("感知层", "车型识别 · 风管检测 · 工业视觉 · 智能感知\n（3D激光雷达 · 高清相机 · 力/力矩传感）", C_BOX2),
    ]
    y = 8.6
    for name, content, color in layers:
        box(ax, 0.6, y, 1.8, 1.5, name, fc=color, ec=color, fs=14, bold=True, tc="white")
        box(ax, 2.7, y, 6.7, 1.5, content, fc=C_LIGHT, ec=color, fs=10.5)
        y -= 2.0
    # 层间箭头（双向）
    for yy in [8.6, 6.6, 4.6]:
        arrow(ax, 4.6, yy, 4.6, yy - 0.5, color=C_GRAY, style="<|-|>", lw=1.4)
    ax.text(5, 0.3, "感知—决策—执行—监控 四层闭环架构", ha="center", fontsize=11,
            style="italic", color=C_GRAY)
    save(fig, out, "智能解复列机器人系统总体架构图")


# ============ 2. 部署示意图 ============
def fig_deployment(out):
    fig, ax = new_ax(11, 6)
    # 轨道
    ax.plot([0.5, 9.5], [3.2, 3.2], color="#333", lw=3, zorder=1)
    ax.text(5, 2.9, "铁路线", ha="center", fontsize=9, color="#333")
    # 重车线 → 翻车机 → 空车线
    box(ax, 0.7, 5.2, 2.4, 1.6, "重车线\n摘钩机器人", fc=C_LIGHT, ec=C_BOX, fs=11, bold=True)
    box(ax, 3.9, 5.2, 2.4, 1.6, "翻车机\n正钩机器人", fc=C_LIGHT, ec=C_GREEN, fs=11, bold=True)
    box(ax, 7.1, 5.2, 2.4, 1.6, "空车线\n复钩机器人", fc=C_LIGHT, ec=C_ACCENT, fs=11, bold=True)
    arrow(ax, 3.1, 6.0, 3.9, 6.0); arrow(ax, 6.3, 6.0, 7.1, 6.0)
    # 感知系统
    box(ax, 2.5, 8.0, 5.0, 1.2, "车型识别 · 工业视觉 · 智能感知系统（全程覆盖）",
        fc="#FFF4E5", ec="#C88A2D", fs=10.5, bold=True)
    for x in [1.9, 5.1, 8.3]:
        arrow(ax, 5.0, 8.0, x, 6.8, color="#C88A2D", style="-|>", lw=1.2)
    # 控制/联锁
    box(ax, 2.5, 0.6, 5.0, 1.2, "工控机/服务器 + PLC + DCS联锁（硬线）",
        fc="#EFEFEF", ec=C_GRAY, fs=10.5, bold=True)
    for x in [1.9, 5.1, 8.3]:
        arrow(ax, x, 5.2, 5.0, 1.8, color=C_GRAY, style="-|>", lw=1.1)
    save(fig, out, "智能解复列机器人系统部署示意图")


# ============ 3. 进度甘特图 ============
def fig_gantt(out):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    stages = [
        ("研发设计阶段", 1, 8, C_BOX),
        ("生产制造阶段", 7, 14, C_BOX2),
        ("现场安装调试阶段", 13, 20, C_GREEN),
        ("最终验证阶段", 21, 22, "#C88A2D"),
        ("结题验收阶段", 23, 24, C_ACCENT),
    ]
    for i, (name, s, e, c) in enumerate(stages):
        ax.barh(len(stages) - 1 - i, e - s, left=s, height=0.55, color=c,
                edgecolor="white", alpha=0.9)
        ax.text((s + e) / 2, len(stages) - 1 - i, f"{name}\n{s}-{e}月",
                ha="center", va="center", fontsize=9.5, color="white", fontweight="bold")
    # 里程碑
    miles = [(1, "M1\n研发计划"), (15, "M3\n设备供货\n30%"), (20, "M4\n安装调试"),
             (22, "M5\n验证"), (24, "M6\n最终验收\n90%")]
    for x, lab in miles:
        ax.axvline(x, color=C_GRAY, ls="--", lw=1, alpha=0.6)
        ax.text(x, len(stages) - 0.3, lab, ha="center", va="bottom", fontsize=7.5, color=C_ACCENT)
    ax.set_xlim(0, 25); ax.set_ylim(-0.6, len(stages) + 0.6)
    ax.set_yticks([]); ax.set_xlabel("月（自合同签订起）", fontsize=11)
    ax.set_xticks(range(0, 25, 2))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_title("项目 24 个月总体进度甘特图", fontsize=15, fontweight="bold", color=C_BOX, pad=16)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  生成: {out}")


# ============ 4. 识别作业流程图 ============
def fig_flowchart(out):
    fig, ax = new_ax(10, 9)
    X, W, H = 3.3, 3.4, 0.85  # 主干列
    steps = [
        (9.1, "列车到位（拨车机定位到位信号）"),
        (8.0, "车型识别（相机 + 激光扫描）"),
        (6.9, "风管状态识别"),
    ]
    for y, t in steps:
        box(ax, X, y, W, H, t)
    # 判断1：状态正常？
    diamond(ax, 5.0, 5.75, 3.4, 1.3, "车型/风管\n状态正常？")
    box(ax, 7.6, 5.35, 2.2, 0.85, "报警并闭锁\n人工介入处理", fc="#FDF2F2", ec=C_ACCENT, fs=9)
    arrow(ax, 6.7, 5.75, 7.6, 5.78, color=C_ACCENT)
    ax.text(7.0, 5.95, "否", fontsize=9, color=C_ACCENT)
    # 中段
    for y, t in [(4.55, "3D 视觉定位车钩（点云）"), (3.45, "作业轨迹规划与避障校验"),
                 (2.35, "摘钩/复钩/正钩作业（力控）")]:
        box(ax, X, y, W, H, t)
    # 判断2：分离确认？
    diamond(ax, 5.0, 1.2, 3.4, 1.3, "车厢分离\n确认？")
    box(ax, 7.6, 0.8, 2.2, 0.85, "自动重试≤2次\n仍失败转报警", fc="#FDF6E8", ec="#C88A2D", fs=9)
    arrow(ax, 6.7, 1.2, 7.6, 1.23, color="#C88A2D")
    ax.text(7.0, 1.4, "否", fontsize=9, color="#C88A2D")
    # 重试回路：回到 3D 定位
    ax.plot([9.6, 9.85, 9.85, 5.0], [0.8, 0.8, 4.98, 4.98], color="#C88A2D", lw=1.2, ls="--", zorder=1)
    arrow(ax, 5.6, 4.98, 5.2, 4.98, color="#C88A2D", lw=1.2)
    box(ax, 1.0, 0.6, 2.0, 0.85, "完成\n机器人退位复位", fc="#EDF5EF", ec=C_GREEN, fs=9, bold=True)
    arrow(ax, 3.3, 1.2, 3.0, 1.03, color=C_GREEN)
    ax.text(3.35, 1.42, "是", fontsize=9, color=C_GREEN)
    # 主干箭头（起止坐标手工校准）
    for (y1, y2) in [(8.78, 8.0), (7.68, 6.9), (6.58, 6.4), (5.1, 4.98), (4.1, 3.45), (3.0, 2.35), (1.9, 1.72)]:
        arrow(ax, 5.0, y1, 5.0, y2)
    ax.text(5.15, 6.15, "是", fontsize=9, color=C_GREEN)
    ax.text(5.15, 1.85, "是", fontsize=9, color=C_GREEN)
    ax.text(5, 0.15, "感知 → 决策 → 执行 → 确认 全流程闭环（识别成功率 ≥99%，摘/复/正钩成功率 ≥97%）",
            ha="center", fontsize=10, style="italic", color=C_GRAY)
    save(fig, out, "感知识别与摘钩作业流程图")


# ============ 5. 安全联锁逻辑图 ============
def fig_interlock(out):
    fig, ax = new_ax(11, 7.5)
    conds = [
        (7.9, "拨车机到位且速度匹配"),
        (6.8, "夹轮器夹紧状态确认"),
        (5.7, "车钩闭合/打开状态确认"),
        (4.6, "作业区域无人员侵入"),
        (3.5, "急停回路正常（未触发）"),
    ]
    for y, t in conds:
        box(ax, 0.4, y, 3.0, 0.8, t, fc="#EDF5EF", ec=C_GREEN, fs=10)
        arrow(ax, 3.4, y + 0.4, 4.3, 5.3 if y > 5.4 else 5.3, color=C_GREEN, lw=1.2)
    # AND 汇聚框
    box(ax, 4.3, 4.2, 2.1, 2.2, "安全联锁条件\n全部满足\n（AND）", fc=C_LIGHT, ec=C_BOX, fs=11, bold=True)
    box(ax, 7.1, 4.5, 2.6, 1.6, "允许机器人作业\n（摘/复/正钩）", fc=C_BOX, ec=C_BOX,
        fs=11, bold=True, tc="white")
    arrow(ax, 6.4, 5.3, 7.1, 5.3, lw=2)
    ax.text(6.55, 5.5, "允许", fontsize=9, color=C_BOX)
    # 危险检测支路（OR → 停机）
    box(ax, 0.4, 1.0, 3.6, 1.3, "危险检测（任一即触发 OR）：\n障碍侵入 · 机械臂超限 · 通讯中断",
        fc="#FDF2F2", ec=C_ACCENT, fs=9.5)
    box(ax, 4.6, 1.15, 2.6, 1.0, "立即停机\n声光报警", fc=C_ACCENT, ec=C_ACCENT, fs=10.5, bold=True, tc="white")
    box(ax, 7.8, 1.15, 2.1, 1.0, "严重危险：硬线联动\n停止翻车机作业", fc="#FDF2F2", ec=C_ACCENT, fs=9, bold=True)
    arrow(ax, 4.0, 1.65, 4.6, 1.65, color=C_ACCENT, lw=2)
    arrow(ax, 7.2, 1.65, 7.8, 1.65, color=C_ACCENT, lw=2)
    # 作业允许框到停机框的抑制关系
    arrow(ax, 8.4, 4.5, 8.85, 2.15, color=C_ACCENT, style="-|>", lw=1.2)
    ax.text(9.0, 3.3, "条件失效\n即撤销允许", fontsize=8.5, color=C_ACCENT, ha="center")
    ax.text(5.5, 0.25, "联锁交互信号全部采用硬线接入（不经通讯网络），隐患未排除前翻车机控制系统暂停相关作业",
            ha="center", fontsize=10, style="italic", color=C_GRAY)
    save(fig, out, "机器人与翻车机系统安全联锁逻辑图")


# ============ 6. 网络拓扑图 ============
def fig_topology(out):
    fig, ax = new_ax(11, 8)
    # 分区
    zone(ax, 0.3, 5.3, 9.4, 3.4, "控制室层（管理网）")
    zone(ax, 0.3, 0.5, 9.4, 3.6, "现场层（工业以太网）")
    # 控制室设备
    for x, t in [(0.7, "操作员站\nHMI"), (3.0, "工程师站\n（调试/维护）"),
                 (5.3, "算法服务器\n（识别/规划）"), (7.6, "视频监控\n工作站")]:
        box(ax, x, 7.2, 1.9, 1.1, t, fs=9.5)
    box(ax, 3.4, 5.7, 3.2, 1.0, "核心交换机", fc=C_BOX, ec=C_BOX, fs=12, bold=True, tc="white")
    # 设备→汇流线→核心交换机（折线）
    for x in [1.65, 3.95, 6.25, 8.55]:
        ax.plot([x, x], [7.2, 6.7], color=C_GRAY, lw=1.3, zorder=1)
    ax.plot([1.65, 8.55], [6.7, 6.7], color=C_GRAY, lw=1.3, zorder=1)
    ax.plot([5.0, 5.0], [6.7, 5.7], color=C_GRAY, lw=1.6, zorder=1)
    # 现场层
    box(ax, 3.4, 2.9, 3.2, 1.0, "现场交换机（环网）", fc=C_BOX2, ec=C_BOX2, fs=11, bold=True, tc="white")
    ax.plot([5.0, 5.0], [5.7, 3.9], color=C_GRAY, lw=1.8, zorder=1)
    ax.text(5.25, 4.7, "光纤环网", fontsize=9, color=C_GRAY)
    devs = [
        (0.6, "机器人控制器\n摘钩×4 / 复钩×4 / 正钩×4"),
        (3.1, "PLC 控制柜\n（伺服/安全回路）"),
        (5.6, "车型识别相机×4\n3D 激光雷达"),
        (7.9, "风管检测\n声光报警/急停"),
    ]
    for x, t in devs:
        box(ax, x, 1.0, 2.1, 1.2, t, fs=9)
        ax.plot([x + 1.05, x + 1.05], [2.2, 3.4], color=C_GRAY, lw=1.3, zorder=1)
        ax.plot([x + 1.05, 5.0], [3.4, 3.4], color=C_GRAY, lw=1.3, zorder=1)
    # DCS 硬线联锁（右侧独立）
    box(ax, 8.15, 5.9, 1.7, 1.4, "电厂 DCS\n系统", fc="#FDF6E8", ec="#C88A2D", fs=10.5, bold=True)
    ax.plot([9.0, 9.0], [5.9, 2.2], color=C_ACCENT, lw=2, ls="--", zorder=1)
    ax.plot([9.0, 9.6], [2.2, 2.2], color=C_ACCENT, lw=2, ls="--", zorder=1)
    ax.plot([9.0, 8.4], [2.2, 2.2], color=C_ACCENT, lw=2, ls="--", zorder=1)
    ax.text(9.35, 4.0, "安全联锁\n信号（硬线）", fontsize=8.5, color=C_ACCENT, ha="center", rotation=90)
    ax.text(5.5, 0.12, "管理网与现场层物理隔离，DCS 联锁信号独立硬线直连（不经网络，详见 2.6 节）",
            ha="center", fontsize=10, style="italic", color=C_GRAY)
    save(fig, out, "系统网络拓扑结构图")


FIGS = {
    "architecture": fig_architecture,
    "deployment": fig_deployment,
    "gantt": fig_gantt,
    "flowchart": fig_flowchart,
    "interlock": fig_interlock,
    "topology": fig_topology,
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--outdir", required=True, help="figures 输出目录")
    ap.add_argument("--only", default=None, help="只画某张（architecture/deployment/gantt/flowchart/interlock/topology）")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    todo = {args.only: FIGS[args.only]} if args.only else FIGS
    for name, fn in todo.items():
        fn(outdir / f"{name}.png")


if __name__ == "__main__":
    main()
