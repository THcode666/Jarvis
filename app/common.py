# -*- coding: utf-8 -*-
"""通用工具：路径、时间、ID、资源定位。

新增模块时通常只需要用到 new_id() / now_str()。
"""
import os
import sys
import uuid
from datetime import datetime

APP_NAME = "贾维斯 Jarvis"
APP_VERSION = "v1.1.0"

DT_FORMAT = "%Y-%m-%d %H:%M"
D_FORMAT = "%Y-%m-%d"


def new_id() -> str:
    """生成短ID，作为每条记录的唯一键。"""
    return uuid.uuid4().hex[:12]


def now_str() -> str:
    return datetime.now().strftime(DT_FORMAT)


def today_str() -> str:
    return datetime.now().strftime(D_FORMAT)


def fmt_dt(value: str) -> str:
    """把 ISO/带秒的时间串统一显示成 yyyy-MM-dd HH:mm。"""
    if not value:
        return ""
    for f in (DT_FORMAT, "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, f).strftime(DT_FORMAT)
        except ValueError:
            continue
    return value.replace("T", " ")[:16]


def fmt_d(value: str) -> str:
    if not value:
        return ""
    return value[:10]


def project_root() -> str:
    """源码运行时的项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def res_path(rel: str) -> str:
    """定位随exe打包的资源文件（图标等）。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(project_root(), rel)


def get_data_dir() -> str:
    """数据目录：优先放在exe（或源码根目录）旁边的 data 文件夹，便于备份/迁移；
    若该位置不可写（如exe在只读目录），回退到 %APPDATA%/Jarvis/data。"""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(project_root())
    candidates.append(os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "Jarvis"))

    for base in candidates:
        data_dir = os.path.join(base, "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            probe = os.path.join(data_dir, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return data_dir
        except OSError:
            continue
    raise RuntimeError("无法创建数据目录")
