# -*- coding: utf-8 -*-
"""模块二「帮记」：备忘录。记录需要记住的内容 + 时间。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .. import common
from ..dialogs import MemoDialog
from ..search import SearchRecord
from .card_base import CardListModule, card_row


class MemoModule(CardListModule):
    module_key = "memos"
    module_name = "帮记"
    page_title = "帮记 · 备忘录"

    def items(self):
        return sorted(self.store.data["memos"],
                      key=lambda m: m.get("time", ""), reverse=True)

    def make_card(self, memo) -> QWidget:
        center = QWidget()
        v = QVBoxLayout(center)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        content = QLabel(memo.get("content", ""))
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextSelectableByMouse)
        time_lbl = QLabel(f"🕒 {common.fmt_dt(memo.get('time', ''))}")
        time_lbl.setObjectName("cardTime")
        v.addWidget(content)
        v.addWidget(time_lbl)

        mid = memo["id"]
        btnEdit = QPushButton("编辑")
        btnEdit.clicked.connect(lambda: self.edit_item(mid))
        btnDel = QPushButton("删除")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(lambda: self.delete_item(mid))
        return self._wrap_card(card_row(center, [btnEdit, btnDel]))

    def add_item(self):
        dlg = MemoDialog(self)
        if dlg.exec() == MemoDialog.Accepted:
            f = dlg.fields()
            if not f["content"]:
                return
            self.store.add_memo(f["content"], f["time"])

    def edit_item(self, memo_id):
        memo = self.store.find("memos", memo_id)
        if not memo:
            return
        dlg = MemoDialog(self, memo=memo)
        if dlg.exec() == MemoDialog.Accepted:
            f = dlg.fields()
            if not f["content"]:
                return
            self.store.update_memo(memo_id, **f)

    def delete_item(self, memo_id):
        memo = self.store.find("memos", memo_id)
        if memo and self.confirm_delete(memo.get("content", "")[:80]):
            self.store.delete("memos", memo_id)

    def search_records(self):
        return [
            SearchRecord(
                module_key=self.module_key, module_name=self.module_name,
                item_id=m["id"], title=(m.get("content", "")[:40] or "（空）"),
                fields={"内容": m.get("content", "")},
                time_text=common.fmt_dt(m.get("time", "")),
            )
            for m in self.store.data["memos"]
        ]

    def locate(self, item_id):
        """搜索跳转：滚动并闪烁定位卡片（刷新列表即可让其出现在正确排序位）。"""
        self.refresh()
