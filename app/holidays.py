# -*- coding: utf-8 -*-
"""节假日日历：判断某天是否为工作日（供每日任务自动跳过节假日用）。

规则：周一至周五为工作日；命中 holidays 放假日不算；周末但命中 workdays（调休补班）算。
日历数据存 data/holidays.json，软件首次运行自动生成内置的官方2026年安排；
之后国务院发布新年度安排时，用户可直接用记事本编辑该文件（说明写在文件里）。
"""
import json
import os
from datetime import datetime

# 国务院办公厅2026年部分节假日安排（2025-11-04发布）
DEFAULT_HOLIDAYS = [
    # 元旦 1/1(四)-1/3(六)
    "2026-01-01", "2026-01-02", "2026-01-03",
    # 春节 2/15(日)-2/23(一)，除夕2/16纳入法定假
    "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",
    # 清明 4/4(六)-4/6(一)
    "2026-04-04", "2026-04-05", "2026-04-06",
    # 劳动节 5/1(五)-5/5(二)
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    # 端午 6/19(五)-6/21(日)
    "2026-06-19", "2026-06-20", "2026-06-21",
    # 中秋 9/25(五)-9/27(日)
    "2026-09-25", "2026-09-26", "2026-09-27",
    # 国庆 10/1(四)-10/7(三)
    "2026-10-01", "2026-10-02", "2026-10-03",
    "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",
]
# 调休补班日（周末但上班）
DEFAULT_WORKDAYS = [
    "2026-02-14", "2026-02-28",   # 春节
    "2026-04-26", "2026-05-09",   # 劳动节
    "2026-10-10",                 # 国庆
]

_HEADER = {
    "_说明": "本文件是每日任务的节假日日历。holidays=放假日期, workdays=周末调休补班日期。"
           "新年度安排公布后（通常每年11-12月），按同样格式追加即可，改完重启软件生效。",
    "_来源": "国务院办公厅2026年部分节假日安排（2025-11-04发布）",
}


class HolidayCalendar:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "holidays.json")
        self.holidays = set(DEFAULT_HOLIDAYS)
        self.workdays = set(DEFAULT_WORKDAYS)
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump({**_HEADER,
                               "holidays": sorted(self.holidays),
                               "workdays": sorted(self.workdays)},
                              f, ensure_ascii=False, indent=1)
            except OSError:
                pass
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("holidays"), list):
                self.holidays = set(data["holidays"]) | self.holidays
            if isinstance(data.get("workdays"), list):
                self.workdays = set(data["workdays"]) | self.workdays
        except (OSError, ValueError):
            pass  # 文件坏了就用内置日历

    def is_workday(self, date) -> bool:
        """date: datetime/date。周一至周五且不放假，或周末调休补班。"""
        key = date.strftime("%Y-%m-%d") if isinstance(date, datetime) \
            else datetime(date.year, date.month, date.day).strftime("%Y-%m-%d")
        if key in self.workdays:
            return True
        if key in self.holidays:
            return False
        return date.weekday() < 5
