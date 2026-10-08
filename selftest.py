# -*- coding: utf-8 -*-
"""贾维斯一键自测。

用法：
    python selftest.py            # 跑全部测试（数据层+GUI离屏），并输出界面截图到 assets/shots/
    python selftest.py --nodata   # 只跑数据层，不跑GUI

测什么：
 1) 数据层：四个模块的增删改查、任务状态流转（完成→归档→还原）、持久化
 2) 搜索：整句/多关键词/跨字段关联/部分命中/无命中/标题加权
 3) 附件：图片+PPT添加（.pptx用标准库现场造一个真文件验证文字抽取）
 4) 一键导出→清空→导入 往返一致性
 5) GUI：离屏构建主窗口，遍历四个页面+搜索页+对话框，刷新并截图（人工检查用）
"""
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'通过' if cond else '失败'}] {name}" + (f"  <{detail}>" if detail and not cond else ""))


# ---------------------------------------------------------------- 数据层

def make_sample_pptx(path):
    """用标准库现场造一个最小可解析的 .pptx（两页，含文字）。"""
    slide1 = """<?xml version="1.0"?><p:sld xmlns:p="urn:x" xmlns:a="urn:y">
    <a:p><a:r><a:t>测试流程</a:t></a:r></a:p>
    <a:p><a:r><a:t>第一步 wafer start</a:t></a:r></a:p></p:sld>"""
    slide2 = """<?xml version="1.0"?><p:sld xmlns:p="urn:x" xmlns:a="urn:y">
    <a:p><a:r><a:t>针卡clean方法</a:t></a:r></a:p></p:sld>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<?xml version='1.0'?><Types/>")
        z.writestr("ppt/slides/slide1.xml", slide1)
        z.writestr("ppt/slides/slide2.xml", slide2)


def test_data_layer(tmp):
    from app.data_store import DataStore, extract_pptx_text

    store = DataStore(os.path.join(tmp, "data"))
    check("初始数据为空", all(len(v) == 0 for v in store.data.values()))

    # 任务 CRUD
    t1 = store.add_task("换针卡", "卡点定位", "2026-10-01 08:00", "2026-10-05", "高")
    t2 = store.add_task("写周报", "", "2026-10-02 09:00", "2026-10-03", "弱")
    t3 = store.add_task("校准prober", "温度补偿", "2026-10-01 10:00", "2026-09-28", "中")  # 逾期
    check("新增任务×3", len(store.data["tasks"]) == 3)
    store.update_task(t1["id"], desc="换针卡（升级）", priority="高")
    check("编辑任务", store.find("tasks", t1["id"])["desc"] == "换针卡（升级）")

    # 状态流转：完成→归档→还原
    store.set_task_status(t2["id"], "已完成")
    check("完成后归档字段", store.find("tasks", t2["id"])["completed_at"] != "")
    store.set_task_status(t2["id"], "未完成")
    check("还原回未完成", store.find("tasks", t2["id"])["status"] == "未完成"
          and store.find("tasks", t2["id"])["completed_at"] == "")

    # 排序键
    from app.data_store import PRIORITY_ORDER
    check("优先级顺序表", list(PRIORITY_ORDER) == ["高", "中", "低", "弱"])

    # 备忘 / 问题
    m1 = store.add_memo("机台PM后要重新load recipe", "2026-10-01 12:00")
    store.update_memo(m1["id"], content="机台PM后要重新load recipe（含mapping）")
    q1 = store.add_question("lot结批报错E102", "2026-10-01 13:00", "")
    store.update_question(q1["id"], solution="重插fiber后重试")
    check("备忘/问题编辑", store.find("memos", m1["id"])["content"].endswith("（含mapping）")
          and store.find("questions", q1["id"])["solution"] == "重插fiber后重试")

    # SOP + 附件（真图片 + 真pptx）
    img_path = os.path.join(tmp, "img.png")
    make_test_image(img_path)
    sop1 = store.add_sop("针卡清洗SOP", "1.取下针卡\n2.酒精超声")
    att_img = store.add_attachment(sop1["id"], img_path)
    pptx_path = os.path.join(tmp, "test.pptx")
    make_sample_pptx(pptx_path)
    att_ppt = store.add_attachment(sop1["id"], pptx_path)
    store.update_sop(sop1["id"], attachments=[att_img, att_ppt])
    check("附件文件已复制", os.path.exists(store.attachment_path(att_img["stored"]))
          and os.path.exists(store.attachment_path(att_ppt["stored"])))
    check("pptx文字抽取", "测试流程" in att_ppt["text"] and "第2页" in att_ppt["text"])

    # 持久化
    store.save()
    store2 = DataStore(os.path.join(tmp, "data"))
    check("重新加载持久化一致",
          len(store2.data["tasks"]) == 3 and len(store2.data["sops"]) == 1
          and store2.find("sops", sop1["id"]) is not None)

    bdir = os.path.join(tmp, "data", "backups")
    check("启动自动备份JSON", os.path.isdir(bdir) and any(
        f.startswith("jarvis_data_") and f.endswith(".json") for f in os.listdir(bdir)))

    # ---- 时间格式回归（v1.2.1）----
    from app.modules.tasks import _is_due_overdue, collect_due
    today = datetime.today().date()
    check("旧纯日期今天不算逾期",
          not _is_due_overdue({"status": "未完成", "due_day": today.strftime("%Y-%m-%d")}))
    check("旧纯日期昨天算逾期",
          _is_due_overdue({"status": "未完成",
                           "due_day": (today - timedelta(days=1)).strftime("%Y-%m-%d")}))
    past_hm = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    check("带时分已过算逾期",
          _is_due_overdue({"status": "未完成", "due_day": past_hm}))
    g = collect_due([{"status": "未完成", "due_day": past_hm}])
    check("今日但时分已过分入逾期", bool(g["逾期"]) and not g["今日"])
    g2 = collect_due([{"status": "未完成",
                       "due_day": (today + timedelta(days=3)).strftime("%Y-%m-%d 12:00")}])
    check("三日内分组", bool(g2["三日"]) and not g2["逾期"] and not g2["今日"])

    # 乱码时间自动修复（旧版bug产生的含%值 → 用创建时间修复）
    store3 = DataStore(os.path.join(tmp, "data"))
    store3.data["tasks"].append({
        "id": "badfix1", "desc": "乱码样例", "difficulty": "",
        "start_time": "%Y-%28-%8 %12:%1", "due_day": "2026-10-05",
        "priority": "低", "status": "未完成",
        "created_at": "2026-10-05 09:30", "completed_at": ""})
    store3.save()
    store4 = DataStore(os.path.join(tmp, "data"))
    fixed = store4.find("tasks", "badfix1")
    check("乱码时间自动修复",
          fixed is not None and "%" not in fixed["start_time"]
          and fixed["start_time"] == "2026-10-05 09:30")
    store4.delete("tasks", "badfix1")

    # 删除（SOP附件文件保留到回收站彻底清除时才删）
    did = sop1["id"]
    stored_name = att_ppt["stored"]
    store2.delete("sops", did)
    check("删除SOP进回收站(附件保留)",
          not store2.find("sops", did)
          and os.path.exists(store2.attachment_path(stored_name)))
    store2.restore(did)
    check("回收站恢复", store2.find("sops", did) is not None
          and len(store2.data["trash"]) == 0)
    store2.delete("sops", did)
    n_purged = store2.purge_trash(all_items=True)
    check("彻底清除时删除附件",
          n_purged == 1 and not os.path.exists(store2.attachment_path(stored_name)))
    return store


def test_new_features(store, tmp):
    """v1.3.0：节假日/每日任务/回收站/周报/SVG图表/单页PPT。"""
    from app.data_store import DataStore

    print("== 1b. v1.3.0 新功能 ==")

    # ---- 节假日日历 ----
    from datetime import date
    from app.holidays import HolidayCalendar
    cal = HolidayCalendar(os.path.join(tmp, "cal_data"))
    check("日历文件自动生成", os.path.exists(os.path.join(tmp, "cal_data", "holidays.json")))
    check("工作日判断", cal.is_workday(date(2026, 3, 2)))          # 周一
    check("周六非工作日", not cal.is_workday(date(2026, 3, 7)))
    check("节假日跳过(国庆)", not cal.is_workday(date(2026, 10, 1)))
    check("调休补班算工作日", cal.is_workday(date(2026, 10, 10)))

    # ---- 每日任务 ----
    fd = DataStore(os.path.join(tmp, "daily_data"))

    class FakeCal:
        def __init__(self, work):
            self.work = work

        def is_workday(self, d):
            return self.work

    fd.add_daily("机台点检", "看参数", "高", "17:00")
    n = fd.ensure_daily_instances(FakeCal(True), today=datetime(2026, 10, 6, 9, 0))
    check("工作日生成每日任务", n == 1 and len(fd.data["tasks"]) == 1
          and fd.data["tasks"][0]["due_day"] == "2026-10-06 17:00")
    n2 = fd.ensure_daily_instances(FakeCal(True), today=datetime(2026, 10, 6, 15, 0))
    check("同日不重复生成", n2 == 0)
    n3 = fd.ensure_daily_instances(FakeCal(False), today=datetime(2026, 10, 7, 9, 0))
    check("休息日自动跳过", n3 == 0 and len(fd.data["tasks"]) == 1)

    # ---- 回收站 ----
    ft = DataStore(os.path.join(tmp, "trash_data"))
    sop = ft.add_sop("回收站SOP", "内容")
    att = ft.add_attachment(sop["id"], os.path.join(tmp, "img.png"))
    ft.update_sop(sop["id"], attachments=[att])
    ft.delete("sops", sop["id"])
    check("删除进回收站", len(ft.data["trash"]) == 1 and not ft.data["sops"])
    check("保留期内附件文件还在", os.path.exists(ft.attachment_path(att["stored"])))
    tid = ft.data["trash"][0]["id"]
    check("剩余时间文本", "剩余" in ft.trash_age_text(ft.data["trash"][0]["deleted_at"]))
    ft.restore(tid)
    check("恢复到原模块", ft.find("sops", sop["id"]) is not None
          and len(ft.data["trash"]) == 0)
    ft.delete("sops", sop["id"])
    n = ft.purge_trash(keep_days=0)
    check("过期/手动彻底清除删附件",
          n == 1 and not os.path.exists(ft.attachment_path(att["stored"])))

    # ---- 周报分组 ----
    from app.modules.weekly import build_weeks, week_summary_text
    wk_tasks = [
        {"id": "1", "desc": "完成任务A", "status": "已完成", "difficulty": "",
         "completed_at": "2026-10-06 15:00", "start_time": "2026-10-01 08:00",
         "due_day": "2026-10-05", "created_at": "2026-10-01 08:00"},
        {"id": "2", "desc": "进行中B", "status": "未完成", "difficulty": "",
         "start_time": "2026-10-07 08:00", "due_day": "2026-10-08 17:00",
         "created_at": "2026-10-06 08:00"},
    ]
    weeks = build_weeks(wk_tasks)
    check("按周分组(周一为一周开始)", len(weeks) == 1
          and weeks[0]["monday"].weekday() == 0)
    check("周内时间轴倒序", weeks[0]["items"][0][2] is False)  # 进行中B时间更晚排在前
    text = week_summary_text(weeks[0])
    check("周总结文本", "已完成" in text and "完成任务A" in text and "进行中B" in text)

    # ---- SVG 图表 ----
    from app.svg_charts import timeline_svg, fishbone_svg, wrap_html
    svg = timeline_svg([{"time": "10-08 08:00", "event": "结批报错E102"},
                        {"time": "10-08 09:00", "event": "重插fiber恢复"}], "时间线")
    check("时间线SVG生成", "<svg" in svg and "结批报错E102" in svg)
    html = wrap_html(fishbone_svg({"人": ["疲劳"], "机": ["接口氧化"]}, "异常X"), "鱼骨")
    check("鱼骨HTML五要素", all(c in html for c in ["人", "机", "料", "法", "环"])
          and "异常X" in html and "<svg" in html)

    # ---- 单页PPT ----
    from app.ppt_report import generate_ppt
    import zipfile as _zf
    out_pptx = os.path.join(tmp, "report.pptx")
    make_test_image(os.path.join(tmp, "ppt_img.png"))
    anomaly = {"title": "lot结批报错E102", "background": "结批时报错设备停机",
               "impact": "交付延迟2小时", "lesson": "去年12月发生过类似故障",
               "actions": "重启重插fiber", "root_cause": "fiber接口氧化",
               "prevention": "点检表增加清洁项"}
    generate_ppt(anomaly, [os.path.join(tmp, "ppt_img.png")], out_pptx)
    with _zf.ZipFile(out_pptx) as z:
        names = z.namelist()
        slides = [n for n in names
                  if n.startswith("ppt/slides/slide") and n.endswith(".xml")
                  and "rels" not in n]
        xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
    check("PPT只有一页", len(slides) == 1)
    check("PPT含标题与六要素", "lot结批报错E102" in xml
          and "What's the impact" in xml and "Root cause" in xml
          and "Lesson learned" in xml)
    check("PPT嵌入图片", any(n.startswith("ppt/media/") for n in names))

    # 解异数据方法
    an = store.add_anomaly("测试异常", {"background": "b",
                                        "timeline": [{"time": "t", "event": "e"}]})
    store.update_anomaly(an["id"], root_cause="rc")
    check("解异增改", store.find("anomalies", an["id"])["root_cause"] == "rc")
    store.delete("anomalies", an["id"])
    store.purge_trash(all_items=True)


def make_test_image(path):
    from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
    from PySide6.QtCore import Qt
    pm = QPixmap(320, 200)
    pm.fill(QColor("#123456"))
    p = QPainter(pm)
    p.setPen(QColor("white"))
    p.setFont(QFont("Microsoft YaHei", 14))
    p.drawText(pm.rect(), Qt.AlignCenter, "测试图片\n清洗步骤图")
    p.end()
    pm.save(path)


# ---------------------------------------------------------------- 搜索

def test_search(store):
    from app.search import search, SearchRecord

    records = []
    for page_records in (store,):
        pass
    recs = []
    from app.modules.tasks import TaskModule  # 仅用其 search_records 的纯数据逻辑不便离屏，这里直接构造
    recs.append(SearchRecord("tasks", "缓急", "1", "换针卡（升级）",
                             {"描述": "换针卡（升级）", "难点": "卡点定位", "优先级": "高"}, ""))
    recs.append(SearchRecord("memos", "帮记", "2", "机台PM后要重新load recipe（含mapping）",
                             {"内容": "机台PM后要重新load recipe（含mapping）"}, ""))
    recs.append(SearchRecord("questions", "解惑", "3", "lot结批报错E102",
                             {"问题": "lot结批报错E102", "解决方案": "重插fiber后重试"}, ""))
    recs.append(SearchRecord("sops", "存知", "4", "针卡清洗SOP",
                             {"标题": "针卡清洗SOP", "正文": "1.取下针卡\n2.酒精超声",
                              "PPT文字": "[第1页] 测试流程 [第2页] 针卡clean方法"}, ""))

    r1 = search(recs, "针卡")
    check("整句模糊命中（跨模块关联：任务+SOP）",
          {x.record.item_id for x in r1} == {"1", "4"} and r1[0].record.item_id == "4")

    r2 = search(recs, "报错 fiber")
    check("多关键词跨字段关联", len(r2) == 1 and r2[0].record.item_id == "3")

    r3 = search(recs, "流程")
    check("搜到PPT内文字", len(r3) == 1 and r3[0].record.item_id == "4")

    r4 = search(recs, "清洗SOP")
    check("SOP标题命中加权第一", r4 and r4[0].record.item_id == "4")

    r5 = search(recs, "mapping")
    check("部分词命中（关联宽松）", len(r5) == 1 and "mapping" in r5[0].snippet_html)

    r6 = search(recs, "不存在的词xyz")
    check("无命中返回空", r6 == [])

    r7 = search(recs, "RECIPE")  # 大小写
    check("忽略大小写", len(r7) == 1)

    r8 = search(recs, "hzk")  # 换针卡 → huan zhen ka
    check("拼音首字母命中", bool(r8) and r8[0].record.item_id == "1")
    r9 = search(recs, "zhenka")  # 全拼
    check("拼音全拼命中", any(x.record.item_id == "1" for x in r9))
    check("拼音匹配结果有标记", bool(r8) and r8[0].via_pinyin)

    check("高亮标签存在", "<font" in search(recs, "针卡")[0].snippet_html)


# ---------------------------------------------------------------- 导入导出

def test_export_import(store, tmp):
    from app.data_store import DataStore

    zip_path = os.path.join(tmp, "backup.zip")
    store.export_zip(zip_path)
    check("导出zip生成", os.path.exists(zip_path))

    # 新store导入
    target_dir = os.path.join(tmp, "restored")
    store_b = DataStore(target_dir)
    store_b.add_task("旧数据会被覆盖", "", "2026-01-01 00:00", "2026-01-02", "低")
    bdir_b = os.path.join(target_dir, "backups")
    n_snap0 = len(os.listdir(bdir_b)) if os.path.isdir(bdir_b) else 0
    store_b.import_zip(zip_path)
    n_snap1 = len(os.listdir(bdir_b)) if os.path.isdir(bdir_b) else 0
    same = (len(store_b.data["tasks"]) == 3
            and len(store_b.data["memos"]) == 1
            and len(store_b.data["questions"]) == 1
            and len(store_b.data["sops"]) == 1)
    check("导入后与导出前一致", same)
    check("导入前自动快照", n_snap1 == n_snap0 + 1)

    # 坏文件拒绝
    bad = os.path.join(tmp, "bad.zip")
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("other.txt", "x")
    try:
        store_b.import_zip(bad)
        check("非法备份被拒绝", False)
    except ValueError:
        check("非法备份被拒绝", True)


# ---------------------------------------------------------------- GUI

def make_gui_store(tmp):
    """GUI测试专用：全新数据目录 + 完整示例数据（附件文件完好，可渲染缩略图）。"""
    from datetime import datetime, timedelta
    from app.data_store import DataStore

    store = DataStore(os.path.join(tmp, "gui_data"))
    t0 = datetime.today()
    today = t0.strftime("%Y-%m-%d")
    d2 = (t0 + timedelta(days=2)).strftime("%Y-%m-%d")
    store.add_task("换针卡（升级）", "卡点定位", "2026-10-01 08:00", "2026-10-05 18:00", "高")
    store.add_task("校准prober", "温度补偿", "2026-10-01 10:00", "2026-09-28 12:00", "中")
    store.add_task("写周报", "", "2026-10-02 09:00", "2026-10-03 17:30", "弱")
    store.add_task("确认lot放行", "", f"{today} 08:00", f"{today} 17:00", "高")
    store.add_task("盘点耗材", "", f"{today} 09:00", f"{d2} 12:00", "低")
    done = store.add_task("整理wafer盒", "", "2026-09-30 14:00", "2026-09-30", "低")
    store.set_task_status(done["id"], "已完成")

    store.add_memo("机台PM后要重新load recipe（含mapping）", "2026-10-01 12:00")
    store.add_memo("每周五下午17:00交周报", "2026-10-02 09:30")
    store.add_question("lot结批报错E102", "2026-10-01 13:00", "重插fiber后重试")
    store.add_question("prober卡针频率突然升高？", "2026-10-02 15:00", "")

    # 上一周完成的任务（让周报出现多周）
    old = store.add_task("上个月备件盘点", "", "2026-09-21 09:00", "2026-09-23", "低")
    ot = store.find("tasks", old["id"])
    ot["status"] = "已完成"
    ot["completed_at"] = "2026-09-23 15:00"
    store._emit()

    # 解异样例：六要素+图片+时间线+鱼骨
    from app import common as _cm
    aid = _cm.new_id()
    anom_img = os.path.join(tmp, "anom.png")
    make_test_image(anom_img)
    an_att = store.add_attachment(aid, anom_img)
    store.add_anomaly("lot结批报错E102", {
        "background": "10-08 08:15 lot A1024 结批时报错E102，设备停机。",
        "impact": "该lot交付延迟约2小时。",
        "lesson": "去年12月发生过一次类似的fiber故障。",
        "actions": "重启设备、重插fiber、重新结批成功。",
        "root_cause": "fiber接口氧化导致接触不良。",
        "prevention": "点检表增加fiber接口清洁与紧固检查项。",
        "images": [an_att],
        "timeline": [{"time": "10-08 08:15", "event": "结批报错E102"},
                     {"time": "10-08 08:20", "event": "上报并停机检查"},
                     {"time": "10-08 09:00", "event": "重插fiber恢复"},
                     {"time": "10-08 09:30", "event": "重新结批成功"}],
        "fishbone": {"人": ["夜班疲劳"], "机": ["fiber接口氧化"], "料": [],
                     "法": ["点检表缺fiber项"], "环": ["车间湿度偏高"]},
    })

    img_path = os.path.join(tmp, "img.png")
    make_test_image(img_path)
    pptx_path = os.path.join(tmp, "test.pptx")
    make_sample_pptx(pptx_path)
    sop = store.add_sop("针卡清洗SOP", "1.取下针卡\n2.酒精超声5分钟\n3.氮气吹干\n4.上机前显微镜检查针尖")
    atts = [store.add_attachment(sop["id"], img_path),
            store.add_attachment(sop["id"], pptx_path)]
    store.update_sop(sop["id"], attachments=atts)
    store.add_sop("设备日常点检checklist", "1.确认真空度\n2.确认padding对齐")
    return store


def test_gui(store, tmp, shots_dir):
    from PySide6.QtWidgets import QApplication

    from app import theme
    from app.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.QSS)

    win = MainWindow(store)
    win.resize(1160, 720)
    win.show()
    app.processEvents()

    def shot(name):
        app.processEvents()
        pm = win.grab()
        pm.save(os.path.join(shots_dir, name))
        print(f"  [截图] {name}")

    # 各页面
    for idx, name in enumerate(["01_缓急_任务", "02_帮记", "03_解惑", "04_存知"]):
        win.switch_page(idx)
        shot(f"{name}.png")

    # 已完成归档页签 + 按Due Day排序
    win.switch_page(0)
    task_page = win.pages[0]
    task_page.tabs.setCurrentIndex(1)
    shot("01b_已完成归档.png")
    task_page.tabs.setCurrentIndex(0)
    task_page.cbSort.setCurrentIndex(1)
    shot("01c_按DueDay排序.png")
    task_page.cbSort.setCurrentIndex(0)

    # 搜索页（模糊+关联混合场景）
    from app.search import search as run_search
    results = run_search(win._collect_records(), "针卡")
    win.searchPage.show_results("针卡", results)
    win.stack.setCurrentWidget(win.searchPage)
    shot("05_搜索结果.png")

    # 任务对话框
    from app.dialogs import TaskDialog, SopDialog
    dlg = TaskDialog(win, task=store.data["tasks"][0])
    dlg.resize(460, 460)
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(shots_dir, "06_任务编辑对话框.png"))

    # ---- 对话框时间回归（v1.2.1）----
    f = dlg.fields()
    ok = True
    try:
        datetime.strptime(f["start_time"], "%Y-%m-%d %H:%M")
        datetime.strptime(f["due_day"], "%Y-%m-%d %H:%M")
    except ValueError:
        ok = False
    check("对话框存出时间格式正确", ok and "%" not in f["start_time"] + f["due_day"])

    from PySide6.QtCore import QDateTime, QDate
    btns = {b.text(): b for b in dlg.findChildren(__import__("PySide6.QtWidgets",
            fromlist=["QPushButton"]).QPushButton)}
    btns["现在"].click()
    check("开始时间[现在]按钮生效",
          abs(QDateTime.currentDateTime().secsTo(dlg.edStart.dateTime())) <= 5)
    btns["今天"].click()
    check("DueDay[今天]按钮生效",
          dlg.edDue.dateTime().date() == QDate.currentDate())
    dlg.close()

    dlg2 = TaskDialog(win)  # 无参新建，验证默认值解析
    check("旧纯日期due可编辑", dlg2.edDue.dateTime().isValid())
    dlg2.close()

    sop = store.data["sops"][0]
    dlg2 = SopDialog(win, store=store, sop=sop)
    dlg2.resize(600, 560)
    dlg2.show()
    app.processEvents()
    dlg2.grab().save(os.path.join(shots_dir, "07_SOP编辑对话框.png"))
    dlg2.close()

    # ---- 自动刷新：不切页面、不手动刷新，写入数据后当前页立即更新 ----
    from PySide6.QtCore import Qt as _Qt
    task_page = win.pages[0]
    n0 = task_page.tableTodo.rowCount()
    new_task = store.add_task("自动刷新验证任务", "", "2026-10-03 08:00", "2026-10-20", "高")
    check("任务自动刷新", task_page.tableTodo.rowCount() == n0 + 1)

    task_page.locate(new_task["id"])
    cur_item = task_page.tableTodo.item(task_page.tableTodo.currentRow(), 1)
    check("定位到指定任务",
          cur_item is not None and cur_item.data(_Qt.UserRole) == new_task["id"])

    sop_page = win.pages[3]
    sop_page.locate(sop["id"])
    orig_title = sop["title"]
    store.update_sop(sop["id"], title=orig_title + "（已更新）")
    title_widget = sop_page.detailLay.itemAt(0).widget()
    check("SOP详情自动刷新",
          title_widget is not None and "已更新" in title_widget.text())
    store.update_sop(sop["id"], title=orig_title)

    # 搜索结果页开着时数据变化 → 结果自动重查
    win.edSearch.setText("自动刷新验证")
    win._search_now()
    m1 = re.search(r"(\d+)", win.searchPage.lblSummary.text())
    n_res = int(m1.group(1)) if m1 else 0
    store.add_memo("这条备忘包含 自动刷新验证 关键词", "2026-10-05 10:00")
    m2 = re.search(r"(\d+)", win.searchPage.lblSummary.text())
    check("搜索结果自动更新", bool(m2) and int(m2.group(1)) == n_res + 1)
    win.edSearch.clear()

    # 空状态提示在反复刷新后仍然显示（回归）
    from app.data_store import DataStore as _DS
    from app.modules.memos import MemoModule as _MM
    mm = _MM(_DS(os.path.join(tmp, "empty_gui")))
    mm.refresh()
    mm.refresh()
    check("空状态提示可重复显示", mm.emptyLabel is not None)

    # ---- 托盘与到期提醒 ----
    check("托盘图标就绪", win.tray is not None)
    win._check_reminders()
    check("提醒摘要生成", "逾期" in win._last_digest)  # 样例里有逾期任务
    d1 = win._last_digest
    win._check_reminders()
    check("提醒不重复弹", win._last_digest == d1)

    win.actTrayClose.setChecked(False)
    with open(os.path.join(store.data_dir, "settings.json"), encoding="utf-8") as f:
        _st = __import__("json").load(f)
    check("托盘开关已保存", _st.get("close_to_tray") is False)

    # ---- v1.3.0 新页面 ----
    check("导航结构(5模块+周报+回收站)", len(win.pages) == 5 and len(win.navButtons) == 7)
    win.switch_page(4)  # 解异
    shot("10_解异.png")
    win.switch_page(5)  # 周报
    check("周报周列表生成", win.weeklyPage.list.count() >= 1)
    shot("11_周报.png")
    win.switch_page(6)  # 回收站
    shot("12_回收站.png")

    # 删除一条备忘进回收站并恢复（GUI全链路）
    memo = store.data["memos"][0]
    store.delete("memos", memo["id"])
    check("删除进回收站", len(store.data["trash"]) == 1)
    win.switch_page(6)
    shot("12b_回收站有内容.png")
    store.restore(store.data["trash"][0]["id"])
    check("从回收站恢复", store.find("memos", memo["id"]) is not None)

    # 解异PPT全链路（含真实附件图片）
    an = store.data["anomalies"][0]
    out_pptx = os.path.join(tmp, "gui_report.pptx")
    from app.ppt_report import generate_ppt
    generate_ppt(an, [store.attachment_path(x["stored"]) for x in an["images"]], out_pptx)
    check("GUI生成PPT文件", os.path.exists(out_pptx) and os.path.getsize(out_pptx) > 10000)

    # 解异编辑对话框加载带时间线/鱼骨的数据（回归：v1.3.0曾因缺导入崩溃）
    from app.more_dialogs import AnomalyDialog
    adlg = AnomalyDialog(store=store, item=an)
    check("解异编辑加载时间线", adlg.tlTable.rowCount() == len(an.get("timeline", [])))
    check("解异编辑加载鱼骨", adlg.fbEdits["人"].toPlainText() != "")
    f = adlg.fields()
    check("解异字段往返", f["title"] == an["title"]
          and len(f["timeline"]) == len(an.get("timeline", [])))
    adlg.close()

    # 深色调色板兜底生效（表格项文字可读性）
    pal_txt = win.palette().color(win.palette().ColorRole.Text).name()
    check("全局深色调色板生效", pal_txt.lower() in ("#d7e3f4", "#d7e3f4 ".strip()))

    # 搜索跳转逻辑
    win.open_search_result("sops", sop["id"], False)
    check("搜索跳转到存知", win.stack.currentIndex() == 3)

    # 图标
    from app.icons import draw_logo_pixmap, nav_icon
    check("窗口图标非空", not win.windowIcon().isNull())
    check("导航图标非空", not nav_icon("tasks").isNull())

    win.switch_page(2)
    win.close()
    check("窗口状态已保存", os.path.exists(os.path.join(store.data_dir, "settings.json")))
    return 0


def main():
    # exe环境（windowed+GBK控制台）下保证 print 不因编码崩溃
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    only_data = "--nodata-gui" in sys.argv or "--quick" in sys.argv
    tmp = tempfile.mkdtemp(prefix="jarvis_selftest_")
    shots_dir = os.path.join(HERE, "assets", "shots")
    os.makedirs(shots_dir, exist_ok=True)

    # QPixmap 等绘图类需要先有 QGuiApplication（离屏即可）
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("JARVIS_SILENT", "1")  # 自测期间不弹系统托盘通知
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    print("== 1. 数据层 ==")
    store = test_data_layer(tmp)

    print("== 1b. 新功能 ==")
    test_new_features(store, tmp)

    print("== 2. 搜索 ==")
    test_search(store)

    print("== 3. 导入/导出 ==")
    test_export_import(store, tmp)

    if not only_data:
        print("== 4. GUI（离屏）==")
        gui_store = make_gui_store(tmp)
        test_gui(gui_store, tmp, shots_dir)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：", "；".join(FAIL))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
