# -*- coding: utf-8 -*-
"""媒体元信息辅助：从文件名/路径推断画质徽章，人类可读的大小与日期。"""
import os
import re
from datetime import datetime


def infer_quality(text: str) -> str:
    """从文件名/路径推断画质徽章，返回逗号分隔字符串，如 '4K,HDR10,Atmos'。"""
    if not text:
        return ""
    t = text.lower()
    badges = []

    # 分辨率
    if re.search(r"(2160p|\b4k\b|uhd)", t):
        badges.append("4K")
    elif "1080p" in t:
        badges.append("1080P")
    elif "720p" in t:
        badges.append("720P")

    # HDR / 杜比视界
    if re.search(r"(dolby[\s._-]*vision|\bdv\b|\b杜比视界\b)", t):
        badges.append("杜比视界")
    elif "hdr10" in t or "hdr" in t:
        badges.append("HDR10")

    # 音频
    if "atmos" in t or "杜比全景声" in t:
        badges.append("Atmos")
    if re.search(r"(truehd|dts[\s._-]*hd|dts[\s._-]*x)", t):
        badges.append("DTS:X" if re.search(r"dts[\s._-]*x", t) else "TrueHD")

    # 去重保序
    seen, out = set(), []
    for b in badges:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return ",".join(out)


# 本地图片候选名（海报 / 背景）
_POSTER_NAMES = ["poster.jpg", "poster.png", "poster.jpeg", "folder.jpg", "folder.png",
                 "cover.jpg", "cover.png", "thumb.jpg", "thumb.png", "海报.jpg", "封面.jpg"]
_FANART_NAMES = ["fanart.jpg", "fanart.png", "backdrop.jpg", "backdrop.png",
                 "background.jpg", "background.png", "背景.jpg"]
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def find_local_images(folder: str, base: str = None):
    """在 folder 中查找本地海报 / 背景图。返回 (poster, fanart)，可能为 None。

    优先级：与视频同名的图(如 影片名.jpg / 影片名-poster.jpg) > 通用名(poster.jpg/fanart.jpg)。
    """
    poster = None
    fanart = None
    if not folder or not os.path.isdir(folder):
        return poster, fanart

    # 1) 与视频/目录同名的图片
    if base:
        stem = os.path.splitext(os.path.basename(base))[0]
        cands = [
            (stem + ".jpg", "poster"), (stem + ".png", "poster"),
            (stem + "-poster.jpg", "poster"), (stem + "-poster.png", "poster"),
            (stem + "-thumb.jpg", "poster"), (stem + "-thumb.png", "poster"),
            (stem + ".poster.jpg", "poster"),
            (stem + "-fanart.jpg", "fanart"), (stem + "-fanart.png", "fanart"),
            (stem + "-backdrop.jpg", "fanart"), (stem + ".fanart.jpg", "fanart"),
        ]
        for fn, kind in cands:
            p = os.path.join(folder, fn)
            if os.path.exists(p):
                if kind == "fanart" and not fanart:
                    fanart = p
                elif kind == "poster" and not poster:
                    poster = p

    # 2) 通用命名
    if not poster:
        for n in _POSTER_NAMES:
            p = os.path.join(folder, n)
            if os.path.exists(p):
                poster = p
                break
    if not fanart:
        for n in _FANART_NAMES:
            p = os.path.join(folder, n)
            if os.path.exists(p):
                fanart = p
                break
    return poster, fanart


def find_local_images_near(video_path: str):
    """先找视频所在目录，再找上一级目录（合辑/剧集根常把图片放上层）。"""
    if not video_path:
        return None, None
    folder = os.path.dirname(video_path)
    base = os.path.basename(video_path)
    poster, fanart = find_local_images(folder, base)
    if not poster or not fanart:
        parent = os.path.dirname(folder)
        if parent and parent != folder:
            p2, f2 = find_local_images(parent)
            poster = poster or p2
            fanart = fanart or f2
    return poster, fanart


def runtime_minutes(runtime) -> str:
    """把 'HH:MM:SS' / 'HH:MM' 转成分钟数字符串。"""
    if not runtime:
        return "—"
    try:
        parts = str(runtime).split(":")
        if len(parts) == 3:
            h, m = int(parts[0]), int(parts[1])
        elif len(parts) == 2:
            h, m = int(parts[0]), int(parts[1])
        else:
            return str(runtime)
        return str(h * 60 + m)
    except (TypeError, ValueError):
        return str(runtime)


_KIND_CN = {"movie": "电影", "tvshow": "剧集", "episode": "分集"}


def kind_cn(kind: str) -> str:
    return _KIND_CN.get(kind or "", "")


def human_size(num) -> str:
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.2f} {unit}"
        num /= 1024
    return f"{num:.2f} TB"


def file_added_date(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")
