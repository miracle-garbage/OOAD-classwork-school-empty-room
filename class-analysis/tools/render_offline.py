#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
类图渲染器：负责图 2 的「整理版分层布局」，兼作无 PlantUML / plantuml.jar 时的后备方案。

本脚本用纯 Python 生成 SVG，再调用本机 LibreOffice 把 SVG 转成 PNG，
用于在没有 Java + plantuml.jar、又不能联网的环境里产出图片。

规范来源仍然是 .puml 文件（class-diagram-domain.puml /
class-diagram-analysis.puml）；本脚本渲染的是同一份模型，仅排版取值不同。
其中图 2（分析类图）关系密集、跨层连线多，PlantUML 直出容易绞成一团，故这里
用「三带分层 + 正交折线 + 轨道分配」重新排版：连线走「源底部 → 专用轨道 →
目标顶部」，同轨水平段互不重叠、转角圆角化，读起来一条是一条。
"""

import html
import math
import os
import re
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


# ---------------------------------------------------------------------
# 图 2：分析类图（边界 / 控制 / 实体）—— 整理版分层布局
# ---------------------------------------------------------------------
# PlantUML 在缺少 Graphviz 的机器上会退化成内置布局，几十条跨层关系容易互相
# 缠绕。这里改用「三带分层 + 正交折线 + 轨道分配」的确定性排版重新出图：类与
# 关系同 class-diagram-analysis.puml 完全一致，只是排版更整齐——连线走
# 「源底部 → 专用轨道 → 目标顶部」，同一轨道上的水平段互不重叠、转角圆角化，
# 因此不再绞成一团。

CHIP_W = 150.0               # 分析类方块宽度
CHIP_GAP = 20.0              # 列间距
CHIP_PITCH = CHIP_W + CHIP_GAP
COL0 = 46.0                  # 第 0 列左边界
BAND_HEADER = 34.0           # 层标题条高度
TRACK_STEP = 12.0            # 走线轨道间距
EDGE_COLOR = "#566072"


def col_cx(col):
    """列号（可为小数）→ 该列中心 x。"""
    return COL0 + col * CHIP_PITCH + CHIP_W / 2.0


def assign_tracks(intervals):
    """区间着色：为每条水平走线分配轨道，同轨区间互不重叠。"""
    tracks = []                       # 每条轨道已占用的最右端
    res = [0] * len(intervals)
    for i in sorted(range(len(intervals)), key=lambda k: intervals[k][0]):
        lo, hi = intervals[i]
        for t, end in enumerate(tracks):
            if lo - end >= 8.0:
                tracks[t] = hi
                res[i] = t
                break
        else:
            tracks.append(hi)
            res[i] = len(tracks) - 1
    return res, len(tracks)


def rounded_path(pts, r=7.0):
    """正交折线 → 带圆角的 SVG path。"""
    pts = [pts[0]] + [p for k, p in enumerate(pts[1:], 1) if p != pts[k - 1]]
    if len(pts) < 2:
        return ""
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        rr = min(r, l1 / 2.0, l2 / 2.0)
        ax, ay = p1[0] - v1[0] / l1 * rr, p1[1] - v1[1] / l1 * rr
        bx, by = p1[0] + v2[0] / l2 * rr, p1[1] + v2[1] / l2 * rr
        d += f" L {ax:.1f} {ay:.1f} Q {p1[0]:.1f} {p1[1]:.1f} {bx:.1f} {by:.1f}"
    d += f" L {pts[-1][0]:.1f} {pts[-1][1]:.1f}"
    return d


class Chip:
    """分层图中的一个分析类方块（«stereotype» + 类名）。"""

    def __init__(self, cid, name, kind, col, row=0):
        self.id, self.name, self.kind, self.row = cid, name, kind, row
        self.x = col_cx(col)
        self.y = 0.0
        self.w = CHIP_W
        self.h = 49.0
        self.fs = 12.5
        self.lines = []

    @property
    def top(self):
        return self.y

    @property
    def bottom(self):
        return self.y + self.h

    def fit(self):
        """按“ / ”断行（过长再按字符断），必要时缩小字号，保证文字不出框。"""
        max_w = self.w - 18
        lines = []
        for seg in self.name.split("\n"):
            cur = ""
            for part in seg.split(" / "):
                cand = part if not cur else f"{cur} / {part}"
                if not cur or text_w(cand, self.fs) <= max_w:
                    cur = cand
                else:
                    lines.append(cur)
                    cur = part
            lines.append(cur)
        # 单段本身就超宽时按字符硬断，避免文字溢出方块
        wrapped = []
        for ln in lines:
            if text_w(ln, self.fs) <= max_w:
                wrapped.append(ln)
                continue
            piece = ""
            for ch in ln:
                if piece and text_w(piece + ch, self.fs) > max_w:
                    wrapped.append(piece)
                    piece = ch
                else:
                    piece += ch
            wrapped.append(piece)
        lines = wrapped
        widest = max(text_w(ln, self.fs) for ln in lines)
        if widest > max_w:
            self.fs = max(9.5, self.fs * max_w / widest)
        self.lines = lines
        self.h = 33.0 + 16.0 * len(lines)


def render_analysis_layered(boundary, row1, row2, entities, b2c, c2c, c2e,
                            out_base, title, legend_lines):
    """三带分层排版：边界（上）/ 控制（中，两行）/ 实体（下）。"""
    chips = {}
    for group, kind, row in ((boundary, "boundary", 0), (row1, "control", 1),
                             (row2, "control", 2), (entities, "entity", 3)):
        for item in group:
            cid, name, col = item[:3]
            chips[cid] = Chip(cid, name, kind, col, row=row)
            if len(item) > 3:                      # 个别长名字给更宽的方块
                chips[cid].w = item[3]
    for ch in chips.values():
        ch.fit()

    def route(edges):
        """为每条边确定出口 x、入口 x 与水平走线轨道号。"""
        outs, ins = {}, {}
        for s, t in edges:
            outs.setdefault(s, []).append(t)
            ins.setdefault(t, []).append(s)
        ex, en = {}, {}
        for s, ts in outs.items():
            ts = sorted(ts, key=lambda t: chips[t].x)
            half = chips[s].w / 2.0 - 14.0
            for i, t in enumerate(ts):
                ex[(s, t)] = chips[s].x + (0.0 if len(ts) == 1 else
                                           -half + 2 * half * i / (len(ts) - 1))
        for t, ss in ins.items():
            ss = sorted(ss, key=lambda s: chips[s].x)
            half = chips[t].w / 2.0 - 14.0
            for i, s in enumerate(ss):
                en[(s, t)] = chips[t].x + (0.0 if len(ss) == 1 else
                                           -half + 2 * half * i / (len(ss) - 1))
        ivs = [(min(ex[e], en[e]), max(ex[e], en[e])) for e in edges]
        tracks, ntr = assign_tracks(ivs)
        return {e: (ex[e], en[e], tracks[i]) for i, e in enumerate(edges)}, ntr

    r_b2c, n_b2c = route(b2c)
    r_c2c, n_c2c = route(c2c)
    r_c2e, n_c2e = route(c2e)

    pad = 18.0
    gap1_h = pad * 2 + n_b2c * TRACK_STEP
    rowgap_h = pad * 2 + n_c2c * TRACK_STEP
    gap2_h = pad * 2 + n_c2e * TRACK_STEP

    h_bnd = max(chips[c].h for c in (it[0] for it in boundary))
    h_r1 = max(chips[c].h for c in (it[0] for it in row1))
    h_r2 = max(chips[c].h for c in (it[0] for it in row2))
    h_ent = max(chips[c].h for c in (it[0] for it in entities))

    y_band1 = 64.0
    ch_top1 = y_band1 + BAND_HEADER + 14.0
    band1_bot = ch_top1 + h_bnd + 16.0
    y_band2 = band1_bot + gap1_h
    ch_top_r1 = y_band2 + BAND_HEADER + 14.0
    ch_top_r2 = ch_top_r1 + h_r1 + rowgap_h
    band2_bot = ch_top_r2 + h_r2 + 16.0
    y_band3 = band2_bot + gap2_h
    ch_top3 = y_band3 + BAND_HEADER + 14.0
    band3_bot = ch_top3 + h_ent + 16.0

    for cid in (it[0] for it in boundary):
        chips[cid].y = ch_top1
    for cid in (it[0] for it in row1):
        chips[cid].y = ch_top_r1
    for cid in (it[0] for it in row2):
        chips[cid].y = ch_top_r2
    for cid in (it[0] for it in entities):
        chips[cid].y = ch_top3

    band_x0 = COL0 - 26.0
    band_w = (len(entities) - 1) * CHIP_PITCH + CHIP_W + 52.0
    W = band_x0 + band_w + COL0
    H = band3_bot + 30.0 + len(legend_lines) * 17.0 + 20.0

    c = Canvas()

    def band(y, h, color, border, label):
        c.rect(band_x0, y, band_w, h, fill="#FFFFFF", stroke=border, sw=1.8, rx=8)
        c.add(f'<path d="M {band_x0 + 8:.1f} {y:.1f} '
              f'H {band_x0 + band_w - 8:.1f} Q {band_x0 + band_w:.1f} {y:.1f} '
              f'{band_x0 + band_w:.1f} {y + 8:.1f} V {y + BAND_HEADER:.1f} '
              f'H {band_x0:.1f} V {y + 8:.1f} Q {band_x0:.1f} {y:.1f} '
              f'{band_x0 + 8:.1f} {y:.1f} Z" fill="{color}" stroke="none"/>')
        c.text(band_x0 + band_w / 2, y + 23, label, fs=15.5, weight="bold",
               anchor="middle", color="#1F2937")

    band(y_band1, band1_bot - y_band1, "#EAF6EE", "#2F9E44",
         "边界类 Boundary（参与者与系统的交互入口）")
    band(y_band2, band2_bot - y_band2, "#FFF6E6", "#E8590C",
         "控制类 Control（用况的实现逻辑）")
    band(y_band3, band3_bot - y_band3, "#EDF2FF", "#3B5BDB",
         "实体类 Entity（业务数据与业务规则的载体）")

    def draw_group(routes, gap_top):
        for (s, t), (x1, x2, track) in routes.items():
            ty = gap_top + pad + track * TRACK_STEP
            y2 = chips[t].top
            pts = [(x1, chips[s].bottom), (x1, ty), (x2, ty), (x2, y2)]
            c.add(f'<path d="{rounded_path(pts)}" fill="none" stroke="{EDGE_COLOR}" '
                  f'stroke-width="1.25" stroke-linejoin="round"/>')
            c.add(f'<path d="M {x2 - 5:.1f} {y2 - 9:.1f} L {x2:.1f} {y2:.1f} '
                  f'L {x2 + 5:.1f} {y2 - 9:.1f}" fill="none" '
                  f'stroke="{EDGE_COLOR}" stroke-width="1.25" stroke-linecap="round"/>')

    draw_group(r_b2c, band1_bot)
    draw_group(r_c2c, ch_top_r1 + h_r1)
    draw_group(r_c2e, band2_bot)

    for ch in chips.values():
        fill, border, head = STYLE[ch.kind]
        c.rect(ch.x - ch.w / 2, ch.y, ch.w, ch.h, fill=fill, stroke=border,
               sw=1.3, rx=5)
        c.text(ch.x, ch.y + 15, f"«{ch.kind}»", fs=10.5, color=head,
               anchor="middle", style="italic")
        for i, ln in enumerate(ch.lines):
            c.text(ch.x, ch.y + 31 + i * 16, ln, fs=ch.fs, color="#1F2937",
                   anchor="middle", weight="bold")

    c.text(W / 2, 36, title, fs=19, weight="bold", anchor="middle", color="#1A1A1A")
    ly = band3_bot + 48.0
    for i, ln in enumerate(legend_lines):
        c.text(COL0, ly + i * 17, ln, fs=11.5, color="#495057")
    save(c.finish(W, H), out_base, png_width=3600)


def save(svg, out_base, png_width=None):
    """写出 SVG；再用 LibreOffice 转一张 PNG（可选指定像素宽度）。

    PNG 转换失败（例如沙箱 / 无 LibreOffice）只提示、不影响 SVG 产出。
    """
    os.makedirs(SVG_DIR, exist_ok=True)
    svg_path = os.path.join(SVG_DIR, out_base + ".svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    os.makedirs(PNG_DIR, exist_ok=True)
    filt = "png"
    if png_width:
        # LibreOffice 命令行默认把长边压到 2048px；宽、高都要显式给出（取值写成
        # 字符串）才能按目标分辨率导出，否则会自动缩到 2048 宽导致糊字。
        m = re.search(r'width="([0-9.]+)px"\s+height="([0-9.]+)px"', svg)
        ratio = (float(m.group(2)) / float(m.group(1))) if m else 0.34
        filt = ('png:draw_png_Export:{"PixelWidth":{"type":"long","value":"%d"},'
                '"PixelHeight":{"type":"long","value":"%d"}}'
                % (int(png_width), int(round(png_width * ratio))))
    try:
        subprocess.run(["soffice", "--headless", "--convert-to", filt,
                        "--outdir", PNG_DIR, svg_path],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("warn: soffice 转 PNG 失败（已保留 SVG）：", exc)
        print("wrote", svg_path)
        return
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
    # (id, 名称, 列号)：列号是 0 起算的浮点列，同一行内互不重叠。
    boundary = [
        ("B_Login", "登录界面", 1.2),
        ("B_Classroom", "教室管理界面", 2.4),
        ("B_Adapter", "外部适配器\n(认证 / 课表 / 消息 / 门禁)", 3.6, 196.0),
        ("B_Query", "空教室查询界面", 4.8),
        ("B_Admin", "用户 / 权限 / 统计管理界面", 6.0, 186.0),
        ("B_Reserve", "预约申请界面", 9.5),
        ("B_Approval", "预约审批界面", 11.0),
        ("B_MyCheckIn", "我的预约 / 签到界面", 12.6),
    ]
    control_row1 = [
        ("C_User", "用户与权限控制器", 0.0),
        ("C_Login", "登录控制器", 1.2),
        ("C_Classroom", "教室管理控制器", 2.4),
        ("C_Sync", "课表同步服务", 3.6),
        ("C_Query", "空教室查询控制器", 4.8),
        ("C_Stat", "统计报表控制器", 7.0),
        ("C_Release", "超时未签到释放任务", 9.3),
        ("C_Reserve", "预约控制器", 10.4),
        ("C_Approval", "审批控制器", 11.6),
        ("C_CheckIn", "签到控制器", 12.8),
    ]
    control_row2 = [
        ("C_Credit", "违约与信用控制器", 6.0),
        ("C_Validator", "预约规则校验器", 8.2),
        ("C_Notify", "通知服务", 14.0),
    ]
    entity = [
        ("E_User", "用户 / 学生 / 教师 /\n教室管理员 / 系统管理员\n教务管理人员", 0.0, 184.0),
        ("E_Role", "角色 / 权限", 1.0),
        ("E_Log", "登录日志", 2.0),
        ("E_Equip", "教室设备 /\n开放时间规则", 3.0),
        ("E_Classroom", "教室", 4.0),
        ("E_Schedule", "课表占用", 5.0),
        ("E_Reservation", "预约", 6.0),
        ("E_Credit", "信用信息", 7.0),
        ("E_Purpose", "用途类别", 8.0),
        ("E_Slot", "时段", 9.0),
        ("E_Violation", "违约记录", 10.0),
        ("E_Material", "证明材料", 11.0),
        ("E_Approval", "审批日志", 12.0),
        ("E_CheckIn", "签到记录", 13.0),
        ("E_Notify", "通知", 14.0),
    ]
    # 关系与 diagrams/class-diagram-analysis.puml 一一对应。
    boundary_to_control = [
        ("B_Login", "C_Login"),
        ("B_Query", "C_Query"),
        ("B_Reserve", "C_Reserve"),
        ("B_Reserve", "C_Validator"),
        ("B_MyCheckIn", "C_CheckIn"),
        ("B_MyCheckIn", "C_Reserve"),
        ("B_Approval", "C_Approval"),
        ("B_Classroom", "C_Classroom"),
        ("B_Admin", "C_User"),
        ("B_Admin", "C_Stat"),
        ("B_Admin", "C_Credit"),
        ("B_Adapter", "C_Login"),
        ("B_Adapter", "C_Sync"),
        ("B_Adapter", "C_Notify"),
    ]
    control_to_control = [
        ("C_Reserve", "C_Validator"),
        ("C_Reserve", "C_Notify"),
        ("C_Approval", "C_Notify"),
        ("C_Release", "C_Credit"),
        ("C_Release", "C_Notify"),
    ]
    control_to_entity = [
        ("C_Login", "E_User"),
        ("C_Login", "E_Role"),
        ("C_Login", "E_Log"),
        ("C_Query", "E_Classroom"),
        ("C_Query", "E_Schedule"),
        ("C_Query", "E_Reservation"),
        ("C_Reserve", "E_Reservation"),
        ("C_Validator", "E_Slot"),
        ("C_Validator", "E_Schedule"),
        ("C_Validator", "E_Credit"),
        ("C_Validator", "E_Purpose"),
        ("C_Approval", "E_Approval"),
        ("C_CheckIn", "E_CheckIn"),
        ("C_Release", "E_Violation"),
        ("C_Credit", "E_Credit"),
        ("C_Classroom", "E_Classroom"),
        ("C_Classroom", "E_Equip"),
        ("C_User", "E_User"),
        ("C_Sync", "E_Schedule"),
        ("C_Reserve", "E_Material"),
        ("C_Stat", "E_Reservation"),
        ("C_Notify", "E_Notify"),
    ]
    legend = [
        "«boundary» 边界类：参与者与系统交互的入口（界面 / 外部适配器）。",
        "«control» 控制类：承载用况的业务逻辑，协调实体类完成用例。",
        "«entity» 实体类：业务数据与业务规则；彼此关系（泛化 / 聚合 / 关联）见「图 1」。",
        "箭头方向 = 调用 / 使用方向：边界类 → 控制类 → 实体类。",
        "注：本图表达分层与「用况 → 类」的映射，非实体类之间的结构关系。",
    ]
    render_analysis_layered(boundary, control_row1, control_row2, entity,
                            boundary_to_control, control_to_control,
                            control_to_entity, "类图-分析类图",
                            "图 2  校园空教室预约管理系统 · 分析类图（边界类 / 控制类 / 实体类）",
                            legend)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "domain"):
        build_domain()
    if which in ("all", "analysis"):
        build_analysis()
