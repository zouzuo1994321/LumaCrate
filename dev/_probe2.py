# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET

cands = {
    "fileinfo_single": '<movie><fileinfo><streamdetails><video><codec>h264</code><width>1280</width><height>720</height><resolution>720</resolution></video></streamdetails></fileinfo></movie>',
    "fileinfo_multiline": '<movie>\n<fileinfo>\n<streamdetails>\n<video>\n<codec>h264</code>\n<width>1280</width>\n</video>\n</streamdetails>\n</fileinfo>\n</movie>',
    "ratings": '<movie><ratings><rating max="10"><value>4.5</value></rating></ratings></movie>',
    "set_plot": '<movie><set/><plot/></movie>',
    "jc_head": '<movie><title>\u30c6\u30b9\u30c8\u6a19\u984c</title></movie>',
}
for name, xml in cands.items():
    try:
        ET.fromstring(xml)
        print("OK  ", name)
    except Exception as e:
        print("FAIL", name, "->", e)
