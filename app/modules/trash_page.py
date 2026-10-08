# -*- coding: utf-8 -*-
"""回收站：软件内删除的记录保留3天，可恢复；超期自动彻底清除。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import common

MODULE_NAMES = {"tasks": "缓急·任务", "memos": "帮记·备忘",
                "questions": "解惑·问题", "sops": "存知·SOP",
                "dailies": "每日任务", "anomalies": "解异·异常"}


def _summary(entry) -> str:
    item = entry.get("item") or {}
    for key in ("desc", "title", "question", "content"):
        if item.get(key):
            return str(item[key])[:80]
    return "（无内容）"


class TrashModule(QWidget):
    module_key = None  # 不参与全局搜索
    module_name = "回收站"

    def __init__(self, store):
        super().__init__()
        self.store = store
        store.changed.connect(self.refresh)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        lbl = QLabel("回收站 · 误删保护")
        lbl.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnEmpty = QPushButton("清空回收站")
        btnEmpty.setObjectName("danger")
        btnEmpty.clicked.connect(self.empty_all)
        head.addWidget(lbl)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(btnEmpty)
        lay.addLayout(head)

        hint = QLabel("删除的记录在这里保留 3 天（保留期内可恢复），超过 3 天自动彻底删除。"
                      "彻底删除时才会同时清理SOP附件文件。")
        hint.setObjectName("muted")
        lay.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.v = QVBoxLayout(self.host)
        self.v.setContentsMargins(0, 0, 6, 0)
        self.v.setSpacing(8)
        self.v.addStretch(1)
        self.scroll.setWidget(self.host)
        lay.addWidget(self.scroll, 1)

    def refresh(self):
        while self.v.count() > 1:
            it = self.v.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        entries = sorted(self.store.data["trash"],
                         key=lambda x: x.get("deleted_at", ""), reverse=True)
        self.lblCount.setText(f"{len(entries)} 条 · 保留3天")
        for entry in entries:
            self.v.insertWidget(self.v.count() - 1, self._card(entry))
        if not entries:
            empty = QLabel("回收站是空的")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignCenter)
            empty.setContentsMargins(0, 50, 0, 0)
            self.v.insertWidget(0, empty)

    def _card(self, entry) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 9, 12, 9)
        h.setSpacing(10)

        tag = QLabel(MODULE_NAMES.get(entry.get("module", ""), "记录"))
        tag.setStyleSheet("color:#04121f;background:#29c6ff;border-radius:3px;"
                          "padding:1px 7px;font-size:11px;font-weight:bold;")
        center = QWidget()
        v = QVBoxLayout(center)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        title = QLabel(_summary(entry))
        title.setWordWrap(True)
        meta = QLabel(f"删除于 {common.fmt_dt(entry.get('deleted_at', ''))} · "
                      f"{self.store.trash_age_text(entry.get('deleted_at', ''))}")
        meta.setObjectName("cardTime")
        v.addWidget(title)
        v.addWidget(meta)

        h.addWidget(tag)
        h.addWidget(center, 1)

        tid = entry["id"]
        btnRestore = QPushButton("恢复")
        btnRestore.setObjectName("primary")
        btnRestore.clicked.connect(lambda _, i=tid: self.restore(i))
        btnPurge = QPushButton("彻底删除")
        btnPurge.setObjectName("danger")
        btnPurge.clicked.connect(lambda _, i=tid: self.purge_one(i))
        h.addWidget(btnRestore)
        h.addWidget(btnPurge)
        return frame

    def restore(self, trash_id):
        if self.store.restore(trash_id):
            QMessageBox.information(self, "已恢复", "记录已恢复到原模块。")

    def purge_one(self, trash_id):
        ret = QMessageBox.question(
            self, "彻底删除确认", "彻底删除后无法恢复（SOP附件文件将一并删除）。确定？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.store.purge_one(trash_id)

    def empty_all(self):
        ret = QMessageBox.question(
            self, "清空回收站",
            "将立即彻底删除回收站里的全部记录（SOP附件一并删除），无法恢复。确定？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.store.purge_trash(all_items=True)
