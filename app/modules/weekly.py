# -*- coding: utf-8 -*-
"""周报视图：已完成事项按周（周一至周日）自动整理，进行中的一并归入，
按时间从上到下生成时间轴；左侧周列表像歌单，点击某周查看该周工作总结。
"""
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .. import common


def _parse(value):
    """把任务时间字段解析成 datetime；兼容日期/日期时间/乱码。"""
    v = (value or "").strip()
    if not v or "%" in v:
        return None
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(v[:16], f)
        except ValueError:
            pass
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _anchor(task):
    """时间轴锚点：已完成→完成时刻；进行中→到期时刻（无则开始时刻，再无则创建）。"""
    done = task.get("status") == "已完成"
    for key in (("completed_at",) if done else ("due_day", "start_time")):
        dt = _parse(task.get(key))
        if dt is not None:
            return dt, done
    return _parse(task.get("created_at")), done


def build_weeks(tasks):
    """把任务按周（周一为一周开始）分组。返回 [{monday, items:[(dt, task, done)]}]，
    每周内按时间倒序（最新在上）。"""
    groups = {}
    for t in tasks:
        dt, done = _anchor(t)
        if dt is None:
            continue
        monday = (dt - timedelta(days=dt.weekday())).date()
        groups.setdefault(monday, []).append((dt, t, done))
    weeks = []
    for monday, items in groups.items():
        items.sort(key=lambda x: x[0], reverse=True)
        weeks.append({
            "monday": monday,
            "sunday": monday + timedelta(days=6),
            "items": items,
        })
    weeks.sort(key=lambda wk: wk["monday"], reverse=True)
    return weeks


def week_summary_text(week) -> str:
    """生成一周的文字版总结（复制用）。"""
    done = [(dt, t) for dt, t, d in week["items"] if d]
    todo = [(dt, t) for dt, t, d in week["items"] if not d]
    lines = [
        f"工作总结（{week['monday'].strftime('%Y-%m-%d')} ~ "
        f"{week['sunday'].strftime('%m-%d')}）",
        f"完成 {len(done)} 项，进行中 {len(todo)} 项", "",
        "【已完成】",
    ]
    for dt, t in sorted(done, key=lambda x: x[0]):
        lines.append(f"  ✓ {dt.strftime('%m-%d %H:%M')}  {t.get('desc', '')}")
    lines.append("")
    lines.append("【进行中】")
    if todo:
        for dt, t in sorted(todo, key=lambda x: x[0]):
            lines.append(f"  → {dt.strftime('%m-%d %H:%M')}  {t.get('desc', '')}"
                         f"（{t.get('priority', '')}优先）")
    else:
        lines.append("  （无）")
    return "\n".join(lines)


class WeeklyModule(QWidget):
    module_key = None  # 派生视图，不参与全局搜索
    module_name = "周报"

    def __init__(self, store):
        super().__init__()
        self.store = store
        store.changed.connect(self.refresh)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        lbl = QLabel("周报 · 每周工作总结")
        lbl.setObjectName("pageHead")
        self.lblCount = QLabel("")
        self.lblCount.setObjectName("muted")
        btnCopy = QPushButton("复制本周总结")
        btnCopy.clicked.connect(self.copy_summary)
        head.addWidget(lbl)
        head.addWidget(self.lblCount)
        head.addStretch(1)
        head.addWidget(btnCopy)
        lay.addLayout(head)

        splitter = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.setMinimumWidth(280)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._on_select)
        splitter.addWidget(self.list)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.lblWeek = QLabel("选择左侧一周查看时间轴")
        self.lblWeek.setObjectName("pageHead")
        rv.addWidget(self.lblWeek)
        from PySide6.QtWidgets import QScrollArea
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.tl = QVBoxLayout(self.host)
        self.tl.setContentsMargins(0, 0, 6, 0)
        self.tl.setSpacing(6)
        self.tl.addStretch(1)
        self.scroll.setWidget(self.host)
        rv.addWidget(self.scroll, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 720])
        lay.addWidget(splitter, 1)

        self.weeks = []

    def refresh(self):
        self.weeks = build_weeks(self.store.data["tasks"])
        self.list.blockSignals(True)
        self.list.clear()
        target = min(self._selected, max(0, len(self.weeks) - 1)) \
            if self.weeks else -1
        for wk in self.weeks:
            n_done = sum(1 for _, _, d in wk["items"] if d)
            n_todo = len(wk["items"]) - n_done
            it = QListWidgetItem(
                f"🎧  {wk['monday'].strftime('%m/%d')} - {wk['sunday'].strftime('%m/%d')}"
                f"   第{wk['monday'].isocalendar()[1]}周\n"
                f"     ✓ 完成 {n_done} 项   ⏳ 进行中 {n_todo} 项")
            it.setData(Qt.UserRole, wk["monday"].toordinal())
            self.list.addItem(it)
        if self.weeks:
            self.list.setCurrentRow(target)
            self.list.blockSignals(False)
            self._render(self.weeks[target])
        else:
            self.list.blockSignals(False)
            self.lblCount.setText("暂无数据")
            self._render(None)

    _selected = 0

    def _on_select(self, row):
        if 0 <= row < len(self.weeks):
            self._selected = row
            self._render(self.weeks[row])

    def _render(self, week):
        while self.tl.count() > 1:
            it = self.tl.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        if week is None:
            self.lblWeek.setText("暂无数据")
            empty = QLabel("还没有任务记录。\n完成任务或添加任务后，这里会自动按周生成时间轴。")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignCenter)
            empty.setContentsMargins(0, 50, 0, 0)
            self.tl.insertWidget(0, empty)
            return

        n_done = sum(1 for _, _, d in week["items"] if d)
        n_todo = len(week["items"]) - n_done
        self.lblWeek.setText(
            f"{week['monday'].strftime('%Y年%m月%d日')} ~ {week['sunday'].strftime('%m月%d日')}"
            f" · 完成 {n_done} · 进行中 {n_todo}")
        self.lblCount.setText(f"共 {len(self.weeks)} 周记录")

        for dt, t, done in week["items"]:
            self.tl.insertWidget(self.tl.count() - 1, self._entry_card(dt, t, done))

    def _entry_card(self, dt, task, done):
        frame = QFrame()
        frame.setObjectName("card")
        color = "#3ddc97" if done else "#ffb64d"
        frame.setStyleSheet(f"QFrame#card{{border-left:4px solid {color};}}")
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color};font-size:16px;")
        h.addWidget(dot)

        center = QWidget()
        v = QVBoxLayout(center)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        badge = QLabel("✓ 已完成" if done else "⏳ 进行中")
        badge.setStyleSheet(f"color:{color};font-size:11px;font-weight:bold;")
        title = QLabel(f"{dt.strftime('%m-%d %H:%M')}  {task.get('desc', '')}")
        title.setWordWrap(True)
        sub_bits = []
        if task.get("priority"):
            sub_bits.append(f"优先级 {task['priority']}")
        if task.get("daily_id"):
            sub_bits.append("每日任务")
        if not done and task.get("due_day"):
            sub_bits.append(f"到期 {common.fmt_dt(task['due_day']) or common.fmt_d(task['due_day'])}")
        sub = QLabel("  ·  ".join(sub_bits))
        sub.setObjectName("cardTime")
        v.addWidget(badge)
        v.addWidget(title)
        if sub_bits:
            v.addWidget(sub)
        h.addWidget(center, 1)

        if done and task.get("difficulty"):
            diff = QLabel(f"难点：{task['difficulty']}")
            diff.setObjectName("muted")
            diff.setWordWrap(True)
            diff.setMaximumWidth(260)
            h.addWidget(diff)
        return frame

    def copy_summary(self):
        row = self.list.currentRow()
        if not (0 <= row < len(self.weeks)):
            QMessageBox.information(self, "提示", "请先在左侧选择一周")
            return
        text = week_summary_text(self.weeks[row])
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制", "本周总结已复制到剪贴板，可直接粘贴到邮件/周报。")
