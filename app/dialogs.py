# -*- coding: utf-8 -*-
"""各模块的新增/编辑对话框。

约定：dialog 返回 QDialog.Accepted 表示用户确认保存，字段从对话框属性读取。
"""
import os

from PySide6.QtCore import QDateTime, QDate, Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDateTimeEdit, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget, QDialogButtonBox,
    QAbstractItemView,
)

from . import common
from .data_store import PRIORITIES


def _buttons(dlg, ok_text="保存"):
    box = QDialogButtonBox()
    ok = box.addButton(ok_text, QDialogButtonBox.AcceptRole)
    box.addButton("取消", QDialogButtonBox.RejectRole)
    ok.setObjectName("primary")
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    return box


class TaskDialog(QDialog):
    """缓急 - 新增/编辑任务。"""

    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.setWindowTitle("编辑任务" if task else "新增任务")
        self.setMinimumWidth(430)

        self.edDesc = QPlainTextEdit()
        self.edDesc.setPlaceholderText("要做什么？")
        self.edDesc.setFixedHeight(56)
        self.edDiff = QPlainTextEdit()
        self.edDiff.setPlaceholderText("难点 / 注意事项（可留空）")
        self.edDiff.setFixedHeight(56)

        self.edStart = QDateTimeEdit(QDateTime.currentDateTime())
        self.edStart.setCalendarPopup(True)
        self.edStart.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.edDue = QDateEdit(QDate.currentDate().addDays(7))
        self.edDue.setCalendarPopup(True)
        self.edDue.setDisplayFormat("yyyy-MM-dd")
        self.cbPri = QComboBox()
        self.cbPri.addItems(PRIORITIES)
        self.cbPri.setCurrentText("中")

        form = QFormLayout()
        form.addRow("事情描述*", self.edDesc)
        form.addRow("难点", self.edDiff)
        form.addRow("开始时间", self.edStart)
        form.addRow("Due Day", self.edDue)
        form.addRow("优先级", self.cbPri)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(_buttons(self))

        if task:
            self.edDesc.setPlainText(task.get("desc", ""))
            self.edDiff.setPlainText(task.get("difficulty", ""))
            self._set_dt(self.edStart, task.get("start_time"))
            self._set_d(self.edDue, task.get("due_day"))
            self.cbPri.setCurrentText(task.get("priority", "中"))

    def _set_dt(self, editor, value):
        dt = QDateTime.fromString(value, common.DT_FORMAT)
        if value and dt.isValid():
            editor.setDateTime(dt)

    def _set_d(self, editor, value):
        d = QDate.fromString((value or "")[:10], "yyyy-MM-dd")
        if value and d.isValid():
            editor.setDate(d)

    def fields(self):
        return {
            "desc": self.edDesc.toPlainText().strip(),
            "difficulty": self.edDiff.toPlainText().strip(),
            "start_time": self.edStart.dateTime().toString(common.DT_FORMAT),
            "due_day": self.edDue.date().toString("yyyy-MM-dd"),
            "priority": self.cbPri.currentText(),
        }


class MemoDialog(QDialog):
    """帮记 - 新增/编辑备忘。"""

    def __init__(self, parent=None, memo=None):
        super().__init__(parent)
        self.setWindowTitle("编辑备忘" if memo else "新增备忘")
        self.setMinimumWidth(430)

        self.edContent = QPlainTextEdit()
        self.edContent.setPlaceholderText("要记住的内容…")
        self.edContent.setFixedHeight(110)
        self.edTime = QDateTimeEdit(QDateTime.currentDateTime())
        self.edTime.setCalendarPopup(True)
        self.edTime.setDisplayFormat("yyyy-MM-dd HH:mm")

        form = QFormLayout()
        form.addRow("内容*", self.edContent)
        form.addRow("时间", self.edTime)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(_buttons(self))

        if memo:
            self.edContent.setPlainText(memo.get("content", ""))
            dt = QDateTime.fromString(memo.get("time", ""), common.DT_FORMAT)
            if memo.get("time") and dt.isValid():
                self.edTime.setDateTime(dt)

    def fields(self):
        return {
            "content": self.edContent.toPlainText().strip(),
            "time": self.edTime.dateTime().toString(common.DT_FORMAT),
        }


class QuestionDialog(QDialog):
    """解惑 - 新增/编辑问题。"""

    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.setWindowTitle("编辑问题" if item else "新增问题")
        self.setMinimumWidth(460)

        self.edQ = QPlainTextEdit()
        self.edQ.setPlaceholderText("工作中不明白的问题…")
        self.edQ.setFixedHeight(56)
        self.edTime = QDateTimeEdit(QDateTime.currentDateTime())
        self.edTime.setCalendarPopup(True)
        self.edTime.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.edSol = QPlainTextEdit()
        self.edSol.setPlaceholderText("解决方案（还没有可先留空，之后再补）")

        form = QFormLayout()
        form.addRow("问题*", self.edQ)
        form.addRow("时间", self.edTime)
        form.addRow("解决方案", self.edSol)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(_buttons(self))

        if item:
            self.edQ.setPlainText(item.get("question", ""))
            self.edSol.setPlainText(item.get("solution", ""))
            dt = QDateTime.fromString(item.get("time", ""), common.DT_FORMAT)
            if item.get("time") and dt.isValid():
                self.edTime.setDateTime(dt)

    def fields(self):
        return {
            "question": self.edQ.toPlainText().strip(),
            "time": self.edTime.dateTime().toString(common.DT_FORMAT),
            "solution": self.edSol.toPlainText().strip(),
        }


class SopDialog(QDialog):
    """存知 - 新增/编辑SOP。支持添加图片和PPT附件。"""

    def __init__(self, parent=None, store=None, sop=None):
        super().__init__(parent)
        self.store = store
        self.sop_id = sop["id"] if sop else common.new_id()
        self.existing = dict(sop) if sop else None
        # 附件编辑状态：{"name","stored","kind","text"}；removed 里记录要删除的旧附件
        self.attachments = [dict(a) for a in (sop.get("attachments", []) if sop else [])]
        self.removed = []
        self.setWindowTitle("编辑SOP" if sop else "新增SOP")
        self.setMinimumSize(560, 520)

        self.edTitle = QLineEdit()
        self.edTitle.setPlaceholderText("SOP标题，例如：针卡清洗SOP")
        self.edContent = QPlainTextEdit()
        self.edContent.setPlaceholderText("正文内容…（步骤、参数、注意事项等）")

        self.attList = QListWidget()
        self.attList.setIconSize(QSize(28, 28))
        self.attList.setSelectionMode(QAbstractItemView.SingleSelection)

        btnAddImg = QPushButton("添加图片")
        btnAddPpt = QPushButton("添加PPT")
        btnDel = QPushButton("移除选中")
        btnDel.setObjectName("danger")
        btnAddImg.clicked.connect(lambda: self._add_files("image"))
        btnAddPpt.clicked.connect(lambda: self._add_files("ppt"))
        btnDel.clicked.connect(self._remove_selected)

        attBtns = QHBoxLayout()
        attBtns.addWidget(btnAddImg)
        attBtns.addWidget(btnAddPpt)
        attBtns.addWidget(btnDel)
        attBtns.addStretch(1)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("标题*", self.edTitle)
        lay.addLayout(form)
        lay.addWidget(QLabel("正文内容"))
        lay.addWidget(self.edContent, 1)
        lay.addWidget(QLabel("附件（支持图片 / PPT，可多个）"))
        lay.addLayout(attBtns)
        lay.addWidget(self.attList, 1)
        lay.addWidget(_buttons(self))

        self.edTitle.setText(sop.get("title", "") if sop else "")
        self.edContent.setPlainText(sop.get("content", "") if sop else "")
        self._reload_att_list()

    def _reload_att_list(self):
        self.attList.clear()
        for att in self.attachments:
            item = QListWidgetItem(att["name"])
            tip = {"image": "图片", "ppt": "PPT", "other": "文件"}.get(att["kind"], "文件")
            item.setToolTip(f"{tip}　{att['name']}")
            if att["kind"] == "image" and self.store:
                pm = QPixmap(self.store.attachment_path(att["stored"]))
                if not pm.isNull():
                    from PySide6.QtGui import QIcon
                    item.setIcon(QIcon(pm.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self.attList.addItem(item)

    def _add_files(self, kind: str):
        if not self.store:
            return
        if kind == "image":
            paths, _ = QFileDialog.getOpenFileNames(
                self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        else:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "选择PPT", "", "演示文稿 (*.pptx *.ppt)")
        for path in paths:
            try:
                att = self.store.add_attachment(self.sop_id, path)
            except OSError as e:
                QMessageBox.warning(self, "添加失败", f"无法添加文件：\n{path}\n\n{e}")
                continue
            self.attachments.append(att)
        if paths:
            self._reload_att_list()

    def _remove_selected(self):
        row = self.attList.currentRow()
        if row < 0:
            return
        att = self.attachments.pop(row)
        # 已存在于正式数据里的附件，确认后删除；新增未保存的直接丢弃
        if self.existing and att in [dict(a) for a in self.existing.get("attachments", [])]:
            self.removed.append(att)
        self._reload_att_list()

    def fields(self):
        return {
            "title": self.edTitle.text().strip(),
            "content": self.edContent.toPlainText(),
            "attachments": self.attachments,
        }


class ImageViewDialog(QDialog):
    """查看大图。"""

    def __init__(self, image_path: str, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 640)
        from PySide6.QtWidgets import QScrollArea, QSizePolicy
        label = QLabel()
        pm = QPixmap(image_path)
        screen = self.screen().availableGeometry()
        scaled = pm.scaled(int(screen.width() * 0.8), int(screen.height() * 0.8),
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)
        label.setAlignment(Qt.AlignCenter)
        area = QScrollArea()
        area.setWidget(label)
        area.setAlignment(Qt.AlignCenter)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(area)

