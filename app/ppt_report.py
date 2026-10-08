# -*- coding: utf-8 -*-
"""解异模块的汇报PPT生成：单页、六要素框架、图片右栏、字号自适应。

框架（题目下方两栏/三行布局，有图片时右侧留图栏）：
  背景 What's the issue ｜ 影响 What's the impact ｜ 过往教训 Lesson learned before
  行动 Action done      ｜ 根因 Root cause        ｜ 预防/跟进 How to prevent / follow up

字号自适应：按各栏文字量估算行数，从14pt逐级降到8pt，取能全部放下的最大字号，
保证内容再多也不超出这一页。
"""
from datetime import datetime

SECTIONS = [
    ("背景", "What's the issue", "background"),
    ("影响", "What's the impact", "impact"),
    ("过往教训", "Lesson learned before", "lesson"),
    ("行动", "Action done", "actions"),
    ("根因", "Root cause", "root_cause"),
    ("预防/跟进", "How to prevent / follow up", "prevention"),
]

_HEAD_COLOR_A = "1F6FA8"


def _set_font(run, size=None, bold=None, color=None, name="Microsoft YaHei"):
    """设置字体（含中文 east-asian 字形，否则中文会回退到默认宋体）。"""
    from pptx.oxml.ns import qn

    run.font.name = name
    if size is not None:
        run.font.size = size
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        from lxml import etree
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", name)


def generate_ppt(anomaly: dict, image_paths: list, out_path: str) -> str:
    """anomaly: 解异记录；image_paths: 图片绝对路径列表（最多取3张）。返回 out_path。"""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

    accent = RGBColor(0x1F, 0x6F, 0xA8)
    accent2 = RGBColor(0x0E, 0x7C, 0x66)
    gray = RGBColor(0x88, 0x88, 0x88)

    # 顶部标题条
    tb = slide.shapes.add_textbox(Inches(0.35), Inches(0.18), Inches(12.6), Inches(0.75))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = str(anomaly.get("title") or "异常报告")
    _set_font(r, size=Pt(26), bold=True, color=accent)
    r2 = p.add_run()
    r2.text = f"    {datetime.now().strftime('%Y-%m-%d')}"
    _set_font(r2, size=Pt(13), color=gray)

    # 布局：有图片时文字占左 8.9in（两列×三行），右侧 3.9in 图片栏
    imgs = [p for p in image_paths if p][:3]
    text_w = 8.9 if imgs else 12.6
    col_w = text_w / 2 - 0.24
    row_h = 6.0 / 3 - 0.10

    body_runs = []
    for idx, (zh, en, key) in enumerate(SECTIONS):
        col, row = idx % 2, idx // 2
        left = Inches(0.35 + col * (col_w + 0.28))
        top = Inches(1.05 + row * (row_h + 0.10))
        box = slide.shapes.add_textbox(left, top, Inches(col_w), Inches(row_h))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = f"{zh} | {en}"
        _set_font(r, size=Pt(13), bold=True,
                  color=accent if idx % 2 == 0 else accent2)
        body = str(anomaly.get(key) or "").strip() or "（无）"
        p2 = tf.add_paragraph()
        rb = p2.add_run()
        rb.text = body
        body_runs.append((rb, col_w - 0.05, row_h - 0.42, body))

    # 字号自适应：所有栏取同一个能放下的最大字号（14 → 8）
    size_pt = 8
    for pt in range(14, 7, -1):
        ok = True
        for _, w_in, h_in, body in body_runs:
            flat = body.replace("\n", "")
            cpl = max(4, int(w_in / (pt / 72.0)))
            lines = max(1, -(-len(flat) // cpl)) + body.count("\n")
            if lines * (pt * 1.32 / 72.0) > h_in:
                ok = False
                break
        if ok:
            size_pt = pt
            break
    for r, _, _, _ in body_runs:
        r.font.size = Pt(size_pt)

    # 图片栏：按原始宽高比缩放进 3.85in × 均分高度 的格子里，不变形
    if imgs:
        from PIL import Image
        img_x = 0.35 + text_w + 0.25
        box_w, box_h = 3.85, 6.0 / len(imgs) - 0.12
        for i, path in enumerate(imgs):
            try:
                with Image.open(path) as im:
                    iw, ih = im.size
                scale = min(box_w / iw * 72, box_h / ih * 72)  # px→pt→in 统一按比例
                w_in, h_in = iw * scale / 72, ih * scale / 72
                left = img_x + (box_w - w_in) / 2
                top = 1.05 + i * (6.0 / len(imgs)) + (6.0 / len(imgs) - h_in) / 2
                slide.shapes.add_picture(path, Inches(left), Inches(top),
                                         Inches(w_in), Inches(h_in))
            except Exception:
                continue  # 单张图坏不影响整页生成

    # 页脚
    ft = slide.shapes.add_textbox(Inches(0.35), Inches(7.1), Inches(12.6), Inches(0.32))
    p = ft.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "贾维斯 · 解异 | One-page anomaly report"
    _set_font(r, size=Pt(9), color=gray)

    prs.save(out_path)
    return out_path
