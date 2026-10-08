# -*- coding: utf-8 -*-
"""数据层：全部业务数据的增删改查、持久化、附件管理、一键导入/导出。

数据结构（data/jarvis_data.json）：
{
  "tasks":     [ {id, desc, difficulty, start_time, due_day, priority, status,
                    created_at, completed_at} ],
  "memos":     [ {id, content, time, created_at} ],
  "questions": [ {id, question, time, solution, created_at} ],
  "sops":      [ {id, title, content, attachments: [{name, stored, kind, text}],
                    created_at} ]
}
附件实体文件保存在 data/attachments/ 下，记录里只存文件名。

新增一种记录类型时：加一个 collection + 对应 add/update/delete 方法即可。
"""
import json
import os
import shutil
import zipfile
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from . import common

PRIORITIES = ["高", "中", "低", "弱"]
PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2, "弱": 3}

STATUS_TODO = "未完成"
STATUS_DONE = "已完成"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
PPT_EXTS = {".pptx", ".ppt"}

_DATA_KEYS = ["tasks", "memos", "questions", "sops"]


class DataStore(QObject):
    """单一数据源。任何写操作后发出 changed 信号，界面层据此刷新。"""

    changed = Signal()

    def __init__(self, data_dir: str):
        super().__init__()
        self.data_dir = data_dir
        self.attach_dir = os.path.join(data_dir, "attachments")
        self.json_path = os.path.join(data_dir, "jarvis_data.json")
        os.makedirs(self.attach_dir, exist_ok=True)
        self.data = {k: [] for k in _DATA_KEYS}
        self.load()
        self.backup_json()

    # ---------- 持久化 ----------

    def load(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for k in _DATA_KEYS:
                    self.data[k] = loaded.get(k, []) or []
                if self._repair_garbage_times():
                    self.save()  # 修复旧版时间格式bug产生的乱码，立即落盘
            except (json.JSONDecodeError, OSError):
                # 数据文件损坏时不直接崩溃，把损坏文件改名保留现场
                try:
                    shutil.copy(self.json_path, self.json_path + ".bad")
                except OSError:
                    pass

    def _repair_garbage_times(self) -> int:
        """v1.2.0及之前对话框用错时间格式串，存出过含%的乱码值。

        无法还原原始时间，但新建时这些字段默认值就是"当前时刻"，与
        created_at 几乎相同，因此用 created_at 修复；正常数据不含%不会被动。
        返回修复条数。
        """
        def bad(v):
            return bool(v) and "%" in v

        n = 0
        for t in self.data["tasks"]:
            if bad(t.get("start_time")):
                t["start_time"] = common.fmt_dt(t.get("created_at")) or common.now_str()
                n += 1
        for m in self.data["memos"]:
            if bad(m.get("time")):
                m["time"] = common.fmt_dt(m.get("created_at")) or common.now_str()
                n += 1
        for q in self.data["questions"]:
            if bad(q.get("time")):
                q["time"] = common.fmt_dt(q.get("created_at")) or common.now_str()
                n += 1
        return n

    def save(self):
        tmp = self.json_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.json_path)

    def _emit(self):
        self.save()
        self.changed.emit()

    def backup_json(self, keep: int = 5):
        """把当前数据文件快照到 data/backups/，滚动保留最近 keep 份。

        启动时和导入覆盖前各做一次，误删/误导入后可以从这里捞回数据。
        """
        if not os.path.exists(self.json_path):
            return
        bdir = os.path.join(self.data_dir, "backups")
        try:
            os.makedirs(bdir, exist_ok=True)
            name = f"jarvis_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.json_path, os.path.join(bdir, name))
            olds = sorted(f for f in os.listdir(bdir)
                          if f.startswith("jarvis_data_") and f.endswith(".json"))
            for f in olds[:-keep]:
                try:
                    os.remove(os.path.join(bdir, f))
                except OSError:
                    pass
        except OSError:
            pass

    # ---------- 缓急：任务 ----------

    def add_task(self, desc, difficulty, start_time, due_day, priority) -> dict:
        task = {
            "id": common.new_id(),
            "desc": desc.strip(),
            "difficulty": difficulty.strip(),
            "start_time": start_time,
            "due_day": due_day,
            "priority": priority if priority in PRIORITIES else "中",
            "status": STATUS_TODO,
            "created_at": common.now_str(),
            "completed_at": "",
        }
        self.data["tasks"].append(task)
        self._emit()
        return task

    def update_task(self, task_id, **fields):
        task = self.find("tasks", task_id)
        if not task:
            return
        for key in ("desc", "difficulty", "start_time", "due_day", "priority"):
            if key in fields:
                task[key] = fields[key]
        self._emit()

    def set_task_status(self, task_id, status: str):
        task = self.find("tasks", task_id)
        if not task:
            return
        task["status"] = status
        task["completed_at"] = common.now_str() if status == STATUS_DONE else ""
        self._emit()

    # ---------- 帮记：备忘 ----------

    def add_memo(self, content, time_str) -> dict:
        memo = {
            "id": common.new_id(),
            "content": content.strip(),
            "time": time_str,
            "created_at": common.now_str(),
        }
        self.data["memos"].append(memo)
        self._emit()
        return memo

    def update_memo(self, memo_id, **fields):
        memo = self.find("memos", memo_id)
        if not memo:
            return
        for key in ("content", "time"):
            if key in fields:
                memo[key] = fields[key]
        self._emit()

    # ---------- 解惑：问题 ----------

    def add_question(self, question, time_str, solution) -> dict:
        item = {
            "id": common.new_id(),
            "question": question.strip(),
            "time": time_str,
            "solution": solution.strip(),
            "created_at": common.now_str(),
        }
        self.data["questions"].append(item)
        self._emit()
        return item

    def update_question(self, q_id, **fields):
        item = self.find("questions", q_id)
        if not item:
            return
        for key in ("question", "time", "solution"):
            if key in fields:
                item[key] = fields[key]
        self._emit()

    # ---------- 存知：SOP ----------

    def add_sop(self, title, content, attachments=None) -> dict:
        sop = {
            "id": common.new_id(),
            "title": title.strip(),
            "content": content,
            "attachments": attachments or [],
            "created_at": common.now_str(),
        }
        self.data["sops"].append(sop)
        self._emit()
        return sop

    def update_sop(self, sop_id, **fields):
        sop = self.find("sops", sop_id)
        if not sop:
            return
        for key in ("title", "content", "attachments"):
            if key in fields:
                sop[key] = fields[key]
        self._emit()

    # ---------- 通用 ----------

    def find(self, collection: str, item_id: str):
        for item in self.data[collection]:
            if item.get("id") == item_id:
                return item
        return None

    def delete(self, collection: str, item_id: str) -> bool:
        item = self.find(collection, item_id)
        before = len(self.data[collection])
        self.data[collection] = [x for x in self.data[collection] if x.get("id") != item_id]
        if len(self.data[collection]) != before:
            if collection == "sops" and item:
                for att in item.get("attachments", []):
                    self.remove_attachment_file(att.get("stored", ""))
            self._emit()
            return True
        return False

    # ---------- 附件管理（存知模块） ----------

    def attachment_path(self, stored_name: str) -> str:
        return os.path.join(self.attach_dir, stored_name)

    def add_attachment(self, sop_id: str, src_path: str) -> dict:
        """把外部文件复制进附件目录，返回附件元数据。

        图片/PPT以外的类型也可以存，但预览和搜索只针对图片与PPT。
        .pptx 会用标准库解出每页文字，供详情预览和全局搜索。
        """
        ext = os.path.splitext(src_path)[1].lower()
        stored = f"{sop_id}_{common.new_id()}{ext}"
        shutil.copy(src_path, self.attachment_path(stored))

        if ext in IMAGE_EXTS:
            kind = "image"
        elif ext in PPT_EXTS:
            kind = "ppt"
        else:
            kind = "other"

        text = ""
        if ext == ".pptx":
            text = extract_pptx_text(self.attachment_path(stored))
        return {"name": os.path.basename(src_path), "stored": stored, "kind": kind, "text": text}

    def remove_attachment_file(self, stored_name: str):
        try:
            os.remove(self.attachment_path(stored_name))
        except OSError:
            pass

    # ---------- 一键导入 / 导出 ----------

    def export_zip(self, zip_path: str) -> str:
        """把全部数据 + 附件打包成一个 zip。"""
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("data.json", json.dumps(self.data, ensure_ascii=False, indent=2))
            for name in sorted(os.listdir(self.attach_dir)):
                fp = os.path.join(self.attach_dir, name)
                if os.path.isfile(fp):
                    z.write(fp, f"attachments/{name}")
        return zip_path

    def import_zip(self, zip_path: str):
        """从备份zip恢复全部数据（覆盖当前所有内容）。"""
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            if "data.json" not in names:
                raise ValueError("这不是本软件的备份文件（缺少 data.json）")
            loaded = json.loads(z.read("data.json").decode("utf-8"))
            for k in _DATA_KEYS:
                if k not in loaded:
                    raise ValueError("备份文件数据不完整")

            # 覆盖前先快照当前数据，误导入可回退
            self.backup_json()

            # 清空当前附件
            for name in os.listdir(self.attach_dir):
                fp = os.path.join(self.attach_dir, name)
                try:
                    os.remove(fp)
                except OSError:
                    pass
            for name in names:
                if name.startswith("attachments/") and not name.endswith("/"):
                    target = os.path.join(self.attach_dir, os.path.basename(name))
                    with z.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        for k in _DATA_KEYS:
            self.data[k] = loaded.get(k, []) or []
        self._emit()


def extract_pptx_text(path: str) -> str:
    """用标准库解析 .pptx（本质是zip+xml），抽取每页文字。

    老 .ppt 为二进制格式，无法用标准库解析，返回空串（仍可双击外部打开）。
    """
    import re
    import html
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            slides = sorted(
                (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                key=lambda n: int(re.search(r"(\d+)", n).group(1)),
            )
            pages = []
            for i, name in enumerate(slides, 1):
                xml = z.read(name).decode("utf-8", "ignore")
                runs = re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)
                text = " ".join(html.unescape(r).strip() for r in runs if r.strip())
                if text:
                    pages.append(f"[第{i}页] {text}")
            return "\n".join(pages)
    except Exception:
        return ""
