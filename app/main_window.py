# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 顶部全局搜索 + 模块页面容器 + 导入/导出。

新增/删减模块只需改 NAV 列表（一行一个模块），其余自动生效。
"""
import os

from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QStatusBar,
)

from . import common, icons, theme
from .data_store import DataStore
from .search import search as run_search
from .modules.tasks import TaskModule
from .modules.memos import MemoModule
from .modules.questions import QuestionModule
from .modules.sop import SopModule
from .modules.search_page import SearchPage

# 模块注册表：新增模块 = 新建文件 + 在这里加一行
NAV = [
    ("缓急", TaskModule),
    ("帮记", MemoModule),
    ("解惑", QuestionModule),
    ("存知", SopModule),
]


class MainWindow(QMainWindow):
    def __init__(self, store: DataStore):
        super().__init__()
        self.store = store
        self.search_mode = False  # 当前是否处于搜索结果页
        self.last_page_idx = 0    # 进入搜索前的页面，退出搜索时回到这里
        self.setWindowTitle(f"{common.APP_NAME} {common.APP_VERSION}")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1000, 640)
        self.resize(1160, 720)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 左侧导航 ----
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(150)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(0, 14, 0, 14)
        sv.setSpacing(2)

        logo = QLabel("J.A.R.V.I.S")
        logo.setObjectName("appTitle")
        logo.setAlignment(Qt.AlignCenter)
        logo_sub = QLabel("贾维斯工作助手")
        logo_sub.setObjectName("appSub")
        logo_sub.setAlignment(Qt.AlignCenter)
        sv.addWidget(logo)
        sv.addWidget(logo_sub)
        sv.addSpacing(16)

        self.navButtons = []
        for i, (name, _) in enumerate(NAV):
            btn = QPushButton(f"  {name}")
            btn.setProperty("class", "nav")
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setIcon(icons.nav_icon(self._icon_kind(name)))
            btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(lambda _, idx=i: self.switch_page(idx))
            sv.addWidget(btn)
            self.navButtons.append(btn)
        sv.addStretch(1)

        ver = QLabel(common.APP_VERSION)
        ver.setObjectName("appSub")
        ver.setAlignment(Qt.AlignCenter)
        sv.addWidget(ver)
        root.addWidget(sidebar)

        # ---- 右侧：顶栏 + 页面 ----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("topbar")
        tv = QHBoxLayout(topbar)
        tv.setContentsMargins(16, 10, 16, 10)
        self.edSearch = QLineEdit()
        self.edSearch.setObjectName("globalSearch")
        self.edSearch.setPlaceholderText(
            "🔍  全局搜索：任务 / 备忘 / 问题 / SOP（支持空格分隔多个关键词、模糊匹配）")
        self.edSearch.addAction(icons.search_icon(), QLineEdit.LeadingPosition)
        self.edSearch.setClearButtonEnabled(True)
        self.edSearch.returnPressed.connect(self._search_now)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._search_now)
        self.edSearch.textChanged.connect(self._on_search_typed)

        btnExport = QPushButton("导出备份")
        btnExport.clicked.connect(self.export_data)
        btnImport = QPushButton("导入备份")
        btnImport.clicked.connect(self.import_data)
        tv.addWidget(self.edSearch, 1)
        tv.addWidget(btnExport)
        tv.addWidget(btnImport)
        rv.addWidget(topbar)

        self.stack = QStackedWidget()
        self.pages = []
        for name, cls in NAV:
            page = cls(self.store)
            self.pages.append(page)
            self.stack.addWidget(page)
        self.searchPage = SearchPage(self.store)
        self.searchPage.searchRequested.connect(self.open_search_result)
        self.stack.addWidget(self.searchPage)
        rv.addWidget(self.stack, 1)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        # ---- 状态栏 ----
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lblDataPath = QLabel("")
        sb.addWidget(self.lblDataPath)
        self.lblCounts = QLabel("")
        sb.addPermanentWidget(self.lblCounts)

        self.switch_page(0)
        self.store.changed.connect(self._on_data_changed)
        self._update_status()

    # ---- 导航 ----

    @staticmethod
    def _icon_kind(name):
        return {"缓急": "tasks", "帮记": "memo", "解惑": "qa", "存知": "knowledge"}.get(name, "tasks")

    def switch_page(self, idx: int):
        if not self.search_mode:
            self.last_page_idx = idx
        self.search_mode = False
        for i, b in enumerate(self.navButtons):
            b.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)
        self.pages[idx].refresh()

    # ---- 全局搜索 ----

    def _collect_records(self):
        records = []
        for page in self.pages:
            records.extend(page.search_records())
        return records

    def _on_search_typed(self, text):
        if not text.strip():
            self._exit_search()
        else:
            self._debounce.start()

    def _search_now(self):
        query = self.edSearch.text().strip()
        if not query:
            self._exit_search()
            return
        results = run_search(self._collect_records(), query)
        self.search_mode = True
        for b in self.navButtons:
            b.setChecked(False)
        self.searchPage.show_results(query, results)
        self.stack.setCurrentWidget(self.searchPage)

    def _exit_search(self):
        if self.search_mode:
            self.switch_page(self.last_page_idx)

    def open_search_result(self, module_key, item_id, open_editor):
        for i, page in enumerate(self.pages):
            if page.module_key == module_key:
                self.switch_page(i)
                page.locate(item_id)
                if open_editor and hasattr(page, "edit_item"):
                    page.edit_item(item_id)
                elif open_editor and hasattr(page, "edit_current"):
                    page.edit_current()
                return

    # ---- 导入 / 导出 ----

    def export_data(self):
        default_name = f"jarvis_backup_{common.today_str().replace('-', '')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出备份（数据+附件）", os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "备份文件 (*.zip)")
        if not path:
            return
        try:
            self.store.export_zip(path)
            QMessageBox.information(self, "导出成功", f"备份已保存到：\n{path}")
        except OSError as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def import_data(self):
        ret = QMessageBox.warning(
            self, "导入确认",
            "导入将【覆盖】当前软件里的全部数据（含附件）。\n建议先点「导出备份」保存当前数据。\n\n确定继续导入？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择备份文件", "", "备份文件 (*.zip)")
        if not path:
            return
        try:
            self.store.import_zip(path)
            QMessageBox.information(self, "导入成功", "数据已恢复。")
        except (ValueError, OSError, KeyError) as e:
            QMessageBox.critical(self, "导入失败", f"文件无效或读取失败：\n{e}")

    # ---- 状态栏 ----

    def _on_data_changed(self):
        self._update_status()

    def _update_status(self):
        d = self.store.data
        self.lblCounts.setText(
            f"任务 {len(d['tasks'])} · 备忘 {len(d['memos'])} · 问题 {len(d['questions'])} · SOP {len(d['sops'])}")
        self.lblDataPath.setText(f"数据目录：{self.store.data_dir}")
