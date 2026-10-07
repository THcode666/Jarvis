# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 顶部全局搜索 + 模块页面容器 + 导入/导出。

新增/删减模块只需改 NAV 列表（一行一个模块），其余自动生效。
"""
import json
import os

from PySide6.QtCore import QTimer, Qt, QSize, QByteArray, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSizePolicy, QStackedWidget, QStatusBar,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import common, icons, theme
from .data_store import DataStore
from .search import search as run_search
from .modules.tasks import TaskModule, collect_due
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
            "🔍  全局搜索：任务 / 备忘 / 问题 / SOP（多关键词、模糊、拼音首字母如 hzk）")
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
        self.lblDue = QPushButton("")
        self.lblDue.setObjectName("dueBadge")
        self.lblDue.setCursor(Qt.PointingHandCursor)
        self.lblDue.setToolTip("点击打开任务清单")
        self.lblDue.clicked.connect(lambda: self.switch_page(0))
        self.lblDue.hide()
        sb.addPermanentWidget(self.lblDue)
        self.lblCounts = QLabel("")
        sb.addPermanentWidget(self.lblCounts)

        # ---- 恢复记住的界面状态（窗口大小/位置、上次页面、任务排序）----
        self._settings_path = os.path.join(store.data_dir, "settings.json")
        state = self._load_state()
        si = state.get("task_sort", 0)
        if isinstance(si, int) and 0 <= si < self.pages[0].cbSort.count():
            self.pages[0].cbSort.setCurrentIndex(si)
        geo = state.get("geometry")
        if isinstance(geo, str) and geo:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geo.encode("ascii")))
            except Exception:
                pass

        # ---- 托盘常驻 + 到期提醒 ----
        self._really_quit = False
        self._tray_tipped = False
        self._last_digest = ""
        self.close_to_tray = bool(state.get("close_to_tray", True))
        self._make_tray()
        self._remind_timer = QTimer(self)
        self._remind_timer.setInterval(30 * 60 * 1000)  # 每半小时巡检一次
        self._remind_timer.timeout.connect(self._check_reminders)
        self._remind_timer.start()
        QTimer.singleShot(2500, self._check_reminders)  # 启动后稍等即查一次

        # 快捷键：Ctrl+F 搜索 / Ctrl+N 新增 / F5 刷新
        for keys, slot in (("Ctrl+F", self._focus_search),
                           ("Ctrl+N", self._new_current),
                           ("F5", self._refresh_current)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.activated.connect(slot)
        self.edSearch.installEventFilter(self)  # Esc 退出搜索

        pi = state.get("page", 0)
        self.switch_page(pi if isinstance(pi, int) and 0 <= pi < len(self.pages) else 0)
        self.store.changed.connect(self._on_data_changed)
        self._update_status()

    # ---- 托盘与到期提醒 ----

    def _make_tray(self):
        self.tray = QSystemTrayIcon(icons.app_icon(), self)
        self.tray.setToolTip(common.APP_NAME)
        menu = QMenu()
        act_show = menu.addAction("显示主界面")
        act_show.triggered.connect(self._show_from_tray)
        act_check = menu.addAction("检查任务提醒")
        act_check.triggered.connect(lambda: self._check_reminders(force=True))
        menu.addSeparator()
        self.actTrayClose = menu.addAction("关闭时最小化到托盘")
        self.actTrayClose.setCheckable(True)
        self.actTrayClose.blockSignals(True)
        self.actTrayClose.setChecked(self.close_to_tray)
        self.actTrayClose.blockSignals(False)
        self.actTrayClose.toggled.connect(self._toggle_close_to_tray)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self._quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._show_from_tray()
            if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.messageClicked.connect(self._goto_tasks)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _show_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def _goto_tasks(self):
        self._show_from_tray()
        self.switch_page(0)

    def _toggle_close_to_tray(self, checked):
        self.close_to_tray = checked
        self._save_state()

    def _quit_app(self):
        self._really_quit = True
        self.tray.hide()
        self.close()

    def _check_reminders(self, force=False):
        """巡检到期任务：刷新角标；内容有变化且托盘可用时弹一次通知。"""
        g = collect_due(self.store.data["tasks"])
        n, m = len(g["逾期"]), len(g["今日"])
        if n or m:
            parts = []
            if n:
                parts.append(f"逾期 {n}")
            if m:
                parts.append(f"今日到期 {m}")
            self.lblDue.setText("⚠ " + " · ".join(parts))
            self.lblDue.show()
        else:
            self.lblDue.hide()

        digest = self._digest_text(g)
        if not digest:
            self._last_digest = ""
            return
        if digest == self._last_digest and not force:
            return
        self._last_digest = digest
        if os.environ.get("JARVIS_SILENT"):
            return  # 自测等场景不弹系统通知
        if self.tray.isVisible():
            self.tray.showMessage("贾维斯任务提醒", digest,
                                  QSystemTrayIcon.Information, 10000)

    @staticmethod
    def _digest_text(g):
        def brief(items):
            s = "、".join(t.get("desc", "")[:14] for t in items[:4])
            return s + " 等" if len(items) > 4 else s
        parts = []
        if g["逾期"]:
            parts.append(f"逾期 {len(g['逾期'])} 项：{brief(g['逾期'])}")
        if g["今日"]:
            parts.append(f"今日到期 {len(g['今日'])} 项：{brief(g['今日'])}")
        if g["三日"]:
            parts.append(f"3日内到期 {len(g['三日'])} 项：{brief(g['三日'])}")
        return "\n".join(parts)

    # ---- 快捷键与窗口状态 ----

    def _focus_search(self):
        self.edSearch.setFocus()
        self.edSearch.selectAll()

    def _new_current(self):
        if self.search_mode:
            self.switch_page(self.last_page_idx)
        page = self.pages[self.stack.currentIndex()]
        if hasattr(page, "add_item"):
            page.add_item()

    def _refresh_current(self):
        if self.search_mode:
            self._search_now()
        else:
            self.pages[self.stack.currentIndex()].refresh()

    def eventFilter(self, obj, event):
        """搜索框内按 Esc 清空并退出搜索结果页。"""
        if obj is self.edSearch and event.type() == QEvent.KeyPress \
                and event.key() == Qt.Key_Escape:
            self.edSearch.clear()   # 触发 textChanged → _exit_search
            self.edSearch.clearFocus()
            return True
        return super().eventFilter(obj, event)

    def _load_state(self):
        try:
            with open(self._settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_state(self):
        try:
            state = {
                "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                "page": self.last_page_idx,
                "task_sort": self.pages[0].cbSort.currentIndex(),
                "close_to_tray": self.close_to_tray,
            }
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except OSError:
            pass

    def closeEvent(self, event):
        self._save_state()
        if self.close_to_tray and not self._really_quit \
                and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            if not self._tray_tipped:
                self._tray_tipped = True
                if self.tray.isVisible():
                    self.tray.showMessage(
                        "贾维斯", "已最小化到托盘：双击托盘图标恢复，右键菜单可退出。",
                        QSystemTrayIcon.Information, 5000)
        else:
            event.accept()

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
        # 搜索结果页正打开时数据变了要即时重查，避免展示过期结果
        if self.search_mode and self.edSearch.text().strip():
            self._search_now()

    def _update_status(self):
        d = self.store.data
        self.lblCounts.setText(
            f"任务 {len(d['tasks'])} · 备忘 {len(d['memos'])} · 问题 {len(d['questions'])} · SOP {len(d['sops'])}")
        self.lblDataPath.setText(f"数据目录：{self.store.data_dir}")
        self._check_reminders()
