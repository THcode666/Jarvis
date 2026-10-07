# -*- coding: utf-8 -*-
"""模块一「缓急」：任务清单。

- 新增/编辑/删除任务（描述/难点/开始时间/Due Day/优先级 高中低弱）
- 按 优先级 或 Due Day 排序
- 状态：未完成 / 已完成；已完成的进入"已完成事项"页签，可一键还原回清单
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView,
)

from .. import common
from ..data_store import PRIORITIES, PRIORITY_ORDER, STATUS_DONE, STATUS_TODO
from ..dialogs import TaskDialog
from ..search import SearchRecord

_PRIORITY_COLOR = {"高": "#ff6b6b", "中": "#ffb64d", "低": "#29c6ff", "弱": "#7d92ad"}


class TaskModule(QWidget):
    module_key = "tasks"
    module_name = "缓急"

    def __init__(self, store, jump_signal=None):
        super().__init__()
        self.store = store
        store.changed.connect(self.refresh)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.lblHead = QLabel("缓急 · 任务清单")
        self.lblHead.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnAdd = QPushButton("＋ 新增任务")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(self.add_item)
        head.addWidget(self.lblHead)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(QLabel("排序："))
        self.cbSort = QComboBox()
        self.cbSort.addItems(["按优先级", "按Due Day"])
        self.cbSort.currentIndexChanged.connect(self.refresh)
        head.addWidget(self.cbSort)
        head.addWidget(btnAdd)
        lay.addLayout(head)

        self.tabs = QTabWidget()
        self.tableTodo = self._make_table()
        self.tableDone = self._make_table()
        self.tabs.addTab(self._wrap(self.tableTodo), "进行中")
        self.tabs.addTab(self._wrap(self.tableDone), "已完成事项")
        lay.addWidget(self.tabs, 1)

    def _wrap(self, w):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 6, 0, 0)
        v.addWidget(w)
        return box

    def _make_table(self):
        t = QTableWidget(0, 7)
        t.setHorizontalHeaderLabels(
            ["优先级", "事情描述", "难点", "开始时间", "Due Day", "状态", "操作"])
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setWordWrap(True)
        t.doubleClicked.connect(lambda idx: self.edit_by_table(t, idx))
        h = t.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)   # 描述列拉伸
        h.setSectionResizeMode(2, QHeaderView.Stretch)   # 难点列拉伸
        for col in (0, 3, 4, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        return t

    # ---------- 刷新 ----------

    def refresh(self):
        tasks = self.store.data["tasks"]
        todo = [t for t in tasks if t.get("status") != STATUS_DONE]
        done = [t for t in tasks if t.get("status") == STATUS_DONE]
        key = self._sort_key
        todo.sort(key=key)
        done.sort(key=key)
        self._fill(self.tableTodo, todo, done_tab=False)
        self._fill(self.tableDone, done, done_tab=True)
        overdue = sum(1 for t in todo if self._is_overdue(t))
        self.lblCount.setText(
            f"进行中 {len(todo)} 项（超期 {overdue}）· 已完成 {len(done)} 项")

    def _sort_key(self, t):
        if self.cbSort.currentIndex() == 0:  # 优先级：高中低弱，再按due day
            return (PRIORITY_ORDER.get(t.get("priority"), 9),
                    t.get("due_day", "9999-99-99"))
        return (t.get("due_day", "9999-99-99"),
                PRIORITY_ORDER.get(t.get("priority"), 9))

    def _is_overdue(self, t):
        if not t.get("due_day"):
            return False
        try:
            return datetime.strptime(t["due_day"][:10], "%Y-%m-%d").date() < datetime.today().date()
        except ValueError:
            return False

    def _fill(self, table, tasks, done_tab):
        table.clearContents()
        table.setRowCount(len(tasks))
        for row, t in enumerate(tasks):
            overdue = (not done_tab) and self._is_overdue(t)

            pri = QTableWidgetItem(t.get("priority", ""))
            pri.setTextAlignment(Qt.AlignCenter)

            desc = QTableWidgetItem(t.get("desc", ""))
            diff = QTableWidgetItem(t.get("difficulty", ""))
            start = QTableWidgetItem(common.fmt_dt(t.get("start_time", "")))
            due_text = common.fmt_d(t.get("due_day", ""))
            if overdue:
                due_text += "  ⚠已逾期"
            due = QTableWidgetItem(due_text)

            # 染色：优先级徽章色 / 逾期红色
            pri.setData(Qt.ForegroundRole, self._color(
                _PRIORITY_COLOR.get(t.get("priority"), "#d7e3f4")))
            if overdue:
                due.setData(Qt.ForegroundRole, self._color("#ff6b6b"))
                desc.setData(Qt.ForegroundRole, self._color("#ffb0b0"))

            for col, item in enumerate((pri, desc, diff, start, due)):
                table.setItem(row, col, item)
            table.item(row, 1).setToolTip(t.get("desc", ""))
            table.item(row, 1).setData(Qt.UserRole, t["id"])  # 定位按ID，不受同名影响
            table.setRowHeight(row, 44)
        self._fill_actions(table, tasks, done_tab)

    def _fill_actions(self, table, tasks, done_tab):
        for row, t in enumerate(tasks):
            status_item = QTableWidgetItem(t.get("status", ""))
            status_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 5, status_item)

            bar = QWidget()
            h = QHBoxLayout(bar)
            h.setContentsMargins(4, 2, 4, 2)
            h.setSpacing(4)
            tid = t["id"]
            if done_tab:
                btnBack = QPushButton("还原")
                btnBack.setToolTip("改回未完成，回到清单")
                btnBack.clicked.connect(lambda _, i=tid: self.set_status(i, STATUS_TODO))
                h.addWidget(btnBack)
            else:
                btnDone = QPushButton("完成")
                btnDone.setObjectName("primary")
                btnDone.clicked.connect(lambda _, i=tid: self.set_status(i, STATUS_DONE))
                h.addWidget(btnDone)
            btnEdit = QPushButton("编辑")
            btnEdit.clicked.connect(lambda _, i=tid: self.edit_item(i))
            h.addWidget(btnEdit)
            btnDel = QPushButton("删除")
            btnDel.setObjectName("danger")
            btnDel.clicked.connect(lambda _, i=tid: self.delete_item(i))
            h.addWidget(btnDel)
            table.setCellWidget(row, 6, bar)

    @staticmethod
    def _color(hexstr):
        from PySide6.QtGui import QColor, QBrush
        return QBrush(QColor(hexstr))

    # ---------- 操作 ----------

    def add_item(self):
        dlg = TaskDialog(self)
        if dlg.exec() == TaskDialog.Accepted:
            f = dlg.fields()
            if not f["desc"]:
                QMessageBox.warning(self, "提示", "事情描述不能为空")
                return
            self.store.add_task(f["desc"], f["difficulty"], f["start_time"],
                                f["due_day"], f["priority"])

    def edit_by_table(self, table, index):
        tasks = [t for t in self.store.data["tasks"]
                 if (t.get("status") == STATUS_DONE) == (table is self.tableDone)]
        tasks.sort(key=self._sort_key)
        if 0 <= index.row() < len(tasks):
            self.edit_item(tasks[index.row()]["id"])

    def edit_item(self, task_id):
        task = self.store.find("tasks", task_id)
        if not task:
            return
        dlg = TaskDialog(self, task=task)
        if dlg.exec() == TaskDialog.Accepted:
            f = dlg.fields()
            if not f["desc"]:
                QMessageBox.warning(self, "提示", "事情描述不能为空")
                return
            self.store.update_task(task_id, **f)

    def set_status(self, task_id, status):
        self.store.set_task_status(task_id, status)

    def delete_item(self, task_id):
        task = self.store.find("tasks", task_id)
        if not task:
            return
        ret = QMessageBox.question(
            self, "删除确认", f"确定删除任务？\n\n{task.get('desc', '')}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.store.delete("tasks", task_id)

    # ---------- 全局搜索接入 ----------

    def search_records(self):
        records = []
        for t in self.store.data["tasks"]:
            records.append(SearchRecord(
                module_key=self.module_key,
                module_name=self.module_name,
                item_id=t["id"],
                title=t.get("desc", ""),
                fields={
                    "描述": t.get("desc", ""),
                    "难点": t.get("difficulty", ""),
                    "优先级": t.get("priority", ""),
                    "状态": t.get("status", ""),
                },
                time_text=f"{common.fmt_dt(t.get('start_time', ''))} → {common.fmt_d(t.get('due_day', ''))}",
            ))
        return records

    def locate(self, item_id):
        """从搜索结果跳转：切到正确页签并选中该行。"""
        task = self.store.find("tasks", item_id)
        if not task:
            return
        is_done = task.get("status") == STATUS_DONE
        self.tabs.setCurrentIndex(1 if is_done else 0)
        table = self.tableDone if is_done else self.tableTodo
        for row in range(table.rowCount()):
            it = table.item(row, 1)
            if it and it.data(Qt.UserRole) == item_id:
                table.selectRow(row)
                break
