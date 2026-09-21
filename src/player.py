# -*- coding: utf-8 -*-
"""
本地播放器直接调用
====================
解决 Emby 必须网页播放的痛点：点击播放时直接调用本地播放器打开视频文件，
全程不启动任何 Web 服务 / 浏览器。
优先顺序：用户设定的播放器 -> 常见播放器(vlc/mpv/potplayer) -> 系统默认关联。
"""
import os
import shutil
import subprocess
import sys


def _candidate_players():
    names = ["vlc", "mpv", "potplayer", "mpc-hc", "mpc-be", "smplayer", "kmplayer"]
    found = []
    for n in names:
        p = shutil.which(n)
        if p:
            found.append(p)
    # Windows 常见安装路径
    if sys.platform.startswith("win"):
        prog = os.environ.get("ProgramFiles", "C:\\Program Files")
        progx = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        extras = [
            os.path.join(prog, "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(progx, "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(prog, "MPC-HC", "mpc-hc.exe"),
            os.path.join(progx, "DAUM", "PotPlayer", "PotPlayerMini64.exe"),
        ]
        for e in extras:
            if os.path.exists(e):
                found.append(e)
    # 去重保序
    seen = set()
    out = []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def launch(file_path: str, player_path: str = None) -> dict:
    """打开视频文件。返回 {ok, msg}。"""
    if not file_path or not os.path.exists(file_path):
        return {"ok": False, "msg": f"文件不存在: {file_path}"}

    players = []
    if player_path:
        players.append(player_path)
    players.extend(_candidate_players())

    # 1) 指定/常见播放器
    for p in players:
        try:
            subprocess.Popen([p, file_path], shell=False)
            return {"ok": True, "msg": f"已用 {os.path.basename(p)} 打开: {file_path}"}
        except Exception:
            continue

    # 2) 系统默认关联程序(Windows os.startfile / 其他平台 open/xdg-open)
    try:
        if sys.platform.startswith("win"):
            os.startfile(file_path)  # noqa: F821 (Windows only)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])
        return {"ok": True, "msg": f"已用系统默认程序打开: {file_path}"}
    except Exception as e:
        return {"ok": False, "msg": f"无法打开播放器: {e}"}


def reveal_in_explorer(file_path: str) -> dict:
    """在资源管理器中定位文件。"""
    if not file_path or not os.path.exists(file_path):
        return {"ok": False, "msg": "文件不存在"}
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(file_path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", file_path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(file_path)])
        return {"ok": True, "msg": "已在资源管理器中打开"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
