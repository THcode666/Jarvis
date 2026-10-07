# -*- coding: utf-8 -*-
"""全局搜索结果页：展示跨模块命中的结果，点击跳转到对应模块。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class SearchPage(QWidget):
    """searchRequested(module_key, item_id, open_editor)：跳转信号。"""
    searchRequested = Signal(str, str, bool)

    def __init__(self, store):
        super().__init__()
        self.store = store

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.lblHead = QLabel("搜索")
        self.lblHead.setObjectName("pageHead")
        self.lblSummary = QLabel("")
        self.lblSummary.setObjectName("muted")
        head.addWidget(self.lblHead)
        head.addWidget(self.lblSummary)
        head.addStretch(1)
        lay.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.v = QVBoxLayout(self.host)
        self.v.setContentsMargins(0, 0, 6, 0)
        self.v.setSpacing(8)
        self.v.addStretch(1)
        self.scroll.setWidget(self.host)
        lay.addWidget(self.scroll, 1)

    def show_results(self, query: str, results: list):
        self.lblHead.setText(f"搜索 “{query}”")
        self.lblSummary.setText(f"{len(results)} 条结果" if results else "没有找到相关内容")

        while self.v.count() > 1:
            it = self.v.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)  # 立即从布局移除，不等事件循环
                w.deleteLater()

        if not results:
            empty = QLabel("换个关键词试试，或减少关键词个数。\n搜索范围：任务描述/难点、备忘内容、问题/解决方案、SOP标题/正文/PPT文字/附件名。\n输入拼音首字母也能命中（如 hzk → 换针卡）。")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignCenter)
            empty.setContentsMargins(0, 60, 0, 0)
            self.v.insertWidget(0, empty)
            return

        # 按模块分组显示
        order = ["tasks", "memos", "questions", "sops"]
        name_map = {"tasks": "缓急 · 任务", "memos": "帮记 · 备忘",
                    "questions": "解惑 · 问题", "sops": "存知 · SOP"}
        groups = {}
        for r in results:
            groups.setdefault(r.record.module_key, []).append(r)

        for key in order:
            if key not in groups:
                continue
            cap = QLabel(f"{name_map.get(key, key)}（{len(groups[key])}）")
            cap.setStyleSheet("color:#29c6ff;font-weight:bold;margin-top:6px;")
            self.v.insertWidget(self.v.count() - 1, cap)
            for r in groups[key]:
                self.v.insertWidget(self.v.count() - 1, self._result_card(r))

    def _result_card(self, r) -> QFrame:
        rec = r.record
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel(rec.title or "（无标题）")
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        tag = QLabel(rec.module_name)
        tag.setStyleSheet(
            "color:#04121f;background:#29c6ff;border-radius:3px;padding:1px 7px;font-size:11px;font-weight:bold;")
        time_lbl = QLabel(rec.time_text)
        time_lbl.setObjectName("cardTime")
        top.addWidget(tag)
        top.addWidget(title, 1)
        top.addWidget(time_lbl)
        v.addLayout(top)

        if r.snippet_html:
            snip = QLabel(r.snippet_html)
            snip.setTextFormat(Qt.RichText)
            snip.setWordWrap(True)
            snip.setStyleSheet("color:#a9bdd6;")
            v.addWidget(snip)
            if r.via_pinyin and "<font" not in r.snippet_html:
                tag_py = QLabel("拼音匹配")
                tag_py.setStyleSheet("color:#7d92ad;font-size:11px;")
                v.addWidget(tag_py)

        bottom = QHBoxLayout()
        hint = QLabel("点击卡片跳转到该条内容")
        hint.setObjectName("cardTime")
        bottom.addWidget(hint)
        bottom.addStretch(1)
        btnEdit = QPushButton("打开/编辑")
        btnEdit.clicked.connect(
            lambda _, k=rec.module_key, i=rec.item_id: self.searchRequested.emit(k, i, True))
        bottom.addWidget(btnEdit)
        v.addLayout(bottom)

        def jump(_=None):
            self.searchRequested.emit(rec.module_key, rec.item_id, False)
        frame.setCursor(Qt.PointingHandCursor)
        frame.mouseReleaseEvent = jump
        return frame
