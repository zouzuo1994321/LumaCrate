# -*- coding: utf-8 -*-
"""v1.25.0 真机验收配套补丁：刷新点击坐标 + 扩展 live_verify 覆盖面。

背景：v1.25.0 在工具窗口导航里**插入**了新页「标签优化」（位置在「智能推荐」之后），
于是 `lmc_ui_coords.json` 里缓存的「服务管理 / 重复检测 / 数据与日志」纵坐标整体下移
一格 —— 不刷新就会点错页，而且「重复检测」那一步还会真等 85 秒，白等。

本补丁做两件事：
1. ui_coords.py 补出「标签优化」页要用到的按钮坐标；
2. live_verify.py：首页加入截图列表（验反馈 6 的三个快捷筛选芯片）、工具窗口多走
   一遍「标签优化」页（扫描预览 → 执行写入），并且写入用的是 %TEMP% 下的夹具 nfo，
   真机上不碰用户任何真实文件。

写入一律 `newline=""`，避免 Write/Edit 工具把 LF 转成 CRLF（本项目已踩过）。
"""
import os
import sys

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"


def patch(rel, label, old, new, count=1):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 {count}）")
        print("----- 锚点 -----")
        print(old[:400])
        raise SystemExit(1)
    s = s.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {label}")


# ---------------------------------------------------------------- ui_coords.py
patch(
    r"dev\_scratch\ui_coords.py",
    "ui_coords：补「标签优化」页坐标",
    '''dlg._show("重复检测")
app.processEvents()
_d = [b for b in dlg.findChildren(QPushButton) if b.text() == "开始检测"]
res["dedupe_start_btn"] = center(_d[0], dlg) if _d else None
res["dedupe_excl_ck"] = center(dlg.dd_excl, dlg) if dlg.dd_excl else None
res["dedupe_verify_ck"] = center(dlg.dd_verify, dlg) if dlg.dd_verify else None
''',
    '''dlg._show("重复检测")
app.processEvents()
_d = [b for b in dlg.findChildren(QPushButton) if b.text() == "开始检测"]
res["dedupe_start_btn"] = center(_d[0], dlg) if _d else None
res["dedupe_excl_ck"] = center(dlg.dd_excl, dlg) if dlg.dd_excl else None
res["dedupe_verify_ck"] = center(dlg.dd_verify, dlg) if dlg.dd_verify else None

# v1.25.0（反馈 4）：新页「标签优化」是 tagopt 模块的唯一入口 —— 漏打包 only 在这里炸。
# 页面上的按钮全部按属性取（不按文案匹配），文案改一个字就不会悄悄失配。
dlg._show("标签优化")
app.processEvents()
for _k, _attr in (("tagopt_scan_btn", "btn_to_scan"),
                  ("tagopt_run_btn", "btn_to_run"),
                  ("tagopt_clear_btn", "btn_to_clear"),
                  ("tagopt_path_edit", "to_path"),
                  ("tagopt_lib_combo", "to_lib"),
                  ("tagopt_ai_rb", "rb_to_ai"),
                  ("tagopt_normal_rb", "rb_to_normal")):
    _w = getattr(dlg, _attr, None)
    res[_k] = center(_w, dlg) if _w is not None else None
    if _w is None:
        print(f"[警告] dlg.{_attr} 不存在，标签优化页可能没建出来")
''',
)


# -------------------------------------------------------------- live_verify.py
patch(
    r"dev\live_verify.py",
    "live_verify：首页进截图列表（验反馈 6 芯片）",
    '# 一次最多传 5 个页面名（页面截图编号 18~22，工具窗口固定占 30 起，不会撞号）\nPAGES = ["全部", "智能推荐", "导演库", "合集"]',
    '''# 一次最多传 5 个页面名（页面截图编号 18~22，工具窗口固定占 30 起，不会撞号）
# v1.25.0（反馈 6）：首页排第一 —— 它要拍的是三个快捷筛选芯片被点中后的高亮差异，
# 而「首页」正是 _load() 后唯一会显示芯片的页面。
PAGES = ["首页", "全部", "智能推荐", "导演库", "合集"]''',
)

patch(
    r"dev\live_verify.py",
    "live_verify：夹具 nfo + tagopt 偏好",
    '''    data["insight"] = {"scope": "", "favorites_only": bool(scope_favorites)}
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[临时配置] {dst} insight={data['insight']}", flush=True)
    return dst
''',
    '''    data["insight"] = {"scope": "", "favorites_only": bool(scope_favorites)}
    # v1.25.0（反馈 4）：标签优化页要真按一次「扫描并预览」+「执行写入」才算验过。
    # 写入目标是 %TEMP% 下的**夹具 nfo**，绝不碰用户真实媒体文件。
    fixdir = make_tagopt_fixture()
    data["tagopt"] = {"scope": "folder", "path": fixdir, "library": "",
                      "algo": "normal", "translate": True, "overwrite": False,
                      "complete": True, "backup": True}
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[临时配置] {dst} insight={data['insight']} tagopt={data['tagopt']}",
          flush=True)
    return dst


def make_tagopt_fixture():
    """在 %TEMP%/lmc_live_tagopt/fix 下造 3 个 nfo，供真机验收「标签优化」写入。

    刻意混入：① 日文标签（要能译成中文）② 技术标签 1080p（必须原样保留）
    ③ 片商 / 系列伪标签（要能从 nfo 推断出来）④ 中文标签（不该被动）。
    """
    import xml.etree.ElementTree as ET
    base = os.path.join(os.path.dirname(LOG), "lmc_live_tagopt", "fix")
    os.makedirs(base, exist_ok=True)
    rows = [
        ("ABC-001", "ABC-001 単体作品 巨乳 中出し", ["中出し", "巨乳", "単体作品", "1080p"],
         "冒烟社", "冒烟系列"),
        ("ABC-002", "ABC-002 潮吹き 痴女", ["潮吹き", "痴女", "720p"], "冒烟社", ""),
        ("ABC-003", "ABC-003 3P 顔射 巨乳", ["3P", "顔射", "巨乳", "1080p"], "试作社", ""),
    ]
    for code, title, genres, studio, series in rows:
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = title
        ET.SubElement(root, "plot").text = "真机验收夹具，可随时删除。"
        for g in genres:
            ET.SubElement(root, "genre").text = g
        ET.SubElement(root, "studio").text = studio
        if series:
            st = ET.SubElement(root, "set")
            ET.SubElement(st, "name").text = series
        ET.SubElement(root, "uniqueid", {"type": "tmdb", "default": "true"}).text = "70000"
        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        tree.write(os.path.join(base, code + ".nfo"), encoding="utf-8",
                   xml_declaration=True)
    print(f"[夹具] {base} -> {len(rows)} 个 nfo", flush=True)
    return base
''',
)

patch(
    r"dev\live_verify.py",
    "live_verify：标签优化页真机走查",
    '''            dn3 = coords["dialog_nav"].get("演员刮削")''',
    '''            # 标签优化（v1.25.0 反馈 4）：tagopt 只是 hidden-import，只有打开这一页
            # 并真的跑一次读写才会 import 到它 —— 漏打包就在这里炸。
            dn_to = coords["dialog_nav"].get("标签优化")
            if dn_to:
                nx, ny = dn_to
                print(f"[点击] 工具·标签优化 @({nx},{ny})", flush=True)
                click(dlg, nx, ny)
                time.sleep(2.5)
                out = os.path.join(SHOT_DIR, "36_live_tools_tagopt.png")
                pm = grab(app, dlg)
                print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                      f"{pm.save(out)}", flush=True)

                sb = coords.get("tagopt_scan_btn")
                if sb:
                    print(f"[点击] 扫描并预览 @({sb[0]},{sb[1]})", flush=True)
                    click(dlg, sb[0], sb[1])
                    time.sleep(6.0)
                    out = os.path.join(SHOT_DIR, "37_live_tools_tagopt_scan.png")
                    pm = grab(app, dlg)
                    print(f"  [抓取] {pm.width()}x{pm.height()} -> {os.path.basename(out)} "
                          f"{pm.save(out)}", flush=True)
                    rb = coords.get("tagopt_run_btn")
                    if rb:
                        print(f"[点击] 执行写入 @({rb[0]},{rb[1]})", flush=True)
                        click(dlg, rb[0], rb[1])
                        time.sleep(7.0)
                        out = os.path.join(SHOT_DIR, "38_live_tools_tagopt_run.png")
                        pm = grab(app, dlg)
                        print(f"  [抓取] {pm.width()}x{pm.height()} -> "
                              f"{os.path.basename(out)} {pm.save(out)}", flush=True)
            else:
                print("[跳过] 坐标里没有「标签优化」页（ui_coords 需重跑）", flush=True)

            dn3 = coords["dialog_nav"].get("演员刮削")''',
)

print("\n全部补丁完成。")
