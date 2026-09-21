# -*- coding: utf-8 -*-
"""临时探针：验证 smoke 的 NFO fixture 是否能被 ElementTree 解析。"""
import os, sys, tempfile, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import nfo_parser as nfo

NFO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>390JAC-240 テスト標題</title>
  <originaltitle>390JAC-240</originaltitle>
  <sorttitle>390JAC-240</sorttitle>
  <year>2026</year>
  <ratings>
    <rating default="false" max="100" name="tomatometerallcritics"><value>45.0</value><votes>0</votes></rating>
    <rating default="false" max="10" name="NFO"><value>4.5</value><votes>0</votes></rating>
  </ratings>
  <userrating>9.9</userrating>
  <set/>
  <plot/>
  <tagline>发行日期 2026-08-17</tagline>
  <runtime>116</runtime>
  <mpaa>US:NC-17 / US:Rated NC-17</mpaa>
  <certification>US:NC-17 / US:Rated NC-17</certification>
  <premiered>2026-08-17</premiered>
  <genre>AVC1</genre><genre>720P</genre><genre>390JAC</genre><genre>白雪美月</genre><genre>巨乳</genre>
  <studio>Jackson</studio>
  <actor><name>白雪美月</name></actor>
  <fileinfo><streamdetails><video><codec>h264</code><width>1280</width><height>720</height><resolution>720</resolution></video></streamdetails></fileinfo>
</movie>"""

d = tempfile.mkdtemp(prefix="probe_")
p = os.path.join(d, "t.nfo")
with open(p, "w", encoding="utf-8") as f:
    f.write(NFO)

print("=== repr of first 3 lines ===")
for i, ln in enumerate(NFO.splitlines()[:3]):
    print(i, repr(ln))
print("=== line 20 ===", repr(NFO.splitlines()[19]) if len(NFO.splitlines()) > 19 else "n/a")
try:
    info = nfo.parse_movie(p)
    print("PARSE OK:", info.get("title"), info.get("rating"), info.get("user_rating"), info.get("resolution"))
except Exception:
    traceback.print_exc()
