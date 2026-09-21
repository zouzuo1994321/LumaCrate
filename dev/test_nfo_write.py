# -*- coding: utf-8 -*-
"""验证 nfo 用户评分写回 + 回读是否正确。"""
import os, tempfile, sys
sys.path.insert(0, r"Z:\【01】自研软件\【26-19】本地影视中心\src")
import nfo_parser

d = tempfile.mkdtemp()
nfo = os.path.join(d, "movie.nfo")
with open(nfo, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="utf-8"?>\n'
            '<movie><title>Test</title><rating>7.5</rating></movie>\n')

print("== before ==")
print(open(nfo, encoding="utf-8").read())
ok = nfo_parser.write_user_rating(nfo, 8.5)
print("write ok:", ok)
print("== after write ==")
print(open(nfo, encoding="utf-8").read())
info = nfo_parser.parse_movie(nfo)
print("parsed user_rating after write:", info.get("user_rating"))
ok2 = nfo_parser.write_user_rating(nfo, None)
print("clear ok:", ok2)
print("== after clear ==")
print(open(nfo, encoding="utf-8").read())
info2 = nfo_parser.parse_movie(nfo)
print("parsed user_rating after clear:", info2.get("user_rating"))
print("DONE")
