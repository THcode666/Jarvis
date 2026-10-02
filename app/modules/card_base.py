# -*- coding: utf-8 -*-
"""帮记/解惑共用的卡片列表基类。

新增一个"卡片式"模块（比如以后想加"人脉/设备台账"）时：
继承 CardListModule，实现 items() / make_card() / add_item() 即可接入主界面。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QSizePolicy,
)


class CardListModule(QWidget):
    module_key = ""
    module_name = ""
    page_title = ""

    def __init__(self, store):
        super().__init__()
        self.store = store

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        lbl = QLabel(self.page_title)
        lbl.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnAdd = QPushButton("＋ 新增")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(self.add_item)
        head.addWidget(lbl)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(btnAdd)
        lay.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cardsHost = QWidget()
        self.cardsLay = QVBoxLayout(self.cardsHost)
        self.cardsLay.setContentsMargins(0, 0, 6, 0)
        self.cardsLay.setSpacing(8)
        self.cardsLay.addStretch(1)
        self.scroll.setWidget(self.cardsHost)
        lay.addWidget(self.scroll, 1)

        self.emptyLabel = None

    # ---- 子类需要实现 ----

    def items(self):
        """返回该模块的数据列表（按显示顺序）。"""
        raise NotImplementedError

    def make_card(self, item) -> QWidget:
        """为一条数据构造卡片。"""
        raise NotImplementedError

    def add_item(self):
        raise NotImplementedError

    # ---- 通用 ----

    def refresh(self):
        while self.cardsLay.count() > 1:
            it = self.cardsLay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)  # 立即从布局移除，不等事件循环
                w.deleteLater()
        data = self.items()
        for item in data:
            self.cardsLay.insertWidget(self.cardsLay.count() - 1, self.make_card(item))
        self.lblCount.setText(f"共 {len(data)} 条")
        self._update_empty(len(data))

    def _update_empty(self, n):
        if n == 0 and self.emptyLabel is None:
            self.emptyLabel = QLabel("还没有内容，点击右上角「＋ 新增」添加第一条")
            self.emptyLabel.setObjectName("muted")
            self.emptyLabel.setAlignment(Qt.AlignCenter)
            self.emptyLabel.setContentsMargins(0, 60, 0, 0)
            self.cardsLay.insertWidget(0, self.emptyLabel)
        elif n > 0 and self.emptyLabel is not None:
            self.cardsLay.removeWidget(self.emptyLabel)
            self.emptyLabel.deleteLater()
            self.emptyLabel = None

    def confirm_delete(self, text: str) -> bool:
        ret = QMessageBox.question(self, "删除确认", f"确定删除？\n\n{text}",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return ret == QMessageBox.Yes

    # ---- 搜索结果卡片可复用的高亮辅助 ----

    @staticmethod
    def _wrap_card(content_widget: QWidget) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(5)
        v.addWidget(content_widget)
        return frame


def card_row(center: QWidget, buttons: list) -> QWidget:
    """一行：左侧内容 + 右侧竖排小按钮。"""
    bar = QWidget()
    h = QHBoxLayout(bar)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    h.addWidget(center, 1)
    col = QVBoxLayout()
    col.setSpacing(3)
    for b in buttons:
        col.addWidget(b)
    h.addLayout(col)
    return bar
