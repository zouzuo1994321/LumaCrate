# -*- coding: utf-8 -*-
"""v1.25.0 界面预览（离屏渲染出 PNG，供人工核对 6 条反馈的效果）

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/preview_v1250.py', run_name='__main__')"

产出：`dev/screenshots_v1250/*.png`

约定（踩过的坑，与 preview_v1240 / v1241 一致）：
- `QPixmap/QPainter` 必须在 `QApplication` 之后创建，否则 offscreen 原生崩 127；
- 渲染前先注册中文字体（msyh.ttc）+ `load_style(app)`，否则字体回退导致 sizeHint 虚高；
- 用 `QPixmap(w,h)→fill(已知底色)→render()`，**不要**用 `widget.grab()`；
- **必须 `win.show()`**：不 show 时 Qt 不激活布局，卡片几何停在默认值；
- LazyGrid 的卡片要等事件循环，且 `QTimer.singleShot(1, …)` 需要**真实 sleep** 才推得动。

安全：主窗口读的是**真实索引（只读）**；配置写临时目录；
「标签优化」全程只动 `TMP/fix/` 下的临时 nfo，**绝不碰用户磁盘上的任何媒体文件**。
"""
import io
import os
import sys
import time
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

OUT = os.path.join(ROOT, "dev", "screenshots_v1250")
os.makedirs(OUT, exist_ok=True)
# Z: 是同步盘，`shutil.rmtree` 会**静默失败**（ignore_errors 把异常吞掉），
# 上一轮的图就留在目录里冒充本轮产物 —— 改成逐个 unlink 并打印结果。
for _f in os.listdir(OUT):
    try:
        os.remove(os.path.join(OUT, _f))
    except OSError as _e:
        print("  [警告] 清不掉旧图：", _f, _e)
TMP = os.path.join(tempfile.gettempdir(), "lmc_preview_v1250")
FIX = os.path.join(TMP, "fix")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
shutil.rmtree(FIX, ignore_errors=True)
os.makedirs(FIX, exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"

import applog

applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")
applog.log_path = lambda: os.path.join(TMP, "index_data", "logs", "app.log")

import config as cfg
import database as db

cfg.config_path = lambda: os.path.join(TMP, "settings.json")   # 绝不碰用户真实配置

from PySide6.QtCore import QCoreApplication, QRect, QPoint
from PySide6.QtGui import QPixmap, QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

app = QApplication.instance() or QApplication(sys.argv)
for cand in (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyh.ttc"),
             os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyhbd.ttc")):
    if os.path.exists(cand):
        QFontDatabase.addApplicationFont(cand)

import main_window as mw
import tagopt
import ui_home
import ui_settings

mw.load_style(app)


def pump(n=14):
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()
        time.sleep(0.012)


def card_closeup(media, hexv, name, pad=95):
    """特写：新搭一块带留白的画布，放一张**真卡片**进去再挂外发光。

    比「从整块网格里裁一块」可靠 —— 网格是 8000+ px 高的滚动内容，
    按卡片坐标裁剪会算错偏移（第一版就裁出一张只有左边一条的废图）。
    留白就是给外发光用的：光晕能不能溢出卡片、颜色对不对，这张图一眼可见。
    """
    box = QWidget()
    box.setFixedSize(mw.POSTER_W + pad * 2, mw.POSTER_H + pad * 2)
    box.setStyleSheet("background:#17120f;")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(pad, pad, pad, pad)
    lay.setSpacing(0)
    card = mw.PosterCard(media, lambda *a: None, on_select=lambda *a: None)
    lay.addWidget(card)
    box.show()
    pump(8)
    cfg.get_settings().set_accent(hexv)
    mw.render_style({"mode": "经典暗色", "level": "中", "accent": hexv})
    win._select_card(card)
    pump(8)
    eff = card.graphicsEffect()
    print(f"    特写 {name}：blur={eff.blurRadius() if eff else '-'} "
          f"color=({eff.color().red()},{eff.color().green()},{eff.color().blue()},"
          f"a={eff.color().alpha()})" if eff else f"    特写 {name}：没有 effect！")
    shot(box, name)
    box.close()
    return card


def shot(widget, name, w=None, h=None, bg="#0f0d0b"):
    widget.ensurePolished()
    if w is None or h is None:
        w, h = widget.width(), widget.height()
    w, h = max(int(w), 200), max(int(h), 160)
    pm = QPixmap(w, h)
    pm.fill(QColor(bg))
    widget.render(pm)
    path = os.path.join(OUT, f"{name}.png")
    pm.save(path, "PNG")
    print(f"  已保存 {os.path.relpath(path, ROOT)}  {w}x{h}  "
          f"{os.path.getsize(path) // 1024}KB")
    return path


# ============================================================ 临时 nfo（标签优化的素材）
NFO1 = os.path.join(FIX, "ABC-001.nfo")
NFO2 = os.path.join(FIX, "ABC-002.nfo")
NFO3 = os.path.join(FIX, "ABC-003.nfo")
NFO1_TEXT = """<?xml version='1.0' encoding='utf-8'?>
<movie>
  <title>ABC-001 中出し 巨乳 単体作品</title>
  <plot>冒烟简介。</plot>
  <year>2024</year>
  <studio>MOODYZ</studio>
  <set>
    <name>冒烟系列</name>
  </set>
  <genre>中出し</genre>
  <genre>巨乳</genre>
  <genre>単体作品</genre>
  <genre>1080p</genre>
  <genre>フルハイビジョン(FHD)</genre>
  <uniqueid type="tmdb">998877</uniqueid>
  <actor>
    <name>冒烟演员甲</name>
  </actor>
  <director>冒烟导演</director>
  <thumb>ABC-001-poster.jpg</thumb>
</movie>
"""
NFO2_TEXT = """<?xml version='1.0' encoding='utf-8'?>
<movie>
  <title>ABC-002 潮吹き スレンダー</title>
  <studio>S1</studio>
  <genre>潮吹き</genre>
  <genre>スレンダー</genre>
  <genre>キス·接吻</genre>
  <genre>1080p</genre>
</movie>
"""
NFO3_TEXT = """<?xml version='1.0' encoding='utf-8'?>
<movie>
  <title>ABC-003 寝取り·寝取られ·ＮＴＲ パンスト·タイツ</title>
  <studio>IPX</studio>
  <genre>寝取り·寝取られ·ＮＴＲ</genre>
  <genre>パンスト·タイツ</genre>
  <genre>巨乳</genre>
</movie>
"""
for _p, _t in ((NFO1, NFO1_TEXT), (NFO2, NFO2_TEXT), (NFO3, NFO3_TEXT)):
    with io.open(_p, "w", encoding="utf-8", newline="") as f:
        f.write(_t)
print(f"临时 nfo 素材：{FIX}（{len(os.listdir(FIX))} 个，全程只动这里）")

# ============================================================ 主窗口
s = cfg.get_settings()
if not s.library_names():
    s.add_library("冒烟库", "电影", [FIX])
win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
win.resize(1440, 900)
win.show()
pump(10)
print(f"真实索引：{db.count_media(top_only=True):,} 部作品（只读）")

# ============================================================ 反馈 5：12 色高亮 + 外发光
print("\n[1/8] 反馈 5 · 影片墙选中卡片的外发光（朱红 / 天青 两种高亮色对比）")
import colorsys


def lum(rgb):
    return colorsys.rgb_to_hls(*[c / 255.0 for c in rgb])[1]


win.go(lambda: win._wall_page("全部"))
pump(40)
page = win.stack.currentWidget()
cards = page.findChildren(mw.PosterCard)
print(f"  影片墙卡片 {len(cards)} 张")
if len(cards) >= 3:
    target = cards[2]
    s.set_accent("#c0392b")
    mw.render_style({"mode": "经典暗色", "level": "中"})
    win._apply_appearance()
    pump(6)
    win._select_card(target)
    pump(4)
    eff = target.graphicsEffect()
    print(f"  选中《{(target.media.get('title') or '')[:14]}》")
    if eff:
        print(f"    effect={type(eff).__name__} blur={eff.blurRadius()} "
              f"offset=({eff.offset().x()},{eff.offset().y()}) "
              f"color=({eff.color().red()},{eff.color().green()},{eff.color().blue()},"
              f"a={eff.color().alpha()})")
    else:
        print("    选中后没有 effect！")
    shot(win, "01_影片墙_选中外发光_朱红")
    card_closeup(target.media, "#c0392b", "02_卡片特写_外发光_朱红")

    s.set_accent("#3fa9c9")
    mw.render_style({"mode": "经典暗色", "level": "中", "accent": "#3fa9c9"})
    win._apply_appearance()
    pump(6)
    target2 = cards[5] if len(cards) > 5 else cards[1]
    win._select_card(target2)
    pump(4)
    eff2 = target2.graphicsEffect()
    if eff2:
        print(f"  换天青后再选一张 → "
              f"color=({eff2.color().red()},{eff2.color().green()},{eff2.color().blue()},"
              f"a={eff2.color().alpha()})")
    else:
        print("  没有 effect！")
    print(f"  旧卡的外发光已摘掉：{cards[2].graphicsEffect() is None}")
    shot(win, "03_影片墙_选中外发光_天青")
    card_closeup(target2.media, "#3fa9c9", "04_卡片特写_外发光_天青")

# ============================================================ 反馈 6：首页快捷筛选
print("\n[2/8] 反馈 6 · 首页三个快捷筛选的选中态")
holder = QWidget()
holder.resize(1180, 560)
hv = QVBoxLayout(holder)
hv.setContentsMargins(0, 0, 0, 0)
home = ui_home.HomeListView()
hv.addWidget(home)
holder.show()
pump(14)
print(f"  三个 chip：{[(b.text(), b.objectName(), b.isCheckable()) for b in home._chip_btns.values()]}")
shot(holder, "05_首页快捷筛选_默认未选中")
home._click_chip("favorites")
pump(14)
print(f"  点「我的收藏」→ 选中态={home._active_chip} "
      f"checked={[k for k, b in home._chip_btns.items() if b.isChecked()]}")
shot(holder, "06_首页快捷筛选_选中我的收藏")
home._click_chip("collections")
pump(14)
print(f"  再点「合集」→ 选中态转移={home._active_chip}（仍只有一个亮）")
shot(holder, "07_首页快捷筛选_选中合集")
home._click_chip("collections")
pump(14)
print(f"  再点一次同一个 → 取消筛选（active={home._active_chip}）")
holder.close()

# ============================================================ 工具窗口
print("\n[3/8] 打开工具窗口")
win._open_settings()
dlg = win._settings_dlg
dlg.resize(1060, 900)
dlg.show()
pump(6)
_real_ai = ui_settings.AiProbeWorker.start
_real_models = ui_settings.AiModelsWorker.start
ui_settings.AiProbeWorker.start = lambda self: None
ui_settings.AiModelsWorker.start = lambda self: None

# ============================================================ 反馈 5：外观 12 色色板
print("\n[4/8] 反馈 5 · 外观里的 12 种高亮色（朱红 / 鎏金 各一张）")
dlg._show("个性化设置")
pump(8)
print("  12 色：" + "、".join(f"{n}{h}" for n, h in cfg.ACCENT_COLORS))
for hexv, tag in (("#c0392b", "朱红"), ("#d4af37", "鎏金")):
    dlg._apply_accent(hexv)
    pump(8)
    print(f"  切到 {tag} → lb_accent={dlg.lb_accent.text()!r} "
          f"打勾的色块={[h for h, b in dlg._accent_btns.items() if b.text() == '✓']}")
    shot(dlg, f"08_工具_外观_12色高亮_{tag}")

# ============================================================ 反馈 1 / 3：智能推荐页
print("\n[5/8] 反馈 1 + 3 · 智能推荐页（调用模型 / 轮次去重）")
dlg._show("智能推荐")
pump(10)
dlg.ed_ai_model.setText("qwen2.5:7b")
dlg._on_ai_model_edited()
dlg.sp_rounds.setValue(5)
pump(6)
# 造两轮历史，让「已记录 N 轮 / 当前避让 M 部」有内容
cfg.get_settings().clear_smart_history()
cfg.get_settings().push_smart_round([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
cfg.get_settings().push_smart_round([101, 102, 103, 104, 105, 106, 107, 108])
dlg._refresh_hist_label()
dlg._on_ai_models(["qwen2.5:7b", "llama3.1:8b", "qwen3:4b"])
pump(6)
print(f"  ed_ai_model={dlg.ed_ai_model.text()!r}  sp_rounds={dlg.sp_rounds.value()} 轮")
print(f"  本机模型下拉：{[dlg.cb_ai_model.itemText(i) for i in range(dlg.cb_ai_model.count())]}")
print(f"  历史标签：{dlg.lb_hist.text()}")
shot(dlg, "09_工具_智能推荐_模型与轮次")
dlg._on_ai_probe({"engine": "builtin",
                  "label": "内置离线联想引擎（指定模型 qwen2.5:7b 未安装）",
                  "detail": "设置里指定的是「qwen2.5:7b」，但本机 Ollama 里没有这个模型，"
                            "已自动降级为内置联想。本机已装：llama3.1:8b、qwen3:4b。"
                            "可在设置里改成上面其中之一，或执行「ollama pull qwen2.5:7b」把它装上。"})
pump(6)
print(f"  检测结论：{dlg.ai_state.text()[:120]}")
shot(dlg, "10_工具_智能推荐_指定模型未装的提示")

# ============================================================ 反馈 4：标签优化
print("\n[6/8] 反馈 4 · 标签优化（真跑一遍：临时 nfo 上 预览 → 写入）")
dlg._show("标签优化")
pump(10)
dlg.rb_to_folder.setChecked(True)
dlg.to_path.setText(FIX)
dlg.ck_to_trans.setChecked(True)
dlg.ck_to_over.setChecked(False)
dlg.ck_to_full.setChecked(True)
dlg.ck_to_bak.setChecked(True)
dlg.rb_to_normal.setChecked(True)
dlg._tagopt_save_prefs()
pump(6)
shot(dlg, "11_工具_标签优化_页面")

opt = tagopt.TagOptimizer(cfg.get_settings())
nfos = opt.collect("folder", FIX)
print(f"  扫描到 {len(nfos)} 个 nfo：{[os.path.basename(x) for x in nfos]}")
plans = opt.plan(nfos, **dlg._tagopt_kwargs())
for p in plans:
    print(f"    {os.path.basename(p['nfo'])}：原有 {len(p['before'])} → 新增 "
          f"{len(p['added'])}，日语→中文 {len(p['translated'])} "
          f"{[f'{a}→{b}' for a, b in p['translated']]}")
dlg._to_plans = plans
dlg._to_changed = [p for p in plans if p["before"] != p["after"]]
dlg._fill_to_table(plans)
dlg.btn_to_run.setEnabled(bool(dlg._to_changed))
dlg.to_status.setText(f"预览完成：{len(plans)} 个文件，其中 {len(dlg._to_changed)} 个标签会变化"
                      f"（只读预览，尚未写入任何文件）")
pump(8)
shot(dlg, "12_工具_标签优化_扫描预览")

# 真写入（只写临时目录）
stats = opt.apply(dlg._to_changed, backup=dlg.ck_to_bak.isChecked())
dlg._on_tagopt_applied(stats)
pump(8)
print(f"  写入结果：{stats}")
shot(dlg, "13_工具_标签优化_写入完成")

# 逐字节证据：备份 == 改动前；<genre> 已重写；非 genre 内容原样
print("\n[7/8] 回环证据（临时 nfo）")
baks = [f for f in os.listdir(FIX) if ".bak-" in f]
print(f"  备份文件 {len(baks)} 个：{baks}")
if baks:
    bak_text = io.open(os.path.join(FIX, baks[0]), encoding="utf-8", newline="").read()
    print(f"  {baks[0]} 与改动前逐字节相同：{bak_text == NFO1_TEXT}")
after = io.open(NFO1, encoding="utf-8", newline="").read()
print("  ABC-001 现状：")
for line in after.splitlines():
    if "<genre>" in line or "<name>" in line or "uniqueid" in line:
        print("   ", line.strip())
_indented = "\n  <genre>" in after
print(f"  技术标签 1080p 还在：{'<genre>1080p</genre>' in after}")
print(f"  演员节点原样：{'<name>冒烟演员甲</name>' in after}")
print(f"  导演节点原样：{'<director>冒烟导演</director>' in after}")
print(f"  uniqueid 原样：{'998877' in after}   缩进 2 空格：{_indented}")

# 高亮色板特写（把色块那一行单独渲染）
print("\n[8/8] 图片清单")
for f in sorted(os.listdir(OUT)):
    print("   ", f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")

ui_settings.AiProbeWorker.start = _real_ai
ui_settings.AiModelsWorker.start = _real_models
dlg.close()
win.close()
pump(4)
print("\n预览完成 →", os.path.relpath(OUT, ROOT))
