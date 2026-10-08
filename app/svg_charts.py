# -*- coding: utf-8 -*-
"""解异模块的图表生成：时间线（从左到右）与鱼骨图（人机料法环）。

输出为内联 SVG 字符串：软件内用 QSvgRenderer 预览，导出 HTML 时直接嵌入，
不依赖任何第三方图表库，离线可用。中文直接写进 SVG，浏览器打开正常。
"""
import html
from datetime import datetime


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _wrap(text: str, width: int, max_lines: int = 4):
    """按显示宽度折行（中文按1字宽，ASCII按0.6字宽）。"""
    lines, cur, w = [], "", 0
    for ch in str(text):
        cw = 1.0 if ord(ch) > 0x2E80 else 0.6
        if w + cw > width or ch == "\n":
            lines.append(cur)
            cur, w = "", 0
            if ch == "\n":
                continue
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)] + "…"
    return lines or [""]


def timeline_svg(entries: list, title: str = "") -> str:
    """entries: [{time, event}]，按给定顺序从左到右排布。

    布局规则：
    - 宽度随条目数自适应（每条约230px），同侧相邻文字永不重叠；
    - 时间紧贴节点，事件文字向远离轴的方向堆叠（多行不会压到时间上）；
    - 无连接竖线（避免穿过文字）；事件超长自动折行，最多4行。
    """
    entries = [e for e in entries if (e.get("time") or e.get("event"))]
    n = len(entries)
    if n == 0:
        empty = ("有内容后这里会生成时间线")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="160" '
                f'viewBox="0 0 900 160"><rect width="900" height="160" fill="#0d1728"/>'
                f'<text x="450" y="84" text-anchor="middle" font-size="15" fill="#7d92ad" '
                f'font-family="Microsoft YaHei">{_esc(empty)}</text></svg>')

    margin = 120
    w = max(1100, min(3800, 230 * n + 160))
    step = (w - 2 * margin) / (n - 1) if n > 1 else 0

    # 折行宽度：同侧相邻节点间距的一半再留边（居中文字互不侵入）
    wrap_w = max(10, min(18, int((2 * step - 36) / 13)))
    blocks = [_wrap(str(e.get("event", "")).strip(), wrap_w, 4) for e in entries]
    max_lines = max(len(b) for b in blocks)

    line_h = 18
    time_gap = 32     # 轴到时间字的距离
    half_h = time_gap + 14 + max_lines * line_h
    h = half_h * 2 + 60 + (26 if title else 0)
    axis_y = h // 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="Microsoft YaHei, sans-serif">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        'orient="auto"><path d="M0,0 L9,3 L0,6 Z" fill="#29c6ff"/></marker></defs>',
        f'<rect width="{w}" height="{h}" fill="#0d1728"/>',
    ]
    if title:
        parts.append(
            f'<text x="{w / 2}" y="34" text-anchor="middle" font-size="20" '
            f'font-weight="bold" fill="#7adfff">{_esc(_wrap(title, 40)[0])}</text>')
    parts.append(
        f'<line x1="{margin - 50}" y1="{axis_y}" x2="{w - margin + 56}" y2="{axis_y}" '
        f'stroke="#29c6ff" stroke-width="3" marker-end="url(#arrow)"/>')

    for i, e in enumerate(entries):
        x = margin + i * step if n > 1 else w / 2
        up = (i % 2 == 0)
        lines = blocks[i]

        if up:
            time_y = axis_y - 18
            # 事件行堆在时间上方：最靠近时间的是第一行
            base = time_y - 14 - (len(lines) - 1) * line_h
            for j, ln in enumerate(lines):
                parts.append(f'<text x="{x:.0f}" y="{base + j * line_h}" text-anchor="middle" '
                             f'font-size="13" fill="#d7e3f4">{_esc(ln)}</text>')
        else:
            time_y = axis_y + 28
            base = time_y + 16
            for j, ln in enumerate(lines):
                parts.append(f'<text x="{x:.0f}" y="{base + j * line_h}" text-anchor="middle" '
                             f'font-size="13" fill="#d7e3f4">{_esc(ln)}</text>')

        parts.append(f'<text x="{x:.0f}" y="{time_y}" text-anchor="middle" font-size="14" '
                     f'font-weight="bold" fill="#ffd166">{_esc(str(e.get("time", "")).strip())}</text>')
        parts.append(f'<circle cx="{x:.0f}" cy="{axis_y}" r="7" fill="#0d1728" '
                     f'stroke="#29c6ff" stroke-width="3"/>')

    parts.append("</svg>")
    return "\n".join(parts)


_FISHBONE_CATS = ["人", "机", "料", "法", "环"]
_FISHBONE_EN = {"人": "Man", "机": "Machine", "料": "Material",
                "法": "Method", "环": "Environment"}


def fishbone_svg(categories: dict, problem: str = "") -> str:
    """categories: {人:[...], 机:[...], ...}；鱼头为问题描述。"""
    w, h = 1280, 640
    spine_y = h // 2 + 20
    x0, x1 = 60, 1060
    top_cats = ["人", "机", "料"]
    bot_cats = ["法", "环"]
    top_x = [300, 560, 820]
    bot_x = [430, 690]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="Microsoft YaHei, sans-serif">',
        f'<rect width="{w}" height="{h}" fill="#0d1728"/>',
        # 主骨
        f'<line x1="{x0}" y1="{spine_y}" x2="{x1}" y2="{spine_y}" '
        f'stroke="#29c6ff" stroke-width="4"/>',
        # 鱼头（问题描述）
        f'<polygon points="{x1},{spine_y - 52} {x1 + 150},{spine_y} {x1},{spine_y + 52}" '
        f'fill="#0b3a54" stroke="#29c6ff" stroke-width="2.5"/>',
    ]
    head_lines = _wrap(problem or "问题", 7, 3)
    hy = spine_y - (len(head_lines) - 1) * 12
    for j, ln in enumerate(head_lines):
        parts.append(f'<text x="{x1 + 55}" y="{hy + j * 24}" text-anchor="middle" '
                     f'font-size="14" font-weight="bold" fill="#e8fbff">{_esc(ln)}</text>')

    def bone(foot_x: float, up: bool, cat: str):
        sign = -1 if up else 1
        tip_y = spine_y + sign * 210
        tip_x = foot_x - 130
        parts.append(f'<line x1="{foot_x}" y1="{spine_y}" x2="{tip_x}" y2="{tip_y}" '
                     f'stroke="#7adfff" stroke-width="2.5"/>')
        # 类别标签框：上骨在尖端上方，下骨在尖端下方
        bw, bh = 74, 40
        box_y = tip_y - bh - 8 if up else tip_y + 8
        parts.append(f'<rect x="{tip_x - bw / 2}" y="{box_y}" '
                     f'width="{bw}" height="{bh}" rx="6" fill="#0b3a54" '
                     f'stroke="#29c6ff" stroke-width="2"/>')
        label_y = box_y + bh / 2 + 6
        parts.append(f'<text x="{tip_x}" y="{label_y}" text-anchor="middle" font-size="18" '
                     f'font-weight="bold" fill="#7adfff">{_esc(cat)}</text>')
        # 条目：沿鱼骨等分，短横刺 + 左侧文字
        items = [x for x in (categories or {}).get(cat, []) if str(x).strip()]
        for i, item in enumerate(items[:5]):
            f = (i + 1) / 6.0
            px = foot_x + (tip_x - foot_x) * f
            py = spine_y + (tip_y - spine_y) * f
            parts.append(f'<line x1="{px:.0f}" y1="{py:.0f}" x2="{px - 18:.0f}" '
                         f'y2="{py:.0f}" stroke="#3a5a85" stroke-width="1.6"/>')
            lines = _wrap(item, 13, 1)
            parts.append(f'<text x="{px - 24:.0f}" y="{py + 5:.0f}" text-anchor="end" '
                         f'font-size="13" fill="#d7e3f4">{_esc(lines[0])}</text>')

    for cat, fx in zip(top_cats, top_x):
        bone(fx, up=True, cat=cat)
    for cat, fx in zip(bot_cats, bot_x):
        bone(fx, up=False, cat=cat)

    # 底注
    parts.append(f'<text x="{x0}" y="{h - 18}" font-size="12" fill="#7d92ad">'
                 f'鱼骨图分析 · 人 Man / 机 Machine / 料 Material / 法 Method / 环 Environment</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def wrap_html(svg: str, title: str) -> str:
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title>"
        "<style>body{margin:0;background:#0d1728;display:flex;flex-direction:column;"
        "align-items:center;} h1{color:#7adfff;font-family:'Microsoft YaHei';font-size:18px;}"
        "svg{max-width:100%;height:auto;}</style></head><body>"
        f"<h1>{_esc(title)}</h1>{svg}</body></html>")
