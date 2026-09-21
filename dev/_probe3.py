# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET

tests = [
    '<movie><video><codec>h264</codec></video></movie>',
    '<movie><fileinfo><streamdetails><video><codec>h264</codec></video></streamdetails></fileinfo></movie>',
    '<movie><fileinfo><streamdetails><video><codec>h264</codec><width>1280</width></video></streamdetails></fileinfo></movie>',
    '<movie><video><codec>h264</codec><width>1280</width></video></movie>',
    '<movie><width>1280</width></movie>',
    '<movie><resolution>720</resolution></movie>',
    '<movie><fileinfo><streamdetails><video><codec>h264</code><width>1280</width><height>720</height><resolution>720</resolution></video></streamdetails></fileinfo></movie>',
]
for xml in tests:
    try:
        ET.fromstring(xml)
        print("OK  ", xml[:70])
    except Exception as e:
        print("FAIL", xml[:70], "->", e)
