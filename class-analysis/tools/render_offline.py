#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线类图渲染器（无 PlantUML / plantuml.jar 时的后备方案）。

本脚本用纯 Python 生成 SVG，再调用本机 LibreOffice 把 SVG 转成 PNG，
用于在没有 Java + plantuml.jar、又不能联网的环境里产出图片。

规范来源仍然是 .puml 文件（class-diagram-domain.puml /
class-diagram-analysis.puml）；本脚本渲染的是同一份模型，仅排版取值不同。
"""

import html
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SVG_DIR = os.path.join(ROOT, "diagrams", "svg")
PNG_DIR = os.path.join(ROOT, "diagrams", "png")

FONT = "Noto Sans CJK SC, Microsoft YaHei, sans-serif"

STYLE = {
    "entity":  ("#EDF2FF", "#3B5BDB", "#1E3A8A"),
    "abstract": ("#E7ECFF", "#3B5BDB", "#1E3A8A"),
    "value":   ("#F3F0FF", "#6741D9", "#4C2E9E"),
    "enum":    ("#FFF0F6", "#C2255C", "#8B1A45"),
    "control": ("#FFF6E6", "#E8590C", "#8A3B08"),
    "boundary": ("#EAF6EE", "#2F9E44", "#1B6630"),
    "external": ("#F1F3F5", "#495057", "#212529"),
}


def esc(s):
    return html.escape(str(s), quote=True)


def text_w(s, fs):
    """粗略估算字符串像素宽度：CJK/全角按 1.0*fs，其余按 0.55*fs。"""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o >= 0x2E80:
            w += fs
        else:
            w += fs * 0.55
    return w


class Node:
    def __init__(self, nid, name, attrs=(), ops=(), stereo="", style="entity",
                 x=0, y=0, w=None, fix_h=None):
        self.id = nid
        self.name = name
        self.attrs = list(attrs)
        self.ops = list(ops)
        self.stereo = stereo
        self.style = style
        self.x, self.y = x, y
        self.name_fs = 15.0
        self.stereo_fs = 11.0
        self.mem_fs = 12.5
        self.lh = 19.0
        self.pad_l = 14.0
        self.pad_r = 14.0
        self.computed = False
        self.w = w
        self.h = fix_h

    def layout(self):
        fs = self.mem_fs
        w = text_w(self.name, self.name_fs) + 30
        if self.stereo:
            w = max(w, text_w(self.stereo, self.stereo_fs) + 30)
        for line in self.attrs + self.ops:
            w = max(w, text_w(line, fs) + self.pad_l + self.pad_r)
        header = 30.0 if not self.stereo else 46.0
        body = 0.0
        if self.attrs:
            body += len(self.attrs) * self.lh + 10
        if self.ops:
            body += len(self.ops) * self.lh + 10
        if self.w is None:
            self.w = max(w, 110)
        if self.h is None:
            self.h = header + body
        self.header_h = header
        self.computed = True

    @property
    def cx(self):
        return self.x + self.w / 2.0

    @property
    def cy(self):
        return self.y + self.h / 2.0


def border_point(node, tx, ty):
    cx, cy = node.cx, node.cy
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    sx = (node.w / 2.0) / abs(dx) if dx else float("inf")
    sy = (node.h / 2.0) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


def unit(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy)
    if d == 0:
        return (1.0, 0.0), 0.0
    return (dx / d, dy / d), d


class Canvas:
    def __init__(self):
        self.parts = []
        self.max_x = 0.0
        self.max_y = 0.0

    def add(self, s):
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, color="#495057", width=1.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{color}" stroke-width="{width}"{d}/>')

    def poly(self, pts, color="#495057", width=1.4, fill="none", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="{fill}" stroke="{color}" '
                 f'stroke-width="{width}"{d}/>')

    def text(self, x, y, s, fs=12.5, color="#212529", anchor="start",
             weight="normal", style="normal"):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
                 f'font-size="{fs}" fill="{color}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" font-style="{style}">{esc(s)}</text>')

    def rect(self, x, y, w, h, fill="none", stroke="#3B5BDB", sw=1.4, rx=3):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                 f'rx="{rx}" ry="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def polygon(self, pts, fill="#FFFFFF", stroke="#495057", sw=1.4):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def finish(self, w, h):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
                f'width="{w:.0f}px" height="{h:.0f}px" viewBox="0 0 {w:.0f} {h:.0f}">'
                f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="#FFFFFF"/>')
        return head + "".join(self.parts) + "</svg>"


def draw_node(c, n):
    fill, border, headtext = STYLE[n.style]
    c.rect(n.x, n.y, n.w, n.h, fill="#FFFFFF", stroke=border, sw=1.6, rx=4)
    c.add(f'<path d="M {n.x:.1f} {n.y + n.h:.1f} L {n.x:.1f} {n.y + 5:.1f} '
          f'Q {n.x:.1f} {n.y:.1f} {n.x + 5:.1f} {n.y:.1f} '
          f'L {n.x + n.w - 5:.1f} {n.y:.1f} Q {n.x + n.w:.1f} {n.y:.1f} '
          f'{n.x + n.w:.1f} {n.y + 5:.1f} L {n.x + n.w:.1f} {n.y + n.header_h:.1f} '
          f'L {n.x:.1f} {n.y + n.header_h:.1f} Z" fill="{fill}" stroke="none"/>')
    c.line(n.x, n.y + n.header_h, n.x + n.w, n.y + n.header_h, color=border, width=1.2)

    ys = n.y + 20
    name_style = "italic" if n.style in ("abstract",) else "normal"
    c.text(n.cx, ys, n.name, fs=n.name_fs, color=headtext, anchor="middle",
           weight="bold", style=name_style)
    if n.stereo:
        c.text(n.cx, ys + 17, n.stereo, fs=n.stereo_fs, color=headtext,
               anchor="middle", style="italic")

    cy = n.y + n.header_h
    if n.attrs:
        c.line(n.x, cy, n.x + n.w, cy, color=border, width=1.0)
        yy = cy + 16
        for a in n.attrs:
            c.text(n.x + n.pad_l, yy, a, fs=n.mem_fs)
            yy += n.lh
        cy += len(n.attrs) * n.lh + 10
    if n.ops:
        c.line(n.x, cy, n.x + n.w, cy, color=border, width=1.0)
        yy = cy + 16
        for o in n.ops:
            c.text(n.x + n.pad_l, yy, o, fs=n.mem_fs)
            yy += n.lh


def draw_edge(c, a, b, kind, mult_a="", mult_b="", label=""):
    ap = border_point(a, b.cx, b.cy)
    bp = border_point(b, a.cx, a.cy)
    u, dist = unit(ap[0], ap[1], bp[0], bp[1])
    ux, uy = u
    px, py = -uy, ux
    color = "#495057"
    dash = None

    if kind == "gen":
        # 空心三角，指向父类（b）
        L, W = 14, 8
        tip = (bp[0], bp[1])
        b1 = (bp[0] - ux * L + px * W, bp[1] - uy * L + py * W)
        b2 = (bp[0] - ux * L - px * W, bp[1] - uy * L - py * W)
        c.line(ap[0], ap[1], bp[0] - ux * L, bp[1] - uy * L, color=color, width=1.5)
        c.polygon([tip, b1, b2], fill="#FFFFFF", stroke=color, sw=1.5)
    else:
        if kind == "dep":
            dash = "6,4"
        c.line(ap[0], ap[1], bp[0], bp[1], color=color, width=1.4, dash=dash)
        if kind in ("comp", "aggr"):
            L, W = 20, 9
            fill = color if kind == "comp" else "#FFFFFF"
            d1 = (ap[0] + ux * (L / 2) + px * W / 2, ap[1] + uy * (L / 2) + py * W / 2)
            d2 = (ap[0] + ux * L, ap[1] + uy * L)
            d3 = (ap[0] + ux * (L / 2) - px * W / 2, ap[1] + uy * (L / 2) - py * W / 2)
            c.polygon([ap, d1, d2, d3], fill=fill, stroke=color, sw=1.4)
        elif kind == "arrow":
            L = 12
            c.line(bp[0], bp[1], bp[0] - ux * L + px * 6, bp[1] - uy * L + py * 6,
                   color=color, width=1.4)
            c.line(bp[0], bp[1], bp[0] - ux * L - px * 6, bp[1] - uy * L - py * 6,
                   color=color, width=1.4)

    off = 18
    def mult_label(txt, x, y):
        tw = text_w(txt, 11.5) + 6
        c.add(f'<rect x="{x - tw / 2:.1f}" y="{y - 9:.1f}" width="{tw:.1f}" '
              f'height="14" fill="#FFFFFF" opacity="0.92"/>')
        c.text(x, y, txt, fs=11.5, color="#343A40", anchor="middle")
    if mult_a:
        mult_label(mult_a, ap[0] + ux * off + px * 12, ap[1] + uy * off + py * 12 + 4)
    if mult_b:
        mult_label(mult_b, bp[0] - ux * off + px * 12, bp[1] - uy * off + py * 12 + 4)
    if label:
        mx, my = (ap[0] + bp[0]) / 2, (ap[1] + bp[1]) / 2
        wpx = text_w(label, 11.5) + 8
        c.add(f'<rect x="{mx - wpx / 2:.1f}" y="{my - 10:.1f}" width="{wpx:.1f}" '
              f'height="16" fill="#FFFFFF" opacity="0.92"/>')
        c.text(mx, my + 3, label, fs=11.5, color="#343A40", anchor="middle")


def render_domain(nodes, edges, out_base, title):
    for n in nodes.values():
        n.layout()
    c = Canvas()
    max_x = max(n.x + n.w for n in nodes.values())
    max_y = max(n.y + n.h for n in nodes.values())
    for a, b, kind, ma, mb, label in edges:
        draw_edge(c, nodes[a], nodes[b], kind, ma, mb, label)
    for n in nodes.values():
        draw_node(c, n)
    W, H = max_x + 60, max_y + 80
    c.text(W / 2, 34, title, fs=19, weight="bold", anchor="middle", color="#1A1A1A")
    save(c.finish(W, H), out_base)


def render_layered(pkgs, arrows, out_base, title, legend_lines):
    c = Canvas()
    x0, y0 = 40, 70
    width = 1180
    pkg_gap = 130
    chip_h = 40
    chip_gap = 14
    per_row = 4
    chip_w = (width - 60 - (per_row - 1) * chip_gap) / per_row
    y = y0
    centers = {}
    for pname, pcolor, pborder, chips in pkgs:
        cols = min(per_row, len(chips))
        rows = math.ceil(len(chips) / per_row)
        rows = max(rows, 1)
        h = 54 + rows * chip_h + (rows - 1) * chip_gap + 24
        c.rect(x0, y, width, h, fill="#FFFFFF", stroke=pborder, sw=1.8, rx=10)
        c.add(f'<rect x="{x0}" y="{y}" width="{width}" height="38" rx="10" ry="10" '
              f'fill="{pcolor}" stroke="none"/>')
        c.add(f'<rect x="{x0}" y="{y + 28}" width="{width}" height="10" '
              f'fill="{pcolor}" stroke="none"/>')
        c.text(x0 + 18, y + 26, pname, fs=15.5, weight="bold", color="#212529")
        centers[pname] = (x0 + width / 2, y, y + h)
        cy = y + 54
        for r in range(rows):
            for k in range(per_row):
                idx = r * per_row + k
                if idx >= len(chips):
                    break
                cx = x0 + 30 + k * (chip_w + chip_gap)
                c.rect(cx, cy, chip_w, chip_h, fill="#FFFFFF", stroke=pborder,
                       sw=1.0, rx=6)
                c.add(f'<rect x="{cx}" y="{cy}" width="{chip_w}" height="{chip_h}" '
                      f'rx="6" ry="6" fill="{pcolor}" opacity="0.45" stroke="none"/>')
                lines = chips[idx].split("\n")
                fs = 12.5
                longest = max(text_w(t, fs) for t in lines)
                if longest > chip_w - 14:
                    fs = max(9.0, fs * (chip_w - 14) / longest)
                lh = fs + 3
                y0 = cy + chip_h / 2 - (len(lines) - 1) * lh / 2 + fs * 0.36
                for j, t in enumerate(lines):
                    c.text(cx + chip_w / 2, y0 + j * lh, t, fs=fs,
                           anchor="middle", color="#212529")
            cy += chip_h + chip_gap
        y += h + pkg_gap
    # 层间箭头
    ys = sorted(centers.values(), key=lambda v: v[1])
    for i in range(len(ys) - 1):
        top_bottom = ys[i][2]
        bot_top = ys[i + 1][1]
        cx = (ys[i][0] + ys[i + 1][0]) / 2
        mid = (top_bottom + bot_top) / 2
        c.line(cx, top_bottom + 6, cx, mid - 6, color="#868E96", width=2.2)
        c.polygon([(cx, mid + 4), (cx - 7, mid - 8), (cx + 7, mid - 8)],
                  fill="#868E96", stroke="#868E96", sw=1.0)
    W = x0 + width + 40
    H = y + 20
    c.text(W / 2, 36, title, fs=19, weight="bold", anchor="middle", color="#1A1A1A")
    ly = y + 10
    for i, ln in enumerate(legend_lines):
        c.text(x0 + 4, ly + i * 17, ln, fs=11.5, color="#495057")
    save(c.finish(W, H + len(legend_lines) * 17 + 16), out_base)


def save(svg, out_base):
    os.makedirs(SVG_DIR, exist_ok=True)
    svg_path = os.path.join(SVG_DIR, out_base + ".svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    png_path = os.path.join(PNG_DIR, out_base + ".png")
    os.makedirs(PNG_DIR, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "png",
                    "--outdir", PNG_DIR, svg_path],
                   check=True, capture_output=True)
    # libreoffice 可能按 basename 输出，统一命名
    produced = os.path.join(PNG_DIR, out_base + ".png")
    if not os.path.exists(produced):
        cand = os.path.join(PNG_DIR, os.path.basename(svg_path) + ".png")
        if os.path.exists(cand):
            os.replace(cand, produced)
    print("wrote", svg_path, "->", produced)


# =====================================================================
# 图 1：领域实体类图
# =====================================================================
def build_domain():
    N = {}
    def node(nid, name, attrs=(), ops=(), stereo="", style="entity", x=0, y=0, w=None):
        N[nid] = Node(nid, name, attrs, ops, stereo, style, x, y, w)

    node("用户", "用户", [
        "# 用户编号 : String", "# 姓名 : String", "# 身份类型 : 身份类型",
        "# 所属院系 : String", "# 联系电话 : String", "# 账号状态 : 账号状态",
    ], ["+ 登录() : 会话"], stereo="«abstract»", style="abstract", x=560, y=70)
    node("预约用户", "预约用户", [], [
        "+ 查询空教室(条件) : 教室[]", "+ 提交预约(申请) : 预约",
        "+ 取消预约(预约号)", "+ 变更预约(预约号, 新时段)",
        "+ 查询我的预约() : 预约[]", "+ 签到(预约号) : 签到记录",
        "+ 是否受预约限制() : boolean",
    ], stereo="«abstract»", style="abstract", x=40, y=430)
    node("学生", "学生", x=90, y=770)
    node("教师", "教师", x=250, y=770)
    node("教室管理员", "教室管理员", [], [
        "+ 审批预约(预约号, 决定)", "+ 管理教室(教室)",
        "+ 管理违约与信用(用户)", "+ 查看统计() : 报表",
    ], x=470, y=430)
    node("系统管理员", "系统管理员", [], [
        "+ 维护用户与权限(用户, 角色)", "+ 配置系统参数()",
    ], x=880, y=430)
    node("教务管理人员", "教务管理人员", [], [
        "+ 查看统计报表() : 报表",
    ], x=1240, y=430)

    node("信用信息", "信用信息", [
        "- 违约累计 : int", "- 信用状态 : 信用状态",
        "- 限制起始 : DateTime", "- 限制截止 : DateTime",
    ], ["+ 记录违约(违约记录)", "+ 重算信用()", "+ 是否受限() : boolean"],
        x=40, y=900)
    node("角色", "角色", ["- 角色编号 : String", "- 角色名称 : String"],
        ["+ 分配权限(权限)"], x=470, y=930)
    node("权限", "权限", ["- 权限编号 : String", "- 权限码 : String",
        "- 资源 : String", "- 操作 : String"], x=470, y=1150)
    node("登录日志", "登录日志", ["- 日志号 : String", "- 登录时间 : DateTime",
        "- 来源IP : String", "- 结果 : String"], style="entity", x=470, y=1400)

    node("教室", "教室", [
        "- 教室编号 : String", "- 楼栋 : String", "- 房间号 : String",
        "- 容量 : int", "- 教室类型 : 教室类型", "- 状态 : 教室状态",
        "- 是否可预约 : boolean", "- 是否需审批 : boolean",
    ], ["+ 查询空闲时段(日期, 时段) : 时段[]", "+ 是否满足容量(人数) : boolean"],
        x=880, y=760)
    node("教室设备", "教室设备", ["- 设备编号 : String", "- 设备名称 : String",
        "- 设备类型 : String", "- 数量 : int"], x=880, y=1210)
    node("开放时间规则", "开放时间规则", ["- 规则号 : String", "- 生效学期 : String",
        "- 星期 : int", "- 是否可预约 : boolean"], x=1200, y=1210)
    node("时段", "时段", ["- 日期 : Date", "- 开始时间 : Time", "- 结束时间 : Time"],
        ["+ 时长() : Duration", "+ 是否重叠(其他) : boolean", "+ 是否合法() : boolean"],
        stereo="«值对象»", style="value", x=880, y=1490)
    node("课表占用", "课表占用", ["- 占用号 : String", "- 课程名称 : String",
        "- 任课教师 : String", "- 时段 : 时段"], x=1200, y=1490)

    node("预约", "预约", [
        "- 预约号 : String", "- 用途类别 : 用途类别", "- 使用人数 : int",
        "- 联系电话 : String", "- 状态 : 预约状态", "- 提交时间 : DateTime",
        "- 是否需审批 : boolean", "- 签到码 : String", "- 签到时间窗 : 时段",
    ], ["+ 提交() : 预约", "+ 校验可用性() : 校验结果", "+ 审批(决定)",
        "+ 取消()", "+ 变更(新教室, 新时段)", "+ 签到() : 签到记录",
        "+ 超时释放()", "+ 是否可取消() : boolean"], x=1560, y=760)
    node("用途类别", "用途类别", ["自习 / 小组讨论 / 补课", "答疑 / 会议 / 社团活动"],
        ["+ 是否需要审批() : boolean", "+ 是否需要材料() : boolean"], stereo="«enum»",
        style="enum", x=1560, y=1230)
    node("签到记录", "签到记录", ["- 记录号 : String", "- 签到时间 : DateTime",
        "- 签到方式 : 签到方式", "- 是否代签 : boolean", "- 代签操作人 : String"],
        x=1560, y=1500)
    node("审批日志", "审批日志", ["- 日志号 : String", "- 审批人 : String",
        "- 审批时间 : DateTime", "- 结论 : 审批结论", "- 理由 : String"],
        x=1900, y=760)
    node("违约记录", "违约记录", ["- 记录号 : String", "- 违约类型 : 违约类型",
        "- 发生时间 : DateTime", "- 是否撤销 : boolean"], x=1900, y=1080)
    node("证明材料", "证明材料", ["- 材料号 : String", "- 文件名 : String",
        "- 上传时间 : DateTime"], x=1900, y=1360)
    node("通知", "通知", ["- 通知号 : String", "- 通知类型 : 通知类型",
        "- 内容 : String", "- 渠道 : 渠道", "- 状态 : 发送状态"],
        x=1900, y=1610)

    edges = [
        ("用户", "预约用户", "gen", "", "", ""),
        ("用户", "教室管理员", "gen", "", "", ""),
        ("用户", "系统管理员", "gen", "", "", ""),
        ("用户", "教务管理人员", "gen", "", "", ""),
        ("预约用户", "学生", "gen", "", "", ""),
        ("预约用户", "教师", "gen", "", "", ""),
        ("用户", "角色", "assoc", "1..*", "0..*", "拥有"),
        ("角色", "权限", "assoc", "1..*", "0..*", "包含"),
        ("用户", "登录日志", "assoc", "1", "0..*", "产生"),
        ("信用信息", "预约用户", "assoc", "1", "1", "对应"),
        ("教室", "教室设备", "comp", "1", "0..*", "配置"),
        ("教室", "开放时间规则", "aggr", "1", "1..*", "遵循"),
        ("教室", "课表占用", "assoc", "1", "0..*", "被占用"),
        ("教室", "预约", "assoc", "1", "0..*", "被预约"),
        ("预约用户", "预约", "assoc", "1", "0..*", "提交"),
        ("预约", "时段", "assoc", "0..*", "1", "占用"),
        ("预约", "用途类别", "assoc", "0..*", "1", "分类"),
        ("预约", "证明材料", "assoc", "1", "0..*", "附有"),
        ("预约", "签到记录", "assoc", "1", "0..1", "对应"),
        ("预约", "审批日志", "assoc", "1", "0..*", "留有"),
        ("预约", "违约记录", "assoc", "1", "0..*", "触发"),
        ("预约用户", "违约记录", "assoc", "1", "0..*", "累计"),
        ("预约", "通知", "assoc", "1", "0..*", "触发"),
        ("课表占用", "时段", "assoc", "0..*", "1", "对应"),
        ("开放时间规则", "时段", "assoc", "0..*", "1", "定义"),
    ]
    render_domain(N, edges, "类图-领域实体类图",
                  "图 1  校园空教室预约管理系统 · 领域实体类图")


# =====================================================================
# 图 2：分析类图（边界 / 控制 / 实体）
# =====================================================================
def build_analysis():
    boundary = [
        "登录界面", "空教室查询界面", "预约申请界面", "我的预约 / 签到界面",
        "预约审批界面", "教室管理界面", "用户 / 权限 / 统计界面",
        "外部适配器\n(认证 / 课表 / 消息 / 门禁)",
    ]
    control = [
        "登录控制器", "空教室查询控制器", "预约控制器", "预约规则校验器",
        "审批控制器", "签到控制器", "超时未签到释放任务", "教室管理控制器",
        "违约与信用控制器", "用户与权限控制器", "统计报表控制器",
        "课表同步服务", "通知服务",
    ]
    entity = [
        "用户 / 学生 / 教师 /\n管理员 / 教务管理人员", "角色 / 权限", "信用信息",
        "教室", "教室设备 / 开放时间规则", "课表占用", "时段", "预约",
        "用途类别", "签到记录", "审批日志", "违约记录", "证明材料", "通知",
        "登录日志",
    ]
    pkgs = [
        ("边界类 Boundary（参与者与系统的交互入口）", "#EAF6EE", "#2F9E44", boundary),
        ("控制类 Control（用况的实现逻辑，一个控制类对应 1~2 个用况）", "#FFF6E6", "#E8590C", control),
        ("实体类 Entity（业务数据与业务规则的载体）", "#EDF2FF", "#3B5BDB", entity),
    ]
    legend = [
        "«boundary» 边界类：参与者与系统交互的入口（界面 / 外部适配器）。",
        "«control» 控制类：承载用况的业务逻辑，协调实体类完成用例。",
        "«entity» 实体类：业务数据与业务规则；彼此关系（泛化 / 聚合 / 关联）见「图 1」。",
        "箭头方向 = 调用 / 使用方向：边界类 → 控制类 → 实体类。",
        "注：本图表达分层与「用况 → 类」的映射，非实体类之间的结构关系。",
    ]
    render_layered(pkgs, None, "类图-分析类图",
                   "图 2  校园空教室预约管理系统 · 分析类图（边界 / 控制 / 实体）",
                   legend)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "domain"):
        build_domain()
    if which in ("all", "analysis"):
        build_analysis()
