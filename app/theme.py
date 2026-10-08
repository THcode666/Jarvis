# -*- coding: utf-8 -*-
"""界面主题：深色科幻风（贾维斯HUD风格）QSS。

改配色只需要动下面的几个色值常量。
"""

# 核心配色
BG        = "#0a1220"   # 主背景
BG_PANEL  = "#0f1b2e"   # 面板背景
BG_CARD   = "#122238"   # 卡片/表格行
BORDER    = "#1e3350"   # 边框
ACCENT    = "#29c6ff"   # 科技蓝（主强调色）
ACCENT2   = "#7adfff"   # 亮青
TEXT      = "#d7e3f4"   # 正文
TEXT_DIM  = "#7d92ad"   # 次要文字
DANGER    = "#ff6b6b"
WARN      = "#ffb64d"
OK        = "#3ddc97"


def apply_dark_palette(app):
    """全局深色调色板：QSS 覆盖不到的原生部件（表格项文本、日历弹窗、
    下拉列表、消息框等）回退到系统浅色调色板时会黑字/刺眼，这里统一兜底。"""
    from PySide6.QtGui import QPalette, QColor

    def c(hexstr):
        return QColor(hexstr)

    pal = QPalette()
    pal.setColor(QPalette.Window, c(BG_PANEL))
    pal.setColor(QPalette.WindowText, c(TEXT))
    pal.setColor(QPalette.Base, c("#0c1830"))
    pal.setColor(QPalette.AlternateBase, c(BG_PANEL))
    pal.setColor(QPalette.Text, c(TEXT))
    pal.setColor(QPalette.Button, c(BG_CARD))
    pal.setColor(QPalette.ButtonText, c(TEXT))
    pal.setColor(QPalette.ToolTipBase, c(BG_PANEL))
    pal.setColor(QPalette.ToolTipText, c(TEXT))
    pal.setColor(QPalette.BrightText, c("#ffffff"))
    pal.setColor(QPalette.Highlight, c("#10395c"))
    pal.setColor(QPalette.HighlightedText, c(TEXT))
    pal.setColor(QPalette.Link, c(ACCENT))
    pal.setColor(QPalette.PlaceholderText, c(TEXT_DIM))
    pal.setColor(QPalette.Disabled, QPalette.Text, c("#46566c"))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, c("#46566c"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, c("#46566c"))
    app.setPalette(pal)

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #04121f;
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#sidebar {{ background: {BG_PANEL}; border-right: 1px solid {BORDER}; }}
QWidget#topbar {{ background: {BG_PANEL}; border-bottom: 1px solid {BORDER}; }}

QLabel#appTitle {{
    font-size: 17px; font-weight: bold; color: {ACCENT};
    letter-spacing: 2px;
}}
QLabel#appSub {{ color: {TEXT_DIM}; font-size: 11px; }}
QLabel#pageHead {{ font-size: 16px; font-weight: bold; color: {ACCENT2}; }}
QLabel#muted {{ color: {TEXT_DIM}; }}

/* ---- 侧边导航 ---- */
QPushButton.nav {{
    text-align: left; padding: 11px 16px; border: none;
    border-left: 3px solid transparent; color: {TEXT_DIM};
    background: transparent; font-size: 14px;
}}
QPushButton.nav:hover {{ color: {TEXT}; background: #10203a; }}
QPushButton.nav:checked {{
    color: {ACCENT}; border-left: 3px solid {ACCENT};
    background: #10233f; font-weight: bold;
}}

/* ---- 搜索框 ---- */
QLineEdit#globalSearch {{
    background: #0c1830; border: 1px solid {BORDER}; border-radius: 17px;
    padding: 7px 16px; font-size: 14px;
}}
QLineEdit#globalSearch:focus {{ border: 1px solid {ACCENT}; }}

/* ---- 通用按钮 ---- */
QPushButton {{
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 4px;
    padding: 5px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT2}; }}
QPushButton:pressed {{ background: #0c1830; }}
QPushButton:disabled {{ color: #46566c; border-color: {BORDER}; }}
QPushButton#primary {{
    background: #0b3a54; border: 1px solid {ACCENT}; color: {ACCENT2}; font-weight: bold;
}}
QPushButton#primary:hover {{ background: #0d4a6d; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#danger:hover {{ border-color: {DANGER}; }}

/* ---- 输入控件 ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QDateTimeEdit {{
    background: #0c1830; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 8px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {BG_PANEL}; border: 1px solid {BORDER};
    selection-background-color: #0b3a54;
}}

/* ---- 表格 ---- */
QTableWidget {{
    background: {BG}; color: {TEXT}; alternate-background-color: {BG_PANEL};
    border: 1px solid {BORDER}; gridline-color: {BORDER};
}}
QTableWidget::item {{ padding: 4px; color: {TEXT}; background: transparent; }}
QTableWidget::item:selected {{ background: #10395c; color: {TEXT}; }}
QHeaderView::section {{
    background: {BG_PANEL}; border: none; border-bottom: 1px solid {BORDER};
    padding: 7px 6px; font-weight: bold; color: {ACCENT2};
}}
QTableCornerButton::section {{ background: {BG_PANEL}; border: none; }}

/* ---- 选项卡 ---- */
QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; }}
QTabBar::tab {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-bottom: none;
    padding: 7px 18px; margin-right: 3px; color: {TEXT_DIM};
}}
QTabBar::tab:selected {{ color: {ACCENT}; border-top: 2px solid {ACCENT}; background: {BG}; }}

/* ---- 卡片（帮记/解惑/搜索结果） ---- */
QFrame#card {{
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px;
}}
QFrame#card:hover {{ border-color: #2c4d78; }}
QLabel.cardTitle {{ font-size: 14px; font-weight: bold; color: {ACCENT2}; }}
QLabel.cardTime {{ color: {TEXT_DIM}; font-size: 11px; }}

/* ---- 列表 / 滚动条 ---- */
QListWidget {{
    background: {BG}; border: 1px solid {BORDER};
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid #14243c; }}
QListWidget::item:selected {{ background: #10395c; color: {TEXT}; }}
QScrollArea {{ border: none; background: {BG}; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QScrollBar {{ background: {BG_PANEL}; }}
QScrollBar:vertical {{
    background: {BG_PANEL}; width: 10px; border: none;
}}
QScrollBar::handle:vertical {{ background: #24405f; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {BG_PANEL}; height: 10px; border: none; }}
QScrollBar::handle:horizontal {{ background: #24405f; border-radius: 5px; min-width: 30px; }}

/* ---- 其他 ---- */
QSplitter::handle {{ background: {BORDER}; width: 2px; }}
QStatusBar {{ background: {BG_PANEL}; border-top: 1px solid {BORDER}; color: {TEXT_DIM}; }}
QPushButton#dueBadge {{
    border: none; background: transparent; color: {DANGER};
    font-weight: bold; padding: 0 8px;
}}
QPushButton#dueBadge:hover {{ color: #ff9191; }}
QToolTip {{
    background: {BG_PANEL}; color: {TEXT}; border: 1px solid {ACCENT}; padding: 4px;
}}
QMessageBox {{ background: {BG_PANEL}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QMenu {{ background: {BG_PANEL}; border: 1px solid {BORDER}; color: {TEXT}; }}
QMenu::item:selected {{ background: #0b3a54; }}

/* ---- 复选框（暗色主题下系统指示器看不清） ---- */
QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid #2a4a74; border-radius: 3px;
    background: #0c1830;
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: #0b6a8f; border-color: {ACCENT}; }}
QCheckBox::indicator:disabled {{ border-color: {BORDER}; background: {BG_PANEL}; }}

/* ---- 日历弹窗（开始时间/Due Day 的日历选择） ---- */
QCalendarWidget {{
    background: {BG_PANEL}; color: {TEXT};
}}
QCalendarWidget QWidget {{ alternate-background-color: #10203a; color: {TEXT}; }}
QCalendarWidget QToolButton {{
    background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 4px 8px; font-weight: normal;
}}
QCalendarWidget QToolButton:hover {{ background: #0b3a54; border-color: {ACCENT}; }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {BG_PANEL}; }}
QCalendarWidget QSpinBox {{
    background: #0c1830; color: {TEXT}; border: 1px solid {BORDER};
    selection-background-color: #10395c;
}}
QCalendarWidget QAbstractItemView {{
    background: #0c1830; color: {TEXT}; selection-background-color: #10395c;
    selection-color: {TEXT}; outline: none;
}}
QCalendarWidget QAbstractItemView:enabled {{
    font-size: 12px;
}}
"""
