# -*- coding: utf-8 -*-
"""扩展对话框：每日任务模板 / 解异（异常）编辑 / SVG图表预览。

与 dialogs.py 分文件放置，避免单文件过大；这里反向引用 dialogs 的公共小件。
"""
import os

from PySide6.QtCore import QDateTime, QTime, Qt, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTabWidget, QTimeEdit, QVBoxLayout, QWidget,
    QHeaderView, QCheckBox, QAbstractItemView, QTableWidgetItem,
)

from . import common
from .data_store import PRIORITIES
from .dialogs import _buttons, to_qdatetime  # noqa: F401 (to_qdatetime 备用)

FISHBONE_CATS = ["人", "机", "料", "法", "环"]
_FISHBONE_EN = {"人": "Man", "机": "Machine", "料": "Material",
                "法": "Method", "环": "Environment"}


# ---- 对话框尺寸记忆（数据目录 dialog_sizes.json） ----

def load_dialog_size(store, key: str, default_w: int, default_h: int):
    try:
        import json
        p = os.path.join(store.data_dir, "dialog_sizes.json")
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        w, h = data.get(key, [default_w, default_h])
        return max(400, int(w)), max(320, int(h))
    except Exception:
        return default_w, default_h


def save_dialog_size(store, key: str, w: int, h: int):
    try:
        import json
        p = os.path.join(store.data_dir, "dialog_sizes.json")
        data = {}
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        data[key] = [int(w), int(h)]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


class DailyTaskDialog(QDialog):
    """缓急 - 每日任务模板：工作日自动生成，节假日/周末自动跳过。"""

    def __init__(self, parent=None, daily=None):
        super().__init__(parent)
        self.setWindowTitle("编辑每日任务" if daily else "新增每日任务")
        self.setMinimumWidth(430)

        self.edDesc = QPlainTextEdit()
        self.edDesc.setPlaceholderText("每天要做的事，例如：点检机台参数")
        self.edDesc.setFixedHeight(52)
        self.edDiff = QPlainTextEdit()
        self.edDiff.setPlaceholderText("难点 / 注意事项（可留空）")
        self.edDiff.setFixedHeight(52)
        self.cbPri = QComboBox()
        self.cbPri.addItems(PRIORITIES)
        self.cbPri.setCurrentText("中")
        self.edTime = QTimeEdit(QTime(17, 30))
        self.edTime.setDisplayFormat("HH:mm")
        self.edTime.setToolTip("每天自动生成的任务的到期时刻")
        self.chkEnabled = QCheckBox("启用（工作日自动生成，节假日/周末自动跳过）")
        self.chkEnabled.setChecked(True)

        form = QFormLayout()
        form.addRow("任务内容*", self.edDesc)
        form.addRow("难点", self.edDiff)
        form.addRow("优先级", self.cbPri)
        form.addRow("到期时刻", self.edTime)
        form.addRow("", self.chkEnabled)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(_buttons(self))

        if daily:
            self.edDesc.setPlainText(daily.get("desc", ""))
            self.edDiff.setPlainText(daily.get("difficulty", ""))
            self.cbPri.setCurrentText(daily.get("priority", "中"))
            t = QTime.fromString(daily.get("due_time", "17:30"), "HH:mm")
            if t.isValid():
                self.edTime.setTime(t)
            self.chkEnabled.setChecked(daily.get("enabled", True))

    def fields(self):
        return {
            "desc": self.edDesc.toPlainText().strip(),
            "difficulty": self.edDiff.toPlainText().strip(),
            "priority": self.cbPri.currentText(),
            "due_time": self.edTime.time().toString("HH:mm"),
            "enabled": self.chkEnabled.isChecked(),
        }


class AnomalyDialog(QDialog):
    """解异 - 新增/编辑异常：六要素 + 图片(支持粘贴截图) + 时间线 + 鱼骨图。"""

    def __init__(self, parent=None, store=None, item=None):
        super().__init__(parent)
        self.store = store
        self.item_id = item["id"] if item else common.new_id()
        self.existing = dict(item) if item else None
        self.attachments = [dict(a) for a in (item.get("images", []) if item else [])]
        self.removed = []
        self.setWindowTitle("编辑异常" if item else "新增异常")
        self.setMinimumSize(600, 480)
        # 可调整大小 + 最大化按钮，并记住上次的窗口尺寸
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        if store:
            self.resize(*load_dialog_size(store, "anomaly", 680, 620))
        else:
            self.resize(680, 620)

        tabs = QTabWidget()
        tabs.addTab(self._make_basic_tab(item or {}), "概况（六要素）")
        tabs.addTab(self._make_image_tab(), "图片（可粘贴截图）")
        tabs.addTab(self._make_timeline_tab(item or {}), "时间线")
        tabs.addTab(self._make_fishbone_tab(item or {}), "鱼骨图")

        lay = QVBoxLayout(self)
        lay.addWidget(tabs, 1)
        lay.addWidget(_buttons(self))
        self._reload_att_list()

    def hideEvent(self, event):
        if self.store:
            save_dialog_size(self.store, "anomaly", self.width(), self.height())
        super().hideEvent(event)

    # ---- 概况 ----

    def _make_basic_tab(self, item):
        w = QWidget()
        self.edTitle = QLineEdit()
        self.edTitle.setPlaceholderText("异常标题，例如：lot结批报错E102")
        self.edTitle.setText(item.get("title", "") or "")
        form = QFormLayout()
        form.addRow("标题*", self.edTitle)

        self.edFields = {}
        rows = [("background", "背景"),
                ("impact", "影响"),
                ("lesson", "过往教训"),
                ("actions", "做了什么"),
                ("root_cause", "原因"),
                ("prevention", "后续措施")]
        hints = {"background": "发生了什么问题？何时何地何现象？",
                 "impact": "对产出/品质/交付的影响？",
                 "lesson": "以前有没有发生过？当时的教训？",
                 "actions": "问题发生后做了什么处置？",
                 "root_cause": "根本原因是什么？（可结合鱼骨图结论）",
                 "prevention": "如何预防再次发生 / 后续跟进计划？"}
        for key, label in rows:
            ed = QPlainTextEdit()
            ed.setFixedHeight(50)
            ed.setPlaceholderText(hints[key])
            ed.setPlainText(item.get(key, "") or "")  # 编辑时回填，避免保存清空
            self.edFields[key] = ed
            form.addRow(label, ed)
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 4)
        v.addLayout(form)
        return w

    # ---- 图片 ----

    def _make_image_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 4)
        v.addWidget(QLabel("点「粘贴截图」把剪贴板里的截图存进来（也可从文件添加）。生成PPT时最多放前3张。"))
        self.attList = QListWidget()
        self.attList.setIconSize(QSize(40, 40))
        self.attList.setSelectionMode(QAbstractItemView.SingleSelection)
        h = QHBoxLayout()
        btnPaste = QPushButton("粘贴截图 (Ctrl+V)")
        btnPaste.setObjectName("primary")
        btnPaste.clicked.connect(self._paste_image)
        btnFile = QPushButton("从文件添加")
        btnFile.clicked.connect(self._add_image_files)
        btnDel = QPushButton("移除选中")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(self._remove_selected)
        h.addWidget(btnPaste)
        h.addWidget(btnFile)
        h.addWidget(btnDel)
        h.addStretch(1)
        v.addLayout(h)
        v.addWidget(self.attList, 1)
        return w

    def _paste_image(self):
        if not self.store:
            return
        from PySide6.QtWidgets import QApplication
        img = QApplication.clipboard().image()
        if img.isNull():
            QMessageBox.information(self, "提示", "剪贴板里没有图片。\n先用截图工具截图（或复制图片）再点此按钮。")
            return
        tmp = os.path.join(self.store.data_dir, f"_paste_{common.new_id()}.png")
        if not img.save(tmp, "PNG"):
            QMessageBox.warning(self, "失败", "剪贴板图片保存失败")
            return
        try:
            self.attachments.append(self.store.add_attachment(self.item_id, tmp))
        except OSError as e:
            QMessageBox.warning(self, "添加失败", str(e))
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        self._reload_att_list()

    def _add_image_files(self):
        if not self.store:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        for path in paths:
            try:
                self.attachments.append(self.store.add_attachment(self.item_id, path))
            except OSError as e:
                QMessageBox.warning(self, "添加失败", f"{path}\n\n{e}")
        if paths:
            self._reload_att_list()

    def _remove_selected(self):
        row = self.attList.currentRow()
        if row < 0:
            return
        att = self.attachments.pop(row)
        if self.existing and att in [dict(a) for a in self.existing.get("images", [])]:
            self.removed.append(att)
        self._reload_att_list()

    def _reload_att_list(self):
        self.attList.clear()
        for att in self.attachments:
            it = QListWidgetItem(att["name"])
            if self.store:
                pm = QPixmap(self.store.attachment_path(att["stored"]))
                if not pm.isNull():
                    from PySide6.QtGui import QIcon
                    it.setIcon(QIcon(pm.scaled(64, 64, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation)))
            self.attList.addItem(it)

    # ---- 时间线 ----

    def _make_timeline_tab(self, item):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 4)
        v.setSpacing(4)
        v.addWidget(QLabel("按时间顺序填：什么时间做了什么。预览/导出时会生成从左到右的时间线。"))
        v.addWidget(QLabel("时间格式建议：10-08 08:15 或 2026-10-08 08:15；顺序不对可用 ↑↓ 调整。"))
        self.tlTable = QTableWidget(0, 2)
        self.tlTable.setHorizontalHeaderLabels(["时间", "做了什么"])
        self.tlTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tlTable.setColumnWidth(0, 170)  # 容纳 2026-10-08 08:15 完整显示
        self.tlTable.verticalHeader().setVisible(False)
        self.tlTable.verticalHeader().setDefaultSectionSize(34)

        h = QHBoxLayout()
        btnAdd = QPushButton("＋ 添加一行")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(lambda: self._tl_add())
        btnUp = QPushButton("↑ 上移")
        btnUp.setToolTip("把选中的行往前移（时间线更靠左）")
        btnUp.clicked.connect(lambda: self._tl_move(-1))
        btnDown = QPushButton("↓ 下移")
        btnDown.setToolTip("把选中的行往后移（时间线更靠右）")
        btnDown.clicked.connect(lambda: self._tl_move(1))
        btnDel = QPushButton("删除选中行")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(self._tl_del)
        for b in (btnAdd, btnUp, btnDown, btnDel):
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        v.addWidget(self.tlTable, 1)
        for e in item.get("timeline", []):
            r = self.tlTable.rowCount()
            self.tlTable.insertRow(r)
            self.tlTable.setItem(r, 0, QTableWidgetItem(e.get("time", "")))
            self.tlTable.setItem(r, 1, QTableWidgetItem(e.get("event", "")))
        if self.tlTable.rowCount() == 0:
            self._tl_add(autofocus=False)
        return w

    def _tl_add(self, autofocus=True):
        r = self.tlTable.rowCount()
        self.tlTable.insertRow(r)
        self.tlTable.setItem(r, 0, QTableWidgetItem(""))
        self.tlTable.setItem(r, 1, QTableWidgetItem(""))
        if autofocus:
            self.tlTable.setCurrentCell(r, 0)
            self.tlTable.setFocus()
            self.tlTable.editItem(self.tlTable.item(r, 0))  # 直接进入时间单元格编辑

    def _tl_move(self, delta):
        r = self.tlTable.currentRow()
        t = r + delta
        n = self.tlTable.rowCount()
        if r < 0 or not (0 <= t < n):
            return
        vals = {}
        for row in (r, t):
            vals[row] = [(self.tlTable.item(row, c).text()
                          if self.tlTable.item(row, c) else "")
                         for c in range(self.tlTable.columnCount())]
        for c in range(self.tlTable.columnCount()):
            self.tlTable.setItem(r, c, QTableWidgetItem(vals[t][c]))
            self.tlTable.setItem(t, c, QTableWidgetItem(vals[r][c]))
        self.tlTable.setCurrentCell(t, 0)

    def _tl_del(self):
        r = self.tlTable.currentRow()
        if r >= 0:
            self.tlTable.removeRow(r)

    # ---- 鱼骨图 ----

    def _make_fishbone_tab(self, item):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 4)
        v.addWidget(QLabel("从 人/机/料/法/环 五个角度列出原因，每行一条（每类最多取前5条）。"))
        form = QFormLayout()
        self.fbEdits = {}
        hints = {"人": "人为失误 / 疲劳 / 操作不规范…",
                 "机": "设备 / 工装 / 参数漂移…",
                 "料": "物料 / 来料不良…",
                 "法": "方法 / 流程 / SOP缺陷…",
                 "环": "环境 / 温湿度 / 电压…"}
        for cat in FISHBONE_CATS:
            ed = QPlainTextEdit()
            ed.setFixedHeight(62)
            ed.setPlaceholderText(hints[cat])
            self.fbEdits[cat] = ed
            form.addRow(f"{cat}（{_FISHBONE_EN[cat]}）", ed)
        v.addLayout(form)
        fb = item.get("fishbone", {}) or {}
        for cat, ed in self.fbEdits.items():
            ed.setPlainText("\n".join(fb.get(cat, [])))
        return w

    # ---- 结果 ----

    def fields(self):
        timeline = []
        for r in range(self.tlTable.rowCount()):
            time_it = self.tlTable.item(r, 0)
            ev_it = self.tlTable.item(r, 1)
            t = (time_it.text() if time_it else "").strip()
            e = (ev_it.text() if ev_it else "").strip()
            if t or e:
                timeline.append({"time": t, "event": e})
        fishbone = {cat: [ln.strip() for ln in ed.toPlainText().splitlines() if ln.strip()]
                    for cat, ed in self.fbEdits.items()}
        base = {k: ed.toPlainText().strip() for k, ed in self.edFields.items()}
        return {
            "title": self.edTitle.text().strip(),
            "background": base["background"],
            "impact": base["impact"],
            "lesson": base["lesson"],
            "actions": base["actions"],
            "root_cause": base["root_cause"],
            "prevention": base["prevention"],
            "images": self.attachments,
            "timeline": timeline,
            "fishbone": fishbone,
        }


class ChartPreviewDialog(QDialog):
    """SVG 图表预览（时间线/鱼骨图），支持导出 HTML。可调整大小并记住尺寸。"""

    def __init__(self, svg: str, title: str, parent=None, default_name="chart.html",
                 store=None):
        super().__init__(parent)
        self.svg = svg
        self.store = store
        self.setWindowTitle(title)
        self.setMinimumSize(700, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        if store:
            self.resize(*load_dialog_size(store, "chart", 1150, 680))
        else:
            self.resize(1150, 680)

        from PySide6.QtGui import QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray
        from PySide6.QtWidgets import QScrollArea

        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        size = renderer.defaultSize()
        scale = 1.6
        pm = QPixmap(int(size.width() * scale), int(size.height() * scale))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        renderer.render(p)
        p.end()

        label = QLabel()
        label.setPixmap(pm)
        area = QScrollArea()
        area.setWidget(label)
        area.setAlignment(Qt.AlignCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(area, 1)
        h = QHBoxLayout()
        hint = QLabel("导出 HTML 后可用浏览器打开，适合插入邮件/汇报。")
        hint.setObjectName("muted")
        h.addWidget(hint)
        h.addStretch(1)
        btnHtml = QPushButton("导出 HTML")
        btnHtml.setObjectName("primary")
        btnHtml.clicked.connect(lambda: self._export_html(title, default_name))
        btnClose = QPushButton("关闭")
        btnClose.clicked.connect(self.accept)
        h.addWidget(btnHtml)
        h.addWidget(btnClose)
        lay.addLayout(h)

    def hideEvent(self, event):
        if self.store:
            save_dialog_size(self.store, "chart", self.width(), self.height())
        super().hideEvent(event)

    def _export_html(self, title, default_name):
        from .svg_charts import wrap_html
        path, _ = QFileDialog.getSaveFileName(self, "导出 HTML", default_name,
                                              "网页 (*.html)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrap_html(self.svg, title))
        QMessageBox.information(self, "导出成功", f"已保存到：\n{path}")
