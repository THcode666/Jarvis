# -*- coding: utf-8 -*-
"""贾维斯 Jarvis —— 个人工作助手

运行：  python main.py
自测：  python main.py --selftest   （离屏运行内置自测，无需显示器）
打包：  见 build.bat
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app import theme
from app.common import APP_NAME, APP_VERSION, get_data_dir
from app.data_store import DataStore
from app.main_window import MainWindow


def run_selftest() -> int:
    """离屏自测：数据层 + 搜索 + 导入导出 + 各页面构造与刷新。"""
    from selftest import main as selftest_main
    return selftest_main()


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    theme.apply_dark_palette(app)  # 深色调色板兜底（先于QSS，覆盖原生部件）
    app.setStyleSheet(theme.QSS)
    window = MainWindow(DataStore(get_data_dir()))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()
