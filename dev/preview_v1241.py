# -*- coding: utf-8 -*-
"""v1.24.1 界面预览（离屏渲染出 PNG，供人工核对 4 条反馈的修复效果）

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/preview_v1241.py', run_name='__main__')"

产出：`dev/screenshots_v1241/*.png`

约定（踩过的坑，与 preview_v1240 一致）：
- `QPixmap/QPainter` 必须在 `QApplication` 之后创建，否则 offscreen 原生崩 127；
- 渲染前先注册中文字体（msyh.ttc）+ `load_style(app)`，否则字体回退导致 sizeHint 虚高；
- 用 `QPixmap(w,h)→fill(已知底色)→render()`，**不要**用 `widget.grab()`；
- **必须 `win.show()`**：不 show 时 Qt 不激活布局，卡片几何停在默认值，render 出来只有工具栏；
- LazyGrid 的卡片要等事件循环，且 `QTimer.singleShot(1, …)` 需要**真实 sleep** 才推进得动。
"""
import os
import sys
import time
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

OUT = os.path.join(ROOT, "dev", "screenshots_v1241")
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(tempfile.gettempdir(), "lmc_preview_v1241")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"

import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")
applog.log_path = lambda: os.path.join(TMP, "index_data", "logs", "app.log")

import config as cfg
import database as db
cfg.config_path = lambda: os.path.join(TMP, "settings.json")   # 绝不碰用户真实配置

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QPixmap, QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget, QLabel

app = QApplication.instance() or QApplication(sys.argv)
for cand in (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyh.ttc"),
             os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyhbd.ttc")):
    if os.path.exists(cand):
        QFontDatabase.addApplicationFont(cand)

import main_window as mw
mw.load_style(app)


def pump(n=14):
    """推事件循环（必须带真实 sleep，见文件头说明）。"""
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()
        time.sleep(0.012)


def shot(widget, name, w=None, h=None):
    widget.ensurePolished()
    if w is None or h is None:
        w, h = widget.width(), widget.height()
    w, h = max(int(w), 200), max(int(h), 160)
    pm = QPixmap(w, h)
    pm.fill(QColor("#0f0d0b"))
    widget.render(pm)
    path = os.path.join(OUT, f"{name}.png")
    pm.save(path, "PNG")
    print(f"  已保存 {os.path.relpath(path, ROOT)}  {w}x{h}")
    return path


def audit_cards(page, tag):
    """逐张核对海报与两个角标按钮 —— 这就是反馈 1 的判据（占位图 = 照片没显示）。"""
    cards = page.findChildren(mw.PosterCard)
    ph_img = mw.placeholder_pixmap(mw.POSTER_W, mw.POSTER_H, text="占").toImage()
    placeholders, no_fav, no_play = [], [], []
    playable_n = 0
    for c in cards:
        img = None
        for l in c.findChildren(QLabel):
            pm = l.pixmap()
            if pm is not None and not pm.isNull() and l.width() == mw.POSTER_W:
                img = l
                break
        if img is None or img.pixmap().toImage() == ph_img:
            placeholders.append((c.media.get("title") or "")[:12])
        if c.fav_btn is None:
            no_fav.append((c.media.get("title") or "")[:12])
        if mw.playable_media(c.media):
            playable_n += 1
            if c.play_btn is None:
                no_play.append((c.media.get("title") or "")[:12])
    print(f"    [{tag}] 卡片 {len(cards)} 张 · 可播放 {playable_n} 张 · "
          f"占位图 {len(placeholders)} 张 · 缺 ☆ {len(no_fav)} 张 · 缺 ▶ {len(no_play)} 张")
    if placeholders:
        print(f"      占位图示例：{placeholders[:3]}")
    return len(cards), placeholders, no_fav, no_play


# ---------------------------------------------------------------- 准备主窗口
s = cfg.get_settings()
if not s.library_names():
    s.add_library("Jav-library", "电影", [os.path.join(TMP, "lib")])
win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win.resize(1440, 900)
win.show()
pump(10)

TOTAL = db.count_media(top_only=True)
print(f"真实索引：{TOTAL:,} 部作品（只读）")

# ---------------------------------------------------------------- 反馈 1：推荐墙
print("\n[1/7] 反馈 1 · 智能推荐墙（海报 + 左下☆ + 右下▶）")
import recommend as rec_mod
import insight as ins_mod      # noqa: F401  （仅为确认模块可导入）

res = rec_mod.recommend(page=1, limit=24, algo="normal")
raw_picks = res.get("picks", [])
print(f"  推荐引擎返回 {len(raw_picks)} 条；"
      f"原始结果里有没有 poster = {'poster' in (raw_picks[0] if raw_picks else {})}"
      f" / file_path = {'file_path' in (raw_picks[0] if raw_picks else {})}")
hydrated = mw.MainWindow._hydrate_picks(raw_picks)
print(f"  回填后：有没有 poster = {'poster' in (hydrated[0] if hydrated else {})}"
      f" / file_path = {'file_path' in (hydrated[0] if hydrated else {})}")
if raw_picks:
    kept = [k for k in ("score", "reason") if k in hydrated[0]]
    print(f"  推荐专有字段保留情况：{kept}")

win._smart_res = res
win._smart_picks = hydrated
win._smart_algo = "normal"
win.go(lambda: win._smart_wall())
pump(30)
c, ph, nf, np_ = audit_cards(win.stack.currentWidget(), "智能推荐")
shot(win, "01_智能推荐_海报与角标")

# 卡片特写：把第一张卡单独渲染出来，☆ 与 ▶ 一目了然
cards = win.stack.currentWidget().findChildren(mw.PosterCard)
if cards:
    shot(cards[0], "02_推荐卡特写_左下星标右下播放",
         cards[0].width(), cards[0].height())
    m = cards[0].media
    print(f"  特写卡：《{m.get('title')}》 收藏={bool(m.get('favorite'))} "
          f"星标={'有' if cards[0].fav_btn else '无'} "
          f"播放键={'有' if cards[0].play_btn else '无'}")

# ---------------------------------------------------------------- 反馈 3：导演库
print("\n[2/7] 反馈 3 · 导演库（点 ☆ / ▲ 原地重排，不再跳演员库）")
win.go(win._view_directors)
pump(30)
cur = win.stack.currentWidget()
print(f"  导演卡 {len(cur.findChildren(mw.DirectorCard))} 张；"
      f"_people_builder = {getattr(win._people_builder, '__name__', None)}")
shot(win, "03_导演库_收藏置顶不跳页")

# ---------------------------------------------------------------- 工具窗口
print("\n[3/7] 打开工具窗口")
win._open_settings()
dlg = win._settings_dlg
dlg.resize(1000, 880)
dlg.show()
pump(6)

import ui_settings
_real_ins_start = ui_settings.PortraitWorker.start
ui_settings.PortraitWorker.start = lambda self: None      # 别真起线程，手动喂结果
_real_ai_start = ui_settings.AiProbeWorker.start
ui_settings.AiProbeWorker.start = lambda self: None

# ---------------------------------------------------------------- 反馈 4：画像概览
print("\n[4/7] 反馈 4 · 画像概览：统计范围加入「我的收藏」")
dlg._show("画像概览")
texts = [dlg.ins_lib.itemText(i) for i in range(dlg.ins_lib.count())]
print(f"  统计范围下拉：{texts}")
for combo_idx, title, fav in ((0, "全部媒体库", False), (1, "我的收藏", True)):
    dlg.ins_lib.blockSignals(True)          # 别触发 _on_insight_scope 里的重算
    dlg.ins_lib.setCurrentIndex(combo_idx)
    dlg.ins_lib.blockSignals(False)
    data = ins_mod.Portrait(favorites_only=fav).build()
    dlg._insight_pending = False
    dlg._on_insight_done(data)
    pump(8)
    ov = data["overview"]
    print(f"  范围「{ov['scope']}」：作品 {ov['media']:,} 部 · 收藏 {ov['favorite']:,} 部 · "
          f"演员关联 {ov['actor_links']:,} 条 · 导演关联 {ov['director_links']:,} 条")
    print(f"    一句话画像：{data['line'][:78]}")
    shot(dlg, f"04_画像概览_{title}")

# ---------------------------------------------------------------- 反馈 2：AI 检测反馈
print("\n[5/7] 反馈 2 · 检测本地 AI 引擎（点下去有反馈）")
dlg._show("智能推荐")
pump(6)
dlg._ai_worker = None
dlg._refresh_ai_state()
pump(4)
print(f"  忙碌态文案：{dlg.ai_state.text()}")
print(f"  按钮：enabled={dlg.ai_test.isEnabled()} text={dlg.ai_test.text()!r}")
shot(dlg, "05_工具_智能推荐_检测中")

dlg._on_ai_probe(rec_mod.ai_status())          # 真实结论（本机未装 Ollama → ⚠）
pump(4)
print(f"  结果文案：{dlg.ai_state.text()[:96]}")
shot(dlg, "06_工具_智能推荐_检测结果带时间戳")

dlg._on_ai_probe({"engine": "ollama", "label": "本地 Ollama（qwen2.5:7b）",
                  "detail": "离线扩词已启用：会把偏好种子词交给本地模型做语义扩展。"})
pump(4)
shot(dlg, "07_工具_智能推荐_检出Ollama")

# 向量编辑页（v1.24.0 新增，用户在真机上已经编了 70 条权重）
try:
    print(f"\n[6/7] 向量编辑（本机已有 {len(db.vector_overrides())} 条手动权重）")
    dlg._open_vector_editor()
    pump(8)
    ved = dlg._vector_dlg
    ved.resize(720, 620)
    ved.show()
    pump(6)
    shot(ved, "08_工具_向量编辑")
    ved.close()
except Exception as e:
    print("   向量编辑出图失败：", e)

# 摘要
print("\n[7/7] 图片清单")
for f in sorted(os.listdir(OUT)):
    print("   ", f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")

ui_settings.PortraitWorker.start = _real_ins_start
ui_settings.AiProbeWorker.start = _real_ai_start
dlg.close()
win.close()
pump(4)
print("\n预览完成 →", os.path.relpath(OUT, ROOT))
