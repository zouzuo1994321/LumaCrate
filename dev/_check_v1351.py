# -*- coding: utf-8 -*-
"""v1.35.1 打包前 30 秒闸门：签名 / 方法 / 资源 / 模块 import 全量自检。

只做静态与 import 级校验，不建 Qt 窗口；任何一项不过就 exit(1)，阻止打包。
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_SYSMON", "1")

FAIL = []


def ok(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("  -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# 1) 关键模块 import
import version as ver                     # noqa: E402
import main_window as mw                  # noqa: E402
import recommend as rec                   # noqa: E402
import ui_settings                        # noqa: E402
import database as db                     # noqa: E402
import config as cfg                      # noqa: E402
import splash as splash_mod               # noqa: E402
print("[import] version / main_window / recommend / ui_settings / database / config / splash 全部 OK")

# 2) 签名（v1.22.0 踩过：main.py 传 logo_path、main_window 没落盘 → frozen 启动即 TypeError）
sig = inspect.signature(mw.MainWindow.__init__)
ok("MainWindow.__init__ 接受 logo_path", "logo_path" in sig.parameters, list(sig.parameters))

# 3) 本版新增 / 改动的成员
ok("MainWindow.GUIDE_CHIP_LIMIT 存在且为正整数",
   isinstance(getattr(mw.MainWindow, "GUIDE_CHIP_LIMIT", None), int)
   and mw.MainWindow.GUIDE_CHIP_LIMIT > 0, getattr(mw.MainWindow, "GUIDE_CHIP_LIMIT", None))
for meth in ("_guide_bar", "_guide_row", "_toggle_guides_expand", "_refresh_guides", "_smart_wall"):
    ok(f"MainWindow.{meth} 存在", callable(getattr(mw.MainWindow, meth, None)))

# 4) 品牌图标：源图存在 + 三处引用已切
ok("logo-4.png 存在", os.path.exists(os.path.join(ROOT, "logo-4.png")))
main_src = open(os.path.join(SRC, "main.py"), encoding="utf-8").read()
ok('main.py 引用 logo-4.png 且无 "logo-3.png" 字面量',
   "_app_resource(\"logo-4.png\")" in main_src and '"logo-3.png"' not in main_src)
splash_src = open(os.path.join(SRC, "splash.py"), encoding="utf-8").read()
ok('splash.py 引用 logo-4.png 且无 "logo-3.png" 字面量',
   '"logo-4.png"' in splash_src and '"logo-3.png"' not in splash_src)
be_src = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
ok("build_exe.py 已切到 logo-4.png",
   "'logo-4.png')" in be_src and "'logo-3.png')};" not in be_src)

# 5) 版本
ok("外部版本号 = v1.35.1", ver.VERSION == "v1.35.1", ver.VERSION)
ok("内部构建号 = 2609300053", ver.BUILD == "2609300053", ver.BUILD)
ok("exe 产物名", (f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}") == "流明盒-v1.35.1-2609300053",
   f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}")

# 6) 版权声明
ok("版权声明保留", "肆月Aperture" in ver.COPYRIGHT and "禁止用于商业用途" in ver.LICENSE_NOTE)

print("")
print(f"==== v1.35.1 打包闸门：{'PASS' if not FAIL else 'FAIL'} (失败 {len(FAIL)}) ====")
for n in FAIL:
    print("  FAIL:", n)
sys.exit(1 if FAIL else 0)
