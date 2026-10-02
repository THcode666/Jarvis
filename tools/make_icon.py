# -*- coding: utf-8 -*-
"""生成应用图标 assets/jarvis.ico 和 assets/jarvis_preview.png

造型：深空圆盘 + HUD刻度环 + 旋转弧 + 反应堆三角核心（贾维斯风格，简约科幻）。
用法：python tools/make_icon.py（依赖 Pillow：pip install pillow）
"""
import os

from PIL import Image, ImageDraw
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.icons import draw_logo_pixmap  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")  # 仓库根目录/assets


def save_ico():
    os.makedirs(ASSETS, exist_ok=True)
    # 512px 母图
    master = draw_logo_pixmap(512)
    master.save(os.path.join(ASSETS, "jarvis_preview.png"))

    img = Image.open(os.path.join(ASSETS, "jarvis_preview.png")).convert("RGBA")
    ico_path = os.path.join(ASSETS, "jarvis.ico")
    img.save(ico_path, format="ICO", sizes=[
        (256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("图标已生成：", ico_path)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    save_ico()
