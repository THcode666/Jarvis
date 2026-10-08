# -*- coding: utf-8 -*-
"""模块一「缓急」：任务清单。

- 新增/编辑/删除任务（描述/难点/开始时间/Due Day/优先级 高中低弱）
- 按 优先级 或 Due Day 排序
- 状态：未完成 / 已完成；已完成的进入"已完成事项"页签，可一键还原回清单
"""
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView,
)

from .. import common
from ..data_store import PRIORITIES, PRIORITY_ORDER, STATUS_DONE, STATUS_TODO
from ..dialogs import TaskDialog
from ..more_dialogs import DailyTaskDialog
from ..holidays import HolidayCalendar
from ..search import SearchRecord

_PRIORITY_COLOR = {"高": "#ff6b6b", "中": "#ffb64d", "低": "#29c6ff", "弱": "#7d92ad"}


def _due_dt(t):
    """解析 due_day 为 datetime；兼容旧纯日期（视为当天）与新日期时间。返回 (dt, 带时分)。"""
    v = (t.get("due_day") or "").strip()
    if not v:
        return None, False
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(v[:16], f), True
        except ValueError:
            pass
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d"), False
    except ValueError:
        return None, False


def _is_due_overdue(t, today=None, now=None):
    """纯日期按"当天结束前不算逾期"，带时分按精确时间比较。"""
    dt, has_time = _due_dt(t)
    if dt is None:
        return False
    if has_time:
        return dt < (now or datetime.now())
    return dt.date() < (today or datetime.today().date())


def collect_due(tasks, today=None):
    """把未完成任务按 逾期 / 今日 / 三日内 分组（托盘提醒与角标共用）。"""
    today = today or datetime.today().date()
    now = datetime.now()
    groups = {"逾期": [], "今日": [], "三日": []}
    for t in tasks:
        if t.get("status") == STATUS_DONE:
            continue
        dt, _ = _due_dt(t)
        if dt is None:
            continue
        if _is_due_overdue(t, today, now):
            groups["逾期"].append(t)
        elif dt.date() == today:
            groups["今日"].append(t)
        elif dt.date() <= today + timedelta(days=3):
            groups["三日"].append(t)
    return groups


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
        self.tabs.addTab(self._make_daily_tab(), "每日任务")
        lay.addWidget(self.tabs, 1)

        # 节假日日历（data/holidays.json，可编辑；供每日任务跳过节假日）
        self.calendar = HolidayCalendar(store.data_dir)
        self._daily_generated_note = ""

    def _make_daily_tab(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(6)
        head = QHBoxLayout()
        self.lblDailyStatus = QLabel("")
        self.lblDailyStatus.setObjectName("muted")
        btnAdd = QPushButton("＋ 新增每日任务")
        btnAdd.setObjectName("primary")
        btnAdd.clicked.connect(self.add_daily)
        head.addWidget(self.lblDailyStatus)
        head.addStretch(1)
        head.addWidget(btnAdd)
        v.addLayout(head)

        self.tableDaily = QTableWidget(0, 6)
        self.tableDaily.setHorizontalHeaderLabels(
            ["任务内容", "难点", "优先级", "到期时刻", "状态", "操作"])
        self.tableDaily.verticalHeader().setVisible(False)
        self.tableDaily.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableDaily.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h = self.tableDaily.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        v.addWidget(self.tableDaily, 1)
        return box

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
        g = collect_due(todo)
        self.lblCount.setText(
            f"进行中 {len(todo)} 项（逾期 {len(g['逾期'])} · 今日到期 {len(g['今日'])}）"
            f"· 已完成 {len(done)} 项")
        self._fill_daily()

    def _sort_key(self, t):
        if self.cbSort.currentIndex() == 0:  # 优先级：高中低弱，再按due day
            return (PRIORITY_ORDER.get(t.get("priority"), 9),
                    t.get("due_day", "9999-99-99"))
        return (t.get("due_day", "9999-99-99"),
                PRIORITY_ORDER.get(t.get("priority"), 9))

    def _is_overdue(self, t):
        return _is_due_overdue(t)

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
            _, has_time = _due_dt(t)
            due_text = common.fmt_dt(t.get("due_day", "")) if has_time \
                else common.fmt_d(t.get("due_day", ""))
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

    # ---------- 每日任务 ----------

    def _fill_daily(self):
        dailies = self.store.data["dailies"]
        self.tableDaily.clearContents()
        self.tableDaily.setRowCount(len(dailies))
        today = datetime.today()
        work = self.calendar.is_workday(today)
        done_ids = {t.get("daily_id") for t in self.store.data["tasks"]
                    if t.get("daily_date") == today.strftime("%Y-%m-%d")}
        if self._daily_generated_note:
            note = self._daily_generated_note
        elif not work:
            note = f"今天（{today.strftime('%m-%d')}）是休息日（周末/节假日），每日任务自动跳过"
        else:
            note = f"今天（{today.strftime('%m-%d')}）是工作日，每日任务已自动生成"
        self.lblDailyStatus.setText(f"{note} · 模板 {len(dailies)} 条")

        for row, d in enumerate(dailies):
            self.tableDaily.setItem(row, 0, QTableWidgetItem(d.get("desc", "")))
            self.tableDaily.setItem(row, 1, QTableWidgetItem(d.get("difficulty", "")))
            pri = QTableWidgetItem(d.get("priority", ""))
            pri.setTextAlignment(Qt.AlignCenter)
            pri.setData(Qt.ForegroundRole, self._color(
                _PRIORITY_COLOR.get(d.get("priority"), "#d7e3f4")))
            self.tableDaily.setItem(row, 2, pri)
            self.tableDaily.setItem(row, 3, QTableWidgetItem(d.get("due_time", "")))
            state = QTableWidgetItem("已启用" if d.get("enabled") else "已停用")
            state.setTextAlignment(Qt.AlignCenter)
            self.tableDaily.setItem(row, 4, state)

            bar = QWidget()
            hb = QHBoxLayout(bar)
            hb.setContentsMargins(4, 2, 4, 2)
            hb.setSpacing(4)
            did = d["id"]
            btnToggle = QPushButton("停用" if d.get("enabled") else "启用")
            btnToggle.clicked.connect(lambda _, i=did: self.toggle_daily(i))
            hb.addWidget(btnToggle)
            btnEdit = QPushButton("编辑")
            btnEdit.clicked.connect(lambda _, i=did: self.edit_daily(i))
            hb.addWidget(btnEdit)
            btnDel = QPushButton("删除")
            btnDel.setObjectName("danger")
            btnDel.clicked.connect(lambda _, i=did: self.delete_daily(i))
            hb.addWidget(btnDel)
            self.tableDaily.setCellWidget(row, 5, bar)
            self.tableDaily.setRowHeight(row, 40)

    def add_daily(self):
        dlg = DailyTaskDialog(self)
        if dlg.exec() == DailyTaskDialog.Accepted:
            f = dlg.fields()
            if not f["desc"]:
                QMessageBox.warning(self, "提示", "任务内容不能为空")
                return
            self.store.add_daily(f["desc"], f["difficulty"], f["priority"], f["due_time"])

    def edit_daily(self, daily_id):
        d = self.store.find("dailies", daily_id)
        if not d:
            return
        dlg = DailyTaskDialog(self, daily=d)
        if dlg.exec() == DailyTaskDialog.Accepted:
            f = dlg.fields()
            if not f["desc"]:
                QMessageBox.warning(self, "提示", "任务内容不能为空")
                return
            self.store.update_daily(daily_id, **f)

    def toggle_daily(self, daily_id):
        d = self.store.find("dailies", daily_id)
        if d:
            self.store.update_daily(daily_id, enabled=not d.get("enabled", True))

    def delete_daily(self, daily_id):
        d = self.store.find("dailies", daily_id)
        if d and self.confirm_delete(f"{d.get('desc', '')}\n\n（记录进入回收站，保留3天）"):
            self.store.delete("dailies", daily_id)

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
                time_text=f"{common.fmt_dt(t.get('start_time', ''))} → "
                          f"{common.fmt_dt(t.get('due_day', '')) or common.fmt_d(t.get('due_day', ''))}",
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
