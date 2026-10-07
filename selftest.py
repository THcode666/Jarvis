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

    # 删除（SOP附件随之删除）
    did = sop1["id"]
    stored_name = att_ppt["stored"]
    store2.delete("sops", did)
    check("删除SOP并清理附件", not os.path.exists(store2.attachment_path(stored_name)))
    return store


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
    from app.data_store import DataStore

    store = DataStore(os.path.join(tmp, "gui_data"))
    store.add_task("换针卡（升级）", "卡点定位", "2026-10-01 08:00", "2026-10-05", "高")
    store.add_task("校准prober", "温度补偿", "2026-10-01 10:00", "2026-09-28", "中")
    store.add_task("写周报", "", "2026-10-02 09:00", "2026-10-03", "弱")
    done = store.add_task("整理wafer盒", "", "2026-09-30 14:00", "2026-09-30", "低")
    store.set_task_status(done["id"], "已完成")

    store.add_memo("机台PM后要重新load recipe（含mapping）", "2026-10-01 12:00")
    store.add_memo("每周五下午17:00交周报", "2026-10-02 09:30")
    store.add_question("lot结批报错E102", "2026-10-01 13:00", "重插fiber后重试")
    store.add_question("prober卡针频率突然升高？", "2026-10-02 15:00", "")

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
    dlg.resize(460, 420)
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(shots_dir, "06_任务编辑对话框.png"))
    dlg.close()

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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    print("== 1. 数据层 ==")
    store = test_data_layer(tmp)

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
