# -*- coding: utf-8 -*-
"""v1.36.0 打包前 30 秒闸门。

抓的是「改了一处、另一处没跟上」这类**只在 frozen 才炸**的错误（v1.22.0 的
`logo_path` 漏接就是被这道闸门先抓住的）。跑完再打包，省掉一整个废包。

检查项：
1. 版本号 / 构建号；
2. `MainWindow` 的 `__init__` 签名（`main.py` 会传什么，这里就必须接什么）；
3. 本版新增 / 改动的方法与属性确实在文件里；
4. `guide_translate` 的关键 API 与规模；
5. `build_exe.py` 的 `--hidden-import guide_translate`（漏了 = exe 里 ModuleNotFoundError）；
6. 设置页的复选框与落盘键名。
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# ---------------- 1. 模块可导入 ----------------
import version as ver            # noqa: E402
import config as cfg             # noqa: E402
import recommend as rec_mod      # noqa: E402
import guide_translate as gt     # noqa: E402
import ui_settings as uis        # noqa: E402
import main_window as mw         # noqa: E402
import database as db            # noqa: E402
import splash                    # noqa: E402

check("version 版本号 = v1.36.0", ver.VERSION == "v1.36.0", ver.VERSION)
check("version 构建号 = 2609300054", ver.BUILD == "2609300054", ver.BUILD)
check("exe 名 = 流明盒-v1.36.0-2609300054",
      f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}" == "流明盒-v1.36.0-2609300054")
check("版权声明保留",
      "肆月Aperture" in ver.COPYRIGHT
      and "没有授权禁止用于商业用途" in getattr(ver, "LICENSE_NOTE", ""),
      (ver.COPYRIGHT, getattr(ver, "LICENSE_NOTE", None)))

# ---------------- 2. MainWindow 签名 ----------------
sig = inspect.signature(mw.MainWindow.__init__)
params = set(sig.parameters)
for kw in ("logo_path", "self"):
    check(f"MainWindow.__init__ 接受 {kw}", kw in params, sorted(params))

# ---------------- 3. 本版新增 / 改动的方法 ----------------
for name in ("_guide_ja_enabled", "_add_guide", "_refresh_guides", "_guide_bar",
             "_guide_row", "_toggle_guides_expand", "_smart_wall", "_replace_current",
             "_open_media", "_select_card"):
    check(f"MainWindow 有方法 {name}", hasattr(mw.MainWindow, name),
          [n for n in ("_guide_ja_enabled",) if not hasattr(mw.MainWindow, n)])
check("GUIDE_CHIP_LIMIT 是正整数",
      isinstance(getattr(mw.MainWindow, "GUIDE_CHIP_LIMIT", None), int)
      and mw.MainWindow.GUIDE_CHIP_LIMIT > 0, getattr(mw.MainWindow, "GUIDE_CHIP_LIMIT", None))

# 四处鼠标处理器都要在（v1.36.0 的缺陷修复点）
for cls, meth in ((mw.PosterCard, "mousePressEvent"),
                  (mw.PosterCard, "mouseDoubleClickEvent"),
                  (mw.ActorCard, "mousePressEvent"),
                  (mw.ActorCard, "mouseDoubleClickEvent"),
                  (mw.FolderCard, "mousePressEvent")):
    check(f"{cls.__name__}.{meth} 存在", callable(getattr(cls, meth, None)))

# ---------------- 4. guide_translate ----------------
check("guide_translate.translate_zh_to_ja 可调用", callable(gt.translate_zh_to_ja))
check("CHAR_MAP > 400 组", len(gt.CHAR_MAP) > 400, len(gt.CHAR_MAP))
check("LEXICON > 100 条", len(gt.LEXICON) > 100, len(gt.LEXICON))
check("MAX_VARIANTS 是正整数", isinstance(gt.MAX_VARIANTS, int) and gt.MAX_VARIANTS > 0,
      gt.MAX_VARIANTS)
for _src, _want in (("轮奸", "輪姦"), ("三上悠亚", "三上悠亜"), ("中出", "中出し"),
                    ("护士", "ナース"), ("孕妇教师", "妊婦")):
    check(f"translate({_src}) 含 {_want}", _want in gt.translate_zh_to_ja(_src),
          gt.translate_zh_to_ja(_src))

# ---------------- 5. 偏好键 ----------------
check("DEFAULT_RECOMMEND 含 guide_ja_translate",
      "guide_ja_translate" in cfg.DEFAULT_RECOMMEND)
check("guide_ja_translate 默认关闭",
      cfg.DEFAULT_RECOMMEND.get("guide_ja_translate") is False)
_src_cfg = open(os.path.join(SRC, "config.py"), encoding="utf-8").read()
check("_sanitize_recommend 里对 guide_ja_translate 做了字符串归一（不是裸 bool()）",
      'guide_ja_translate' in _src_cfg
      and 'not in ("", "0", "false", "no", "off")' in _src_cfg)

# ---------------- 6. 设置页 ----------------
_src_uis = open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read()
check("ui_settings 建了 ck_guide_ja", "self.ck_guide_ja = QCheckBox" in _src_uis)
check("ui_settings 落盘 guide_ja_translate", 'kw["guide_ja_translate"]' in _src_uis)
_i_grp = _src_uis.index('QGroupBox("推荐范围与偏好")')
_i_ck = _src_uis.index("self.ck_guide_ja = QCheckBox")
# ⚠ `v.addWidget(g2)` 在 ui_settings 里出现 9 次（每个设置页都有一个 g2）——
# 必须从复选框位置**向后**找那一个，否则永远命中第一个、断言必假 FAIL。
_i_end = _src_uis.index("v.addWidget(g2)", _i_ck)
check("复选框在「推荐范围与偏好」组里（组内、且在本组结束之前）",
      _i_grp < _i_ck < _i_end, (_i_grp, _i_ck, _i_end))

# ---------------- 7. 打包参数 ----------------
_src_be = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
check('build_exe.py 有 --hidden-import guide_translate',
      '"--hidden-import", "guide_translate"' in _src_be)
check("build_exe.py 仍用 logo-4.png",
      "'logo-4.png')" in _src_be and "'logo-3.png')};" not in _src_be)
check("EXE_NAME 由 version 拼出来（不写死）",
      'EXE_NAME = f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}"' in _src_be)

# ---------------- 8. main_window 引用 ----------------
_src_mw = open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
check("main_window 顶层 import guide_translate", "import guide_translate as gt_mod" in _src_mw)
check("_add_guide 里调用了 translate_zh_to_ja",
      "gt_mod.translate_zh_to_ja(text)" in _src_mw)
check("回调之后不再触碰 self（双击修复的结构性判据）",
      "on_open(media)      # 之后不再访问 self" in _src_mw)
# 旧的危险写法必须已经消失
check("旧写法 `self._on_open(self.media)` + `super()` 已清除",
      "self._on_open(self.media)" not in _src_mw
      and "self._on_open(self.person)" not in _src_mw)

# ---------------- 9. 数据层没被动过 ----------------
check("MEDIA_SORTS 白名单仍在", isinstance(getattr(db, "MEDIA_SORTS", None), (dict, tuple, list)))
check("recommend.GUIDE_HEAD 仍在（5 维）", len(rec_mod.GUIDE_HEAD) == 5, rec_mod.GUIDE_HEAD)

print("")
print(f"==== _check_v1360：{'GREEN' if not FAIL else 'RED'}（失败 {len(FAIL)} 项）====")
for n in FAIL:
    print("  FAIL:", n)
sys.exit(1 if FAIL else 0)
