# -*- coding: utf-8 -*-
"""模块四「存知」：SOP / 知识库。

- 标题 + 正文（纯文本）
- 附件支持图片（内嵌预览、点击看大图）和 PPT（.pptx 抽取文字预览与搜索；
  双击可调用系统Office/WPS打开原文件）
- 左侧标题列表（支持按标题快速筛选），右侧详情
"""
import os

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .. import common
from ..dialogs import SopDialog
from ..search import SearchRecord


class SopModule(QWidget):
    module_key = "sops"
    module_name = "存知"
    itemActivated = Signal(str)  # 供未来扩展

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.current_id = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        lbl = QLabel("存知 · SOP知识库")
        lbl.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnAdd = QPushButton("＋ 新增SOP")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(self.add_item)
        btnEdit = QPushButton("编辑")
        btnEdit.clicked.connect(self.edit_current)
        btnDel = QPushButton("删除")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(self.delete_current)
        head.addWidget(lbl)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(btnEdit)
        head.addWidget(btnDel)
        head.addWidget(btnAdd)
        lay.addLayout(head)

        self.edFilter = QLineEdit()
        self.edFilter.setPlaceholderText("按标题快速筛选…")
        self.edFilter.setClearButtonEnabled(True)
        self.edFilter.textChanged.connect(self._apply_filter)
        lay.addWidget(self.edFilter)

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
        splitter.setSizes([260, 700])
        lay.addWidget(splitter, 1)

    # ---------- 详情区 ----------

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
        self.detailLay.setSpacing(10)
        self.detailLay.addStretch(1)
        self.detailArea.setWidget(self.detailHost)
        v.addWidget(self.detailArea)
        self._show_empty_detail()
        return host

    def _clear_detail(self):
        while self.detailLay.count() > 1:
            it = self.detailLay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)  # 立即从布局移除，不等事件循环
                w.deleteLater()

    def _show_empty_detail(self):
        self._clear_detail()
        lbl = QLabel("从左侧选择一条SOP查看详情\n\n还没有内容？点击右上角「＋ 新增SOP」")
        lbl.setObjectName("muted")
        lbl.setAlignment(Qt.AlignCenter)
        self.detailLay.insertWidget(0, lbl)

    # ---------- 刷新与选择 ----------

    def refresh(self):
        selected = self.current_id
        self.list.blockSignals(True)
        self.list.clear()
        sops = sorted(self.store.data["sops"], key=lambda s: s.get("created_at", ""))
        for i, sop in enumerate(sops):
            title = sop.get("title") or "（无标题）"
            n_att = len(sop.get("attachments", []))
            text = f"{title}\n📎 {n_att} 个附件 · {common.fmt_d(sop.get('created_at', ''))}" if n_att \
                else f"{title}\n{common.fmt_d(sop.get('created_at', ''))}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, sop["id"])
            self.list.addItem(item)
            if sop["id"] == selected:
                self.list.setCurrentRow(i)
        self.list.blockSignals(False)
        self.lblCount.setText(f"共 {len(sops)} 篇")
        self._apply_filter(self.edFilter.text())
        if self.list.currentRow() < 0 and self.list.count() > 0:
            self.list.setCurrentRow(0)
        elif self.list.count() == 0:
            self.current_id = None
            self._show_empty_detail()

    def _apply_filter(self, text):
        text = (text or "").lower().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _on_select(self, row):
        if row < 0:
            return
        item = self.list.item(row)
        self.current_id = item.data(Qt.UserRole)
        self._render_detail()

    def _current_sop(self):
        return self.store.find("sops", self.current_id) if self.current_id else None

    def _render_detail(self):
        sop = self._current_sop()
        self._clear_detail()
        if not sop:
            self._show_empty_detail()
            return

        title = QLabel(sop.get("title", ""))
        title.setObjectName("pageHead")
        title.setWordWrap(True)
        meta = QLabel(f"创建于 {common.fmt_dt(sop.get('created_at', ''))}")
        meta.setObjectName("cardTime")
        self.detailLay.insertWidget(0, meta)
        self.detailLay.insertWidget(0, title)

        content = (sop.get("content") or "").strip()
        if content:
            body = QLabel(content)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.detailLay.insertWidget(2, body)

        for att in sop.get("attachments", []):
            self.detailLay.insertWidget(self.detailLay.count() - 1,
                                        self._make_att_widget(att))

    def _make_att_widget(self, att) -> QWidget:
        path = self.store.attachment_path(att.get("stored", ""))
        box = QFrame()
        box.setObjectName("card")
        h = QHBoxLayout(box)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)

        if att.get("kind") == "image" and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                thumb = QLabel()
                thumb.setPixmap(pm.scaledToWidth(360, Qt.SmoothTransformation))
                thumb.setCursor(Qt.PointingHandCursor)
                name = att.get("name", "图片")
                thumb.setToolTip(f"点击查看大图：{name}")
                title = att.get("name", "图片")

                def open_big(_=None, p=path, t=title):
                    from ..dialogs import ImageViewDialog
                    ImageViewDialog(p, t, self).exec()
                thumb.mouseReleaseEvent = lambda ev, fn=open_big: fn()
                h.addWidget(thumb)
            else:
                h.addWidget(QLabel(f"🖼 {att.get('name', '')}（图片文件丢失）"))
        elif att.get("kind") == "ppt":
            v = QVBoxLayout()
            v.setSpacing(4)
            name_lbl = QLabel(f"📽 PPT：{att.get('name', '')}")
            name_lbl.setObjectName("cardTitle")
            v.addWidget(name_lbl)
            text = (att.get("text") or "").strip()
            if text:
                prev = QLabel(text[:500] + ("…" if len(text) > 500 else ""))
                prev.setWordWrap(True)
                prev.setTextInteractionFlags(Qt.TextSelectableByMouse)
                prev.setStyleSheet("color:#a9bdd6;")
                v.addWidget(prev)
            else:
                hint = QLabel("（未解析到文字内容，双击按钮用本机Office/WPS打开）")
                hint.setStyleSheet("color:#7d92ad;font-style:italic;")
                v.addWidget(hint)
            btnOpen = QPushButton("打开文件")
            btnOpen.clicked.connect(lambda _, p=path: self._open_external(p))
            center = QWidget()
            center.setLayout(v)
            h.addWidget(center, 1)
            h.addWidget(btnOpen)
        else:
            name_lbl = QLabel(f"📎 {att.get('name', '附件')}（文件可能已丢失）")
            h.addWidget(name_lbl)
        return box

    @staticmethod
    def _open_external(path):
        if os.path.exists(path):
            os.startfile(path)  # noqa Windows专用：调用系统默认程序打开

    # ---------- 增删改 ----------

    def add_item(self):
        dlg = SopDialog(self, store=self.store)
        if dlg.exec() == SopDialog.Accepted:
            f = dlg.fields()
            if not f["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            sop = self.store.add_sop(f["title"], f["content"], f["attachments"])
            self.current_id = sop["id"]

    def edit_current(self):
        sop = self._current_sop()
        if not sop:
            return
        dlg = SopDialog(self, store=self.store, sop=sop)
        if dlg.exec() == SopDialog.Accepted:
            f = dlg.fields()
            if not f["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            # 处理对话框中标记删除的旧附件
            for att in dlg.removed:
                self.store.remove_attachment_file(att.get("stored", ""))
            self.store.update_sop(sop["id"], **f)

    def delete_current(self):
        sop = self._current_sop()
        if not sop:
            return
        ret = QMessageBox.question(self, "删除确认",
                                   f"确定删除SOP「{sop.get('title', '')}」？\n其附件文件将一并删除。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.store.delete("sops", sop["id"])
            self.current_id = None

    # ---------- 搜索接入 ----------

    def search_records(self):
        records = []
        for s in self.store.data["sops"]:
            fields = {"标题": s.get("title", ""), "正文": s.get("content", "")}
            att_names, att_texts = [], []
            for att in s.get("attachments", []):
                att_names.append(att.get("name", ""))
                if att.get("text"):
                    att_texts.append(att["text"])
            if att_names:
                fields["附件"] = " ".join(att_names)
            if att_texts:
                fields["PPT文字"] = " ".join(att_texts)
            records.append(SearchRecord(
                module_key=self.module_key, module_name=self.module_name,
                item_id=s["id"], title=s.get("title", "") or "（无标题）",
                fields=fields, time_text=common.fmt_d(s.get("created_at", "")),
            ))
        return records

    def locate(self, item_id):
        self.current_id = item_id
        self.edFilter.clear()
        self.refresh()
