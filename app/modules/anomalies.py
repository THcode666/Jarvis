# -*- coding: utf-8 -*-
"""模块五「解异」：工作异常处理。

- 六要素记录（背景/影响/过往教训/行动/根因/后续措施），支持粘贴截图
- 一键生成单页汇报 PPT（python-pptx，字号自适应保证只占一页）
- 时间线分析（从左到右）与鱼骨图分析（人机料法环），软件内预览 + 导出 HTML
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget, QFileDialog,
)

from .. import common
from .. import svg_charts
from ..more_dialogs import AnomalyDialog, ChartPreviewDialog
from ..dialogs import ImageViewDialog
from ..search import SearchRecord

_SECTION_LABELS = [
    ("background", "背景 What's the issue"),
    ("impact", "影响 What's the impact"),
    ("lesson", "过往教训 Lesson learned"),
    ("actions", "做了什么 Action done"),
    ("root_cause", "原因 Root cause"),
    ("prevention", "后续措施 How to prevent / follow up"),
]


class AnomalyModule(QWidget):
    module_key = "anomalies"
    module_name = "解异"

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.current_id = None
        store.changed.connect(self.refresh)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        lbl = QLabel("解异 · 工作异常处理")
        lbl.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnEdit = QPushButton("编辑")
        btnEdit.clicked.connect(self.edit_current)
        btnDel = QPushButton("删除")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(self.delete_current)
        btnPpt = QPushButton("生成汇报PPT")
        btnPpt.setObjectName("primary")
        btnPpt.clicked.connect(self.generate_ppt)
        btnAdd = QPushButton("＋ 新增异常")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(self.add_item)
        head.addWidget(lbl)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(btnPpt)
        head.addWidget(btnEdit)
        head.addWidget(btnDel)
        head.addWidget(btnAdd)
        lay.addLayout(head)

        splitter = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.setMinimumWidth(230)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._on_select)
        self.list.itemDoubleClicked.connect(lambda _: self.edit_current())
        self.detail = self._make_detail()
        splitter.addWidget(self.list)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 760])
        lay.addWidget(splitter, 1)

    # ---- 详情区 ----

    def _make_detail(self) -> QWidget:
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QScrollArea
        self.detailArea = QScrollArea()
        self.detailArea.setWidgetResizable(True)
        self.detailHost = QWidget()
        self.detailLay = QVBoxLayout(self.detailHost)
        self.detailLay.setContentsMargins(4, 2, 10, 10)
        self.detailLay.setSpacing(8)
        self.detailLay.addStretch(1)
        self.detailArea.setWidget(self.detailHost)
        v.addWidget(self.detailArea)
        self._show_empty()
        return host

    def _clear_detail(self):
        while self.detailLay.count() > 1:
            it = self.detailLay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _show_empty(self):
        self._clear_detail()
        lbl = QLabel("从左侧选择一条异常查看详情\n\n还没有记录？点击右上角「＋ 新增异常」")
        lbl.setObjectName("muted")
        lbl.setAlignment(Qt.AlignCenter)
        self.detailLay.insertWidget(0, lbl)

    # ---- 刷新 ----

    def refresh(self):
        selected = self.current_id
        items = sorted(self.store.data["anomalies"],
                       key=lambda a: a.get("created_at", ""), reverse=True)
        self.list.blockSignals(True)
        self.list.clear()
        target = -1
        for i, a in enumerate(items):
            marks = []
            if a.get("images"):
                marks.append("🖼")
            if a.get("timeline"):
                marks.append("⏱")
            if any(a.get("fishbone", {}).values()):
                marks.append("🐟")
            text = f"{a.get('title') or '（无标题）'} {' '.join(marks)}\n{common.fmt_d(a.get('created_at', ''))}"
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, a["id"])
            self.list.addItem(it)
            if a["id"] == selected:
                target = i
        if items:
            row = target if target >= 0 else 0
            self.list.setCurrentRow(row)
            self.current_id = self.list.item(row).data(Qt.UserRole)
        else:
            self.current_id = None
        self.list.blockSignals(False)
        self.lblCount.setText(f"共 {len(items)} 条")
        self._render_detail() if items else self._show_empty()

    def _on_select(self, row):
        if row < 0:
            return
        self.current_id = self.list.item(row).data(Qt.UserRole)
        self._render_detail()

    def _current(self):
        return self.store.find("anomalies", self.current_id) if self.current_id else None

    def _render_detail(self):
        a = self._current()
        self._clear_detail()
        if not a:
            self._show_empty()
            return

        title = QLabel(a.get("title", ""))
        title.setObjectName("pageHead")
        title.setWordWrap(True)
        meta = QLabel(f"创建于 {common.fmt_dt(a.get('created_at', ''))}")
        meta.setObjectName("cardTime")
        self.detailLay.insertWidget(0, title)
        self.detailLay.insertWidget(1, meta)

        for key, label in _SECTION_LABELS:
            text = (a.get(key) or "").strip() or "（未填写）"
            box = QFrame()
            box.setObjectName("card")
            v = QVBoxLayout(box)
            v.setContentsMargins(10, 7, 10, 7)
            v.setSpacing(3)
            head_lbl = QLabel(label)
            head_lbl.setStyleSheet("color:#29c6ff;font-weight:bold;font-size:12px;")
            body = QLabel(text)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.addWidget(head_lbl)
            v.addWidget(body)
            self.detailLay.insertWidget(self.detailLay.count() - 1, box)

        # 图片
        for att in a.get("images", []):
            path = self.store.attachment_path(att.get("stored", ""))
            if att.get("kind") == "image" and os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    thumb = QLabel()
                    thumb.setPixmap(pm.scaledToWidth(300, Qt.SmoothTransformation))
                    thumb.setCursor(Qt.PointingHandCursor)
                    t = att.get("name", "图片")

                    def open_big(_=None, p=path, t=t):
                        ImageViewDialog(p, t, self).exec()
                    thumb.mouseReleaseEvent = lambda ev, fn=open_big: fn()
                    self.detailLay.insertWidget(self.detailLay.count() - 1, thumb)

        chart_row = QHBoxLayout()
        if a.get("timeline"):
            btnTl = QPushButton("⏱ 时间线预览")
            btnTl.clicked.connect(self.preview_timeline)
            chart_row.addWidget(btnTl)
        if any((a.get("fishbone") or {}).values()):
            btnFb = QPushButton("🐟 鱼骨图预览")
            btnFb.clicked.connect(self.preview_fishbone)
            chart_row.addWidget(btnFb)
        if chart_row.count():
            chart_row.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(chart_row)
            self.detailLay.insertWidget(self.detailLay.count() - 1, wrap)

    # ---- 操作 ----

    def add_item(self):
        dlg = AnomalyDialog(self, store=self.store)
        if dlg.exec() == AnomalyDialog.Accepted:
            f = dlg.fields()
            if not f["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            a = self.store.add_anomaly(f["title"], f)
            self.current_id = a["id"]
            self.refresh()

    def edit_current(self):
        a = self._current()
        if not a:
            return
        dlg = AnomalyDialog(self, store=self.store, item=a)
        if dlg.exec() == AnomalyDialog.Accepted:
            f = dlg.fields()
            if not f["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            for att in dlg.removed:
                self.store.remove_attachment_file(att.get("stored", ""))
            self.store.update_anomaly(a["id"], **f)

    def delete_current(self):
        a = self._current()
        if not a:
            return
        ret = QMessageBox.question(
            self, "删除确认",
            f"确定删除异常「{a.get('title', '')}」？\n记录会进入回收站保留3天，可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.store.delete("anomalies", a["id"])

    # ---- 图表与 PPT ----

    def _chart_dir(self):
        return os.path.join(self.store.data_dir, "charts")

    def preview_timeline(self):
        a = self._current()
        if not a or not a.get("timeline"):
            return
        svg = svg_charts.timeline_svg(a["timeline"], title=a.get("title", "时间线分析"))
        ChartPreviewDialog(svg, f"时间线 · {a.get('title', '')}", self,
                           f"timeline_{common.today_str()}.html").exec()

    def preview_fishbone(self):
        a = self._current()
        if not a:
            return
        svg = svg_charts.fishbone_svg(a.get("fishbone", {}), problem=a.get("title", ""))
        ChartPreviewDialog(svg, f"鱼骨图 · {a.get('title', '')}", self,
                           f"fishbone_{common.today_str()}.html").exec()

    def generate_ppt(self):
        a = self._current()
        if not a:
            return
        from ..ppt_report import generate_ppt
        default = os.path.join(os.path.expanduser("~"), "Desktop",
                               f"异常报告_{a.get('title', 'report')}_{common.today_str()}.pptx")
        path, _ = QFileDialog.getSaveFileName(self, "生成单页汇报PPT",
                                              default, "PowerPoint (*.pptx)")
        if not path:
            return
        imgs = [self.store.attachment_path(att.get("stored", ""))
                for att in a.get("images", [])]
        try:
            generate_ppt(a, imgs, path)
        except Exception as e:  # 生成失败要给出明确原因
            QMessageBox.critical(self, "生成失败", f"PPT生成出错：\n{e}")
            return
        ret = QMessageBox.question(self, "生成成功", f"PPT已保存到：\n{path}\n\n立即打开查看？",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret == QMessageBox.Yes:
            os.startfile(path)

    # ---- 搜索接入 ----

    def search_records(self):
        records = []
        for a in self.store.data["anomalies"]:
            fields = {label.split(" ")[0]: a.get(key, "")
                      for key, label in _SECTION_LABELS}
            tl = " ".join(f"{e.get('time', '')} {e.get('event', '')}"
                          for e in a.get("timeline", []))
            if tl:
                fields["时间线"] = tl
            fb = " ".join(" ".join(v) for v in (a.get("fishbone") or {}).values())
            if fb:
                fields["鱼骨图"] = fb
            records.append(SearchRecord(
                module_key=self.module_key, module_name=self.module_name,
                item_id=a["id"], title=a.get("title", "") or "（无标题）",
                fields=fields, time_text=common.fmt_d(a.get("created_at", "")),
            ))
        return records

    def locate(self, item_id):
        self.current_id = item_id
        self.refresh()
