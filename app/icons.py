# -*- coding: utf-8 -*-
"""程序内图标：全部用 QPainter 现场绘制，不依赖外部图片文件。

侧边栏图标 / 应用窗口图标。若 assets/jarvis.ico 存在则窗口图标用ico文件。
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
                           QFont, QLinearGradient, QRadialGradient)

from . import common

ACCENT = QColor("#29c6ff")
DIM = QColor("#7d92ad")


def _painter(pix: QPixmap) -> QPainter:
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    return p


def _icon_from(draw_fn) -> QIcon:
    icon = QIcon()
    for size in (48, 32, 24, 20, 16):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = _painter(pix)
        draw_fn(p, QRectF(0, 0, size, size))
        p.end()
        icon.addPixmap(pix)
    return icon


def nav_icon(kind: str) -> QIcon:
    """侧边栏模块图标：kind = tasks/memo/qa/knowledge"""
    return _icon_from(lambda p, r: _draw_nav(p, r, kind))


def _pen(p: QPainter, color, width, rect):
    scale = rect.width() / 24.0
    pen = QPen(color, max(1.4, width * scale))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


def _draw_nav(p: QPainter, rect: QRectF, kind: str):
    p.scale(rect.width() / 24.0, rect.height() / 24.0)
    c = ACCENT

    if kind == "tasks":  # 缓急：闪电
        _pen(p, c, 1.6, rect)
        path = QPainterPath()
        path.moveTo(13.5, 2.5)
        path.lineTo(6.0, 13.5)
        path.lineTo(11.0, 13.5)
        path.lineTo(10.0, 21.5)
        path.lineTo(18.0, 10.0)
        path.lineTo(12.8, 10.0)
        path.lineTo(13.5, 2.5)
        p.setBrush(QColor(41, 198, 255, 60))
        p.drawPath(path)

    elif kind == "memo":  # 帮记：便签+笔
        _pen(p, DIM, 1.6, rect)
        p.drawRoundedRect(QRectF(4, 3.5, 13, 17), 2, 2)
        for y in (8, 12):
            p.drawLine(QPointF(7, y), QPointF(14, y))
        p.drawLine(QPointF(7, 16), QPointF(11, 16))
        _pen(p, c, 1.8, rect)
        p.drawLine(QPointF(13.5, 16.5), QPointF(20, 10))
        p.drawLine(QPointF(20, 10), QPointF(18.2, 8.2))
        p.drawLine(QPointF(18.2, 8.2), QPointF(11.7, 14.7))

    elif kind == "qa":  # 解惑：问号
        _pen(p, c, 1.8, rect)
        path = QPainterPath()
        path.moveTo(7.5, 8.5)
        path.cubicTo(7.5, 4.5, 16.5, 4.5, 16.5, 8.8)
        path.cubicTo(16.5, 11.8, 12.2, 12.0, 12.2, 15.5)
        p.drawPath(path)
        p.drawEllipse(QPointF(12.2, 19.4), 0.4, 0.4)

    elif kind == "knowledge":  # 存知：书本/档案
        _pen(p, DIM, 1.6, rect)
        p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2, 2)
        p.drawLine(QPointF(8.5, 3.5), QPointF(8.5, 20.5))
        _pen(p, c, 1.6, rect)
        for y in (8, 11.5, 15):
            p.drawLine(QPointF(11.5, y), QPointF(17.5, y))

    elif kind == "anomaly":  # 解异：警告三角
        _pen(p, c, 1.6, rect)
        path = QPainterPath()
        path.moveTo(12, 3.5)
        path.lineTo(21, 19.5)
        path.lineTo(3, 19.5)
        path.closeSubpath()
        p.setBrush(QColor(41, 198, 255, 50))
        p.drawPath(path)
        _pen(p, c, 2.0, rect)
        p.drawLine(QPointF(12, 9), QPointF(12, 14))
        p.drawEllipse(QPointF(12, 17), 0.4, 0.4)

    elif kind == "weekly":  # 周报：日历
        _pen(p, DIM, 1.6, rect)
        p.drawRoundedRect(QRectF(3.5, 5, 17, 15.5), 2, 2)
        p.drawLine(QPointF(3.5, 9.5), QPointF(20.5, 9.5))
        _pen(p, c, 1.6, rect)
        p.drawLine(QPointF(8, 3), QPointF(8, 6.5))
        p.drawLine(QPointF(16, 3), QPointF(16, 6.5))
        for x in (7.5, 11, 14.5):
            p.drawLine(QPointF(x, 13), QPointF(x, 13))
        _pen(p, c, 1.8, rect)
        p.drawLine(QPointF(7.5, 16), QPointF(9.5, 18))
        p.drawLine(QPointF(9.5, 18), QPointF(13.5, 13.5))

    elif kind == "trash":  # 回收站：垃圾桶
        _pen(p, DIM, 1.6, rect)
        p.drawRoundedRect(QRectF(6, 7, 12, 13.5), 2, 2)
        p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
        p.drawLine(QPointF(9.5, 4.5), QPointF(14.5, 4.5))
        _pen(p, c, 1.6, rect)
        p.drawLine(QPointF(10, 10), QPointF(10, 17.5))
        p.drawLine(QPointF(14, 10), QPointF(14, 17.5))


def search_icon() -> QIcon:
    def draw(p, rect):
        p.scale(rect.width() / 24.0, rect.height() / 24.0)
        _pen(p, DIM, 2.0, rect)
        p.drawEllipse(QPointF(10.5, 10.5), 6.0, 6.0)
        p.drawLine(QPointF(15.2, 15.2), QPointF(20.5, 20.5))
    return _icon_from(draw)


def app_icon() -> QIcon:
    """窗口图标：优先用打包好的 assets/jarvis.ico。"""
    import os
    ico = common.res_path(os.path.join("assets", "jarvis.ico"))
    if os.path.exists(ico):
        return QIcon(ico)
    icon = QIcon()
    for size in (256, 128, 64, 48, 32, 16):
        icon.addPixmap(draw_logo_pixmap(size))
    return icon


def draw_logo_pixmap(size: int) -> QPixmap:
    """绘制贾维斯Logo：深空圆盘 + HUD环 + 反应堆三角核心。"""
    s = max(size, 64)  # 先画大图再缩放，保证小尺寸抗锯齿
    pix = QPixmap(s, s)
    pix.fill(Qt.transparent)
    p = _painter(pix)
    w = s

    # 底盘径向渐变
    grad = QRadialGradient(w * 0.5, w * 0.46, w * 0.5)
    grad.setColorAt(0.0, QColor("#12365c"))
    grad.setColorAt(0.65, QColor("#0b2440"))
    grad.setColorAt(1.0, QColor("#071527"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawEllipse(QRectF(w * 0.04, w * 0.04, w * 0.92, w * 0.92))

    # 外环
    pen = QPen(QColor(41, 198, 255, 230), w * 0.022)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(w * 0.09, w * 0.09, w * 0.82, w * 0.82))

    # 外环刻度（HUD感）
    pen.setWidthF(w * 0.012)
    p.setPen(pen)
    import math
    for i in range(24):
        ang = math.radians(i * 15)
        r1, r2 = w * 0.415, w * 0.46 if i % 3 == 0 else w * 0.435
        p.drawLine(QPointF(w * 0.5 + r1 * math.cos(ang), w * 0.5 + r1 * math.sin(ang)),
                   QPointF(w * 0.5 + r2 * math.cos(ang), w * 0.5 + r2 * math.sin(ang)))

    # 内环（旋转弧段感）
    pen.setWidthF(w * 0.03)
    p.setPen(pen)
    rect_in = QRectF(w * 0.2, w * 0.2, w * 0.6, w * 0.6)
    p.drawArc(rect_in, 30 * 16, 100 * 16)
    p.drawArc(rect_in, 150 * 16, 100 * 16)
    p.drawArc(rect_in, 270 * 16, 100 * 16)

    # 中心三角核心（反应堆）
    core = QRectF(w * 0.30, w * 0.30, w * 0.40, w * 0.40)
    glow = QRadialGradient(core.center(), core.width() * 0.8)
    glow.setColorAt(0.0, QColor("#d9f6ff"))
    glow.setColorAt(0.45, QColor(41, 198, 255, 200))
    glow.setColorAt(1.0, QColor(41, 198, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(core.adjusted(-core.width() * 0.18, -core.width() * 0.18,
                                core.width() * 0.18, core.width() * 0.18))
    tri = QPainterPath()
    tri.moveTo(core.center().x(), core.top() + core.height() * 0.08)
    tri.lineTo(core.right() - core.width() * 0.10, core.bottom() - core.height() * 0.08)
    tri.lineTo(core.left() + core.width() * 0.10, core.bottom() - core.height() * 0.08)
    tri.closeSubpath()
    p.setBrush(QColor("#9fe9ff"))
    p.setPen(QPen(QColor("#e8fbff"), w * 0.012))
    p.drawPath(tri)

    p.end()
    if s != size:
        pix = pix.scaled(size, size, Qt.SmoothTransformation, Qt.SmoothTransformation)
    return pix
