# -*- coding: utf-8 -*-
"""模块三「解惑」：工作疑难问题 + 时间 + 解决方案。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .. import common
from ..dialogs import QuestionDialog
from ..search import SearchRecord
from .card_base import CardListModule, card_row


class QuestionModule(CardListModule):
    module_key = "questions"
    module_name = "解惑"
    page_title = "解惑 · 疑难问题"

    def items(self):
        return sorted(self.store.data["questions"],
                      key=lambda q: q.get("time", ""), reverse=True)

    def make_card(self, item) -> QWidget:
        center = QWidget()
        v = QVBoxLayout(center)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        q = QLabel(f"❓ {item.get('question', '')}")
        q.setWordWrap(True)
        q.setTextInteractionFlags(Qt.TextSelectableByMouse)
        time_lbl = QLabel(f"🕒 {common.fmt_dt(item.get('time', ''))}")
        time_lbl.setObjectName("cardTime")
        v.addWidget(q)
        v.addWidget(time_lbl)

        sol = (item.get("solution") or "").strip()
        sol_lbl = QLabel(f"✅ 解决方案：{sol}" if sol else "⏳ 待解决（可在编辑中补充方案）")
        sol_lbl.setWordWrap(True)
        sol_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sol_lbl.setStyleSheet(
            "color:#3ddc97;" if sol else "color:#7d92ad;font-style:italic;")
        v.addWidget(sol_lbl)

        qid = item["id"]
        btnEdit = QPushButton("编辑")
        btnEdit.clicked.connect(lambda: self.edit_item(qid))
        btnDel = QPushButton("删除")
        btnDel.setObjectName("danger")
        btnDel.clicked.connect(lambda: self.delete_item(qid))
        return self._wrap_card(card_row(center, [btnEdit, btnDel]))

    def add_item(self):
        dlg = QuestionDialog(self)
        if dlg.exec() == QuestionDialog.Accepted:
            f = dlg.fields()
            if not f["question"]:
                return
            self.store.add_question(f["question"], f["time"], f["solution"])

    def edit_item(self, q_id):
        item = self.store.find("questions", q_id)
        if not item:
            return
        dlg = QuestionDialog(self, item=item)
        if dlg.exec() == QuestionDialog.Accepted:
            f = dlg.fields()
            if not f["question"]:
                return
            self.store.update_question(q_id, **f)

    def delete_item(self, q_id):
        item = self.store.find("questions", q_id)
        if item and self.confirm_delete(item.get("question", "")[:80]):
            self.store.delete("questions", q_id)

    def search_records(self):
        return [
            SearchRecord(
                module_key=self.module_key, module_name=self.module_name,
                item_id=x["id"], title=(x.get("question", "")[:40] or "（空）"),
                fields={"问题": x.get("question", ""), "解决方案": x.get("solution", "")},
                time_text=common.fmt_dt(x.get("time", "")),
            )
            for x in self.store.data["questions"]
        ]

    def locate(self, item_id):
        self.refresh()
