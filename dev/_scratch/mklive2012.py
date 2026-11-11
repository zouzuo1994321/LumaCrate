# -*- coding: utf-8 -*-
"""把 live_v2010_exe.py 复制并改成 v2.0.12 版（只做机械替换，其余用手改）。"""
import io
import os

D = r"E:\【01】自研软件\【26-19】本地影视中心\dev\_scratch"
src = os.path.join(D, "live_v2010_exe.py")
dst = os.path.join(D, "live_v2012_exe.py")
s = io.open(src, encoding="utf-8").read()

s = s.replace('BUILD_TAG = "2611050131"', 'BUILD_TAG = "2611100133"')
s = s.replace('VER_TAG = "v2.0.10"', 'VER_TAG = "v2.0.12"')
s = s.replace('v2010_%s.png', 'v2012_%s.png')
s = s.replace('LIVE_V2010_FAIL', 'LIVE_V2012_FAIL')
s = s.replace('LIVE_V2010_ALL_OK', 'LIVE_V2012_ALL_OK')
s = s.replace('lmc_exe_v2010', 'lmc_exe_v2012')
s = s.replace('========== v2.0.10 真机验收（首页筛选中文输入） ==========',
              '========== v2.0.12 真机验收（圆角黑框 + 中文输入回归） ==========')

io.open(dst, "w", encoding="utf-8", newline="").write(s)
print("written", dst, len(s), "| v2010 残留:", s.count("v2010"))
