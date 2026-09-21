# -*- coding: utf-8 -*-
"""媒体库扫描器：递归扫描目录，读取已刮削的 nfo，并索引裸视频文件/子文件。

v1.5.0 增强：
- nfo 读取：除 movie.nfo / tvshow.nfo 外，识别与视频同名的 <名称>.nfo（tinyMediaManager 单项刮削），
  以及 <文件夹名>.nfo；解析 year / 评分(嵌套 ratings) / 用户评分 / 上映日期 / 时长 / 分级 / 类型 /
  制片 / 演员 / 流分辨率画质。
- 扫描模式：new(仅新增与修改) / fill(仅补充缺失) / overwrite(全量覆盖)。
- 标题读取：从文件名推断时清理【】/{}、年份、以及 DoVi/HDR/WEB-DL 等发行标签；剧集识别 SxxExx。
- 照片读取：为 nfo 缺失封面的条目、以及裸视频文件自动查找同目录/上层的
  poster.jpg / fanart.jpg / 同名图片，写入 poster / fanart。
- 子文件：季目录下的裸视频按「分集」入库(识别 SxxExx / 第N集)，不再被误当成顶层电影。
- 去重：按 file_path upsert；nfo 文件夹及其子树不再重复索引裸视频。
"""
import os
import re
from typing import Callable, Optional

import database as db
import nfo_parser as nfo
import media_meta as mm

VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv",
              ".flv", ".iso", ".rmvb", ".m4v", ".webm", ".mpg", ".mpeg")

# 文件名中需要剔除的发行 / 编码 / 音轨标签（小写）
_TAG_WORDS = {
    "2160p", "1080p", "1080i", "720p", "576p", "480p", "4k", "8k", "uhd", "fhd", "hd", "sd",
    "hdr", "hdr10", "hdr10+", "hdr10plus", "dv", "dovi", "dolby", "vision", "sdr",
    "atmos", "truehd", "true-hd", "dts", "dtsx", "dts-hd", "dtshd", "dd", "ddp", "dd+",
    "eac3", "ac3", "aac", "flac", "mp3", "opus",
    "remux", "bluray", "blu-ray", "bd", "web", "web-dl", "webdl", "webrip", "web-rip",
    "bdrip", "brrip", "dvdrip", "hdtv", "pdtv", "hdrip", "hdvd", "dvd",
    "x264", "x265", "h264", "h265", "hevc", "avc", "av1", "10bit", "8bit", "hi10p",
    "60fps", "50fps", "24fps", "25fps", "30fps",
    "repack", "proper", "internal", "multi", "complete", "batch", "remastered",
    "extended", "unrated", "imax", "hq", "rarbg", "yts", "yify", "ntb", "cmct", "hdchina",
    "chs", "cht", "gb", "big5", "简繁", "简中", "繁中", "中字", "中文字幕", "内嵌", "内嵌字幕",
    "外挂", "外挂字幕", "国语", "粤语", "未知演员", "unknown", "无码", "有码", "hd",
    "mp4", "mkv", "avi", "m2ts", "mov", "wmv", "flv", "iso", "rmvb", "m4v", "webm",
}

_TAG_RE = re.compile(
    r"(?i)^(dd|ddp|aac|ac3|eac3|dts|truehd|atmos|flac|mp3|opus)\d?(\.\d)?$|^\d{3,4}p$"
)


def _find_video(folder: str, base_name: Optional[str] = None) -> Optional[str]:
    """在 folder 中找到视频文件；base_name 给定时优先同名文件。"""
    best = None
    best_size = -1
    try:
        entries = os.listdir(folder)
    except OSError:
        return None
    for f in entries:
        low = f.lower()
        if not low.endswith(VIDEO_EXTS):
            continue
        full = os.path.join(folder, f)
        if base_name:
            if os.path.splitext(f)[0].lower() == os.path.splitext(base_name)[0].lower():
                return full
        try:
            size = os.path.getsize(full)
        except OSError:
            continue
        if size > best_size:
            best_size = size
            best = full
    return best


def _lib_value(root: str, library_name: Optional[str]) -> str:
    return library_name or root


def _under(path: str, dirs: set) -> bool:
    """path 是否等于 dirs 中某个目录，或位于其子树内。"""
    return any(path == d or path.startswith(d + os.sep) for d in dirs)


def _link_actors(media_id: int, actors: list):
    db.clear_media_people(media_id)
    for i, a in enumerate(actors):
        pid = db.upsert_person(a["name"], a.get("type", "Actor"), a.get("thumb"))
        db.link_media_person(media_id, pid, a.get("role", ""), i)


def backfill_people_links(limit: int = 1500, progress: Callable[[str], None] = None) -> dict:
    """按 nfo 补写 media_people 关联（演员 + 导演），幂等。

    v1.11.0：真机索引库实测 `role_type='Director'` 关联数为 0（旧版扫描器还没把
    <director> 关联进 media_people），于是影片卡的「导演」小字永远为空。
    这里重新读各媒体 nfo 解析演员+导演并补齐关联；与现有内容完全一致则跳过写入，
    因此可以在启动时反复安全调用（有变更才落库）。
    """
    counts = {"media": 0, "people": 0, "skipped": 0, "failed": 0}
    for m in db.media_with_nfo(limit=limit):
        nfo_path = m.get("nfo_path")
        if not nfo_path or not os.path.exists(nfo_path):
            continue
        try:
            info = nfo.parse_any(nfo_path)
        except Exception:
            counts["failed"] += 1
            continue
        actors = info.get("actors") or []
        directors = info.get("directors") or []
        if not actors and not directors:
            continue
        people = actors + [dict(d, type="Director") for d in directors]
        want = [(p.get("name") or "", p.get("type") or "Actor") for p in people]
        if want == db.media_people_roles(m["id"]):
            counts["skipped"] += 1
            continue
        _link_actors(m["id"], people)
        counts["media"] += 1
        counts["people"] += len(people)
        if progress and directors:
            progress(f"关联回填：{info.get('title') or nfo_path}")
    return counts


def scan_library(root: str, progress: Callable[[str], None] = None,
                 library_name: Optional[str] = None, mode: str = "overwrite") -> dict:
    """扫描一个媒体库根目录，返回统计。library_name 给定时 media.library=库名。

    mode: new(仅新增与修改) / fill(仅补充缺失) / overwrite(全量覆盖，默认)。
    """
    root = os.path.abspath(root)
    counts = {"movie": 0, "tvshow": 0, "episode": 0}
    nfo_dirs = set()

    # 第一遍：处理含 nfo 的文件夹（电影 / 剧集 / 同名单项 nfo）
    for dirpath, dirnames, filenames in os.walk(root):
        lower = {f.lower(): f for f in filenames}
        if "movie.nfo" in lower:
            nfo_dirs.add(dirpath)
            _do_movie(dirpath, root, counts, progress, library_name, mode)
            continue
        if "tvshow.nfo" in lower:
            nfo_dirs.add(dirpath)
            _do_tvshow(dirpath, root, counts, progress, library_name, mode, nfo_dirs)
            continue
        if _under(dirpath, nfo_dirs):
            continue
        # 同名 nfo / 文件夹名 nfo（tinyMediaManager 单项刮削）
        vids = [f for f in filenames if f.lower().endswith(VIDEO_EXTS)]
        if vids:
            folder_nfo = lower.get(os.path.basename(dirpath).lower() + ".nfo")
            for v in vids:
                stem = os.path.splitext(v)[0].lower()
                nf = lower.get(stem + ".nfo") or folder_nfo
                if nf is None:
                    # 选集基名 nfo：SAVR-1144-8K-cd1.mp4 -> SAVR-1144-8K.nfo
                    # （v1.19.0 反馈 99：多 CD 选集的 nfo 以基名命名，分片名匹配不到）
                    base = _cd_base_stem(stem)
                    if base != stem:
                        nf = lower.get(base + ".nfo")
                if nf:
                    nfo_dirs.add(dirpath)
                    # v1.19.0 反馈 99：多 CD 选集的 nfo 以「选集基名」命名，覆盖整个文件夹。
                    # 必须把文件夹内所有分片都按该 nfo 索引，才能归组成「选集」且每个分片都带元数据；
                    # 否则只索引首个分片、其余被跳过，选集归组失败、信息反而更少。
                    is_cd_set = (len(vids) >= 2
                                 and any(_cd_number(os.path.splitext(x)[0]) is not None
                                         for x in vids))
                    if is_cd_set:
                        for vv in vids:
                            info = nfo.parse_movie(os.path.join(dirpath, nf))
                            _index_movie(info, os.path.join(dirpath, vv), dirpath,
                                         root, counts, progress, library_name, mode)
                    else:
                        _do_same_nfo(dirpath, nf, v, root, counts, progress, library_name, mode)
                    break

    # 第二遍：索引裸视频文件 / 子文件（跳过 nfo 文件夹及其子树）
    for dirpath, dirnames, filenames in os.walk(root):
        if _under(dirpath, nfo_dirs):
            continue
        for f in filenames:
            if f.lower().endswith(VIDEO_EXTS):
                _do_bare_video(os.path.join(dirpath, f), root, counts, progress,
                               library_name, mode)

    # v1.15.0：把 cd1…cdN 连续序号的视频归组为「一部 + 选集」（不动磁盘）
    try:
        counts["grouped"] = group_cd_sets(root)
    except Exception as e:
        if progress:
            progress(f"[归组出错] {e}")

    return counts


def _finalize_movie(info: dict, video: str, folder: str, root: str,
                    library_name, mode: str) -> dict:
    """补齐文件相关字段（路径/大小/日期/画质/本地封面）。"""
    info["file_path"] = video
    info["library"] = _lib_value(root, library_name)
    info["sort_title"] = (info.get("sort_title") or info.get("title") or "").lower()
    try:
        info["file_size"] = os.path.getsize(video)
        info["file_mtime"] = os.path.getmtime(video)
    except OSError:
        info["file_size"] = None
        info["file_mtime"] = None
    info["added_date"] = mm.file_added_date(video)
    q = mm.infer_quality(video)
    res = info.pop("resolution", "") or ""
    if res and res not in q:
        q = (res + "," + q).strip(",")
    info["quality"] = q
    if not info.get("poster") or not info.get("fanart"):
        p, fa = mm.find_local_images(folder, os.path.basename(video))
        info["poster"] = info.get("poster") or p
        info["fanart"] = info.get("fanart") or fa
    info.pop("nfo_dir", None)
    info.setdefault("thumb", None)
    info.setdefault("premiere", None)
    info.setdefault("user_rating", None)
    return info


def _index_movie(info: dict, video: str, folder: str, root: str, counts: dict,
                 progress, library_name, mode: str, label: str = "电影"):
    info = _finalize_movie(info, video, folder, root, library_name, mode)
    actors = info.pop("actors", [])
    directors = info.pop("directors", [])
    people = actors + [dict(d, type="Director") for d in directors]
    was_new = db.media_id_by_path(video) is None
    mid = db.upsert_media_by_path(mode=mode, **info)
    if mid and people:
        _link_actors(mid, people)
    if was_new:
        counts["movie"] += 1
        if progress:
            progress(f"{label}：{info['title']} ({info.get('year') or '?'})")


def _do_movie(folder: str, root: str, counts: dict, progress, library_name=None,
              mode: str = "overwrite"):
    try:
        info = nfo.parse_movie(os.path.join(folder, "movie.nfo"))
        video = _find_video(folder)
        if not video:
            return
        _index_movie(info, video, folder, root, counts, progress, library_name, mode)
    except Exception as e:
        # nfo 损坏时回退：仍按裸视频索引，避免文件丢失
        video = _find_video(folder)
        if progress:
            progress(f"[nfo解析失败，回退] {folder}: {e}")
        if video:
            _do_bare_video(video, root, counts, progress, library_name, mode)


def _do_same_nfo(folder: str, nfo_name: str, video_name: str, root: str, counts: dict,
                 progress, library_name=None, mode: str = "overwrite"):
    """与视频同名的单项 nfo（如 390JAC-240.nfo + 390JAC-240.mp4）。"""
    video = os.path.join(folder, video_name)
    try:
        info = nfo.parse_movie(os.path.join(folder, nfo_name))
        _index_movie(info, video, folder, root, counts, progress, library_name, mode)
    except Exception as e:
        # nfo 损坏时回退：仍按裸视频索引，避免文件丢失
        if progress:
            progress(f"[nfo解析失败，回退] {folder}/{nfo_name}: {e}")
        _do_bare_video(video, root, counts, progress, library_name, mode)


def _do_tvshow(folder: str, root: str, counts: dict, progress, library_name=None,
               mode: str = "overwrite", nfo_dirs: set = None):
    nfo_path = os.path.join(folder, "tvshow.nfo")
    sid = None
    try:
        info = nfo.parse_tvshow(nfo_path)
        info["library"] = _lib_value(root, library_name)
        info["sort_title"] = (info["sort_title"] or info["title"]).lower()
        info["quality"] = mm.infer_quality(os.path.basename(folder))
        info["added_date"] = mm.file_added_date(nfo_path)
        try:
            info["file_mtime"] = os.path.getmtime(nfo_path)
        except OSError:
            info["file_mtime"] = None
        if not info.get("poster") or not info.get("fanart"):
            p, fa = mm.find_local_images(folder)
            info["poster"] = info.get("poster") or p
            info["fanart"] = info.get("fanart") or fa
        info.pop("nfo_dir", None)
        info.pop("resolution", None)
        info.setdefault("premiere", None)
        info.setdefault("user_rating", None)
        actors = info.pop("actors", [])
        directors = info.pop("directors", [])
        people = actors + [dict(d, type="Director") for d in directors]
        was_new = db.media_id_by_path(nfo_path) is None
        sid = db.upsert_media_by_path(mode=mode, **info)
        if sid and people:
            _link_actors(sid, people)
        if was_new:
            counts["tvshow"] += 1
            if progress:
                progress(f"剧集：{info['title']} ({info.get('year') or '?'})")
    except Exception as e:
        if progress:
            progress(f"[跳过] {folder}: {e}")
        return

    # 扫描季目录
    try:
        entries = os.listdir(folder)
    except OSError:
        return
    for season in entries:
        sp = os.path.join(folder, season)
        if not os.path.isdir(sp) or not re_season(season):
            continue
        if nfo_dirs is not None:
            nfo_dirs.add(sp)
        try:
            nfo_files = [f for f in os.listdir(sp) if f.lower().endswith(".nfo")
                         and f.lower() != "tvshow.nfo"]
        except OSError:
            continue
        handled = set()
        # 1) 分集 nfo
        for f in nfo_files:
            try:
                ep = nfo.parse_episode(os.path.join(sp, f),
                                       parent_title=info["title"], parent_id=sid)
                video = _find_video(sp, f)
                if not video:
                    continue
                handled.add(os.path.basename(video).lower())
                ep["file_path"] = video
                ep["library"] = _lib_value(root, library_name)
                try:
                    ep["file_size"] = os.path.getsize(video)
                    ep["file_mtime"] = os.path.getmtime(video)
                except OSError:
                    ep["file_size"] = None
                    ep["file_mtime"] = None
                ep["added_date"] = mm.file_added_date(video)
                ep["quality"] = mm.infer_quality(video)
                if not ep.get("poster"):
                    p, _ = mm.find_local_images(sp, os.path.basename(video))
                    ep["poster"] = p
                ep.pop("nfo_dir", None)
                ep.pop("parent_title", None)
                ea = ep.pop("actors", [])
                ed = ep.pop("directors", [])
                people_e = ea + [dict(d, type="Director") for d in ed]
                was_new = db.media_id_by_path(video) is None
                eid = db.upsert_media_by_path(mode=mode, **ep)
                if eid and people_e:
                    _link_actors(eid, people_e)
                if was_new:
                    counts["episode"] += 1
            except Exception as e:
                if progress:
                    progress(f"[跳过分集] {f}: {e}")
        # 2) 季目录下的裸视频（无同名 nfo）→ 按分集入库
        try:
            season_files = os.listdir(sp)
        except OSError:
            continue
        for f in season_files:
            if not f.lower().endswith(VIDEO_EXTS) or f.lower() in handled:
                continue
            if any(os.path.splitext(nf)[0].lower() == os.path.splitext(f)[0].lower()
                   for nf in nfo_files):
                continue
            _do_bare_episode(os.path.join(sp, f), sid, info["title"], sp, folder,
                             root, counts, progress, library_name, mode)


def _do_bare_episode(video: str, parent_id, parent_title: str, season_dir: str,
                     show_dir: str, root: str, counts: dict, progress,
                     library_name=None, mode: str = "overwrite"):
    """季目录下的裸视频文件：识别 SxxExx / 第N集，按分集入库。"""
    try:
        season, episode, title = _infer_episode(os.path.basename(video))
        poster, fanart = mm.find_local_images(season_dir, os.path.basename(video))
        if not poster:
            poster, _ = mm.find_local_images(show_dir)
        info = {
            "kind": "episode",
            "title": title,
            "sort_title": (title or "").lower(),
            "year": None,
            "plot": None,
            "rating": None,
            "user_rating": None,
            "premiere": None,
            "poster": poster,
            "fanart": fanart,
            "thumb": None,
            "file_path": video,
            "nfo_path": None,
            "library": _lib_value(root, library_name),
            "genres": "",
            "season": season,
            "episode": episode,
            "parent_id": parent_id,
            "runtime": None,
            "country": None,
            "studio": None,
            "file_size": os.path.getsize(video),
            "file_mtime": os.path.getmtime(video),
            "quality": mm.infer_quality(video),
            "tmdb_id": None,
            "certification": None,
            "collection": None,
            "added_date": mm.file_added_date(video),
            "favorite": 0,
            "play_count": 0,
            "last_played": None,
        }
        was_new = db.media_id_by_path(video) is None
        db.upsert_media_by_path(mode=mode, **info)
        if was_new:
            counts["episode"] += 1
            if progress:
                tag = f"S{season:02d}E{episode:02d}" if season and episode else "分集"
                progress(f"分集：{parent_title} · {tag} {title}")
    except Exception as e:
        if progress:
            progress(f"[跳过分集] {video}: {e}")


def _do_bare_video(path: str, root: str, counts: dict, progress, library_name=None,
                   mode: str = "overwrite"):
    """索引一个裸视频文件：从文件名推断片名 / 年份 / 画质，并查找本地封面。"""
    try:
        title, year = _infer_title_year(os.path.basename(path))
        poster, fanart = mm.find_local_images_near(path)
        info = {
            "kind": "movie",
            "title": title,
            "sort_title": title.lower(),
            "year": year,
            "plot": None,
            "rating": None,
            "user_rating": None,
            "premiere": None,
            "poster": poster,
            "fanart": fanart,
            "thumb": None,
            "file_path": path,
            "nfo_path": None,
            "library": _lib_value(root, library_name),
            "genres": "",
            "season": None,
            "episode": None,
            "parent_id": None,
            "runtime": None,
            "country": None,
            "studio": None,
            "file_size": os.path.getsize(path),
            "file_mtime": os.path.getmtime(path),
            "quality": mm.infer_quality(path),
            "tmdb_id": None,
            "certification": None,
            "collection": None,
            "added_date": mm.file_added_date(path),
            "favorite": 0,
            "play_count": 0,
            "last_played": None,
        }
        was_new = db.media_id_by_path(path) is None
        db.upsert_media_by_path(mode=mode, **info)
        if was_new:
            counts["movie"] += 1
            if progress:
                progress(f"视频：{title} ({year or '?'})")
    except Exception as e:
        if progress:
            progress(f"[跳过] {path}: {e}")


def _infer_title_year(name: str):
    """从文件名 / 名称推断片名与年份，清理发行标签。"""
    base = os.path.splitext(os.path.basename(name))[0]
    # 先从未处理的原始名中提取年份（避免被后续括号剔除误删，例如 (2022)）
    year = None
    my = re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", base)
    if my:
        year = int(my.group(0))
    # 去掉括号内容（含中文【】、[]、()、{}），含其中的年份标签一起清掉
    clean = re.sub(r"【[^】]*】|\[[^\]]*\]|\([^)]*\)|\{[^}]*\}", " ", base)
    clean = re.sub(r"[._\-]+", " ", clean)
    tokens = []
    for t in clean.split():
        tl = t.lower().strip()
        if not tl:
            continue
        if tl in _TAG_WORDS or _TAG_RE.match(tl):
            continue
        tokens.append(t)
    title = " ".join(tokens).strip(" -_·")
    return (title or base), year


def _infer_episode(stem: str):
    """从分集文件名推断 (season, episode, title)。"""
    season = episode = None
    rest = stem
    m = re.search(r"[sS](\d{1,2})\s*[eE](\d{1,3})", stem)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        rest = (stem[:m.start()] + " " + stem[m.end():])
    else:
        m = re.search(r"(?:第|EP|EPISODE|E)\s*(\d{1,3})\s*[集话話]?", stem, re.IGNORECASE)
        if m:
            episode = int(m.group(1))
            rest = (stem[:m.start()] + " " + stem[m.end():])
    title, _ = _infer_title_year(rest)
    if not title or re.fullmatch(r"(?i)[sE]?\d{0,3}[eE]?\d{0,3}", title or ""):
        if season is not None and episode is not None:
            title = f"S{season:02d}E{episode:02d}"
        else:
            title = title or stem
    return season, episode, title


def re_season(name: str):
    return re.match(r"season\s*\d+|^s\d{1,2}$|^\d{1,2}(季|期)$", name, re.IGNORECASE) is not None


# ---------------- v1.15.0：CD 连续序号自动归类（选集） ----------------

# 识别文件名里的「cd1 / cd2 / … / cd12」，分隔符允许 - _ . 与空格
_CD_RE = re.compile(r"(?i)[-_. 　]cd\s*[-_.]?\s*(\d{1,2})$")


def _cd_number(stem: str):
    """从文件名 stem 取 cd 序号；不是分片返回 None。"""
    m = _CD_RE.search(stem)
    return int(m.group(1)) if m else None


def _cd_base_stem(stem: str) -> str:
    """对 `<基名>-cdN` 形式的视频名，返回去掉 cd 后缀的基名（如 savr-1144-8k-cd1 -> savr-1144-8k）。

    tinyMediaManager 把多 CD 选集的 nfo 命名为「选集基名」`<基名>.nfo`（而非每个分片同名 nfo），
    分片视频为 `<基名>-cd1.mp4`。扫描时按分片名找不到 nfo，需回退到基名 nfo 才能带上标题/年份/
    演员等元数据，否则「有选集的资源」在首页/详情页信息为空、反而比单集还少。
    """
    m = _CD_RE.search(stem)
    return stem[:m.start()] if m else stem


def _clean_cd_title(title: str, cd: int) -> str:
    """去掉片名末尾的「 CD5」这类分片标记，让归组后的标题干净。"""
    t = re.sub(r"(?i)[-_. 　]?cd\s*\d{1,2}\s*$", " ", title or "").strip()
    return re.sub(r"\s{2,}", " ", t)


def group_cd_sets(root: str) -> int:
    """把同一目录下 cd1…cdN 连续序号的视频归组为「一部 + 选集」。

    归组单位 = 目录（实测所有多分片集均单目录，无跨目录）。
    代表 = 名称排序最靠前的分片（其 nfo 的标题/海报/简介作为整个选集对外展示信息）；
    幂等：每轮先清空本目录内的旧分组，再重新归组 —— 文件被删后重扫能自动拆回独立影片。
    不动磁盘。返回本轮改动（写入/重置）的记录数。
    """
    root = os.path.abspath(root)
    rows = db.media_for_prune(root=root)
    by_dir = {}
    for r in rows:
        by_dir.setdefault(os.path.dirname(r["file_path"]), []).append(r)

    changed = 0
    for d, group in by_dir.items():
        # 复位本目录内所有旧分组（含被删文件导致的孤儿分片），保证幂等
        for r in group:
            if r.get("parent_id") is not None:
                db.update_media_fields(r["id"], parent_id=None, season=None, episode=None)
                changed += 1
        cds = []
        for r in group:
            fp = r.get("file_path")
            if not fp or not os.path.exists(fp):
                continue
            n = _cd_number(os.path.splitext(os.path.basename(fp))[0])
            if n is not None:
                cds.append((r, n))
        if len(cds) < 2:
            continue
        # v1.18.0（反馈 96）：代表取「名称排序最靠前」的 nfo，而非 cd 号最小者
        cds.sort(key=lambda x: os.path.basename(x[0].get("file_path") or ""))
        rep_r, rep_cd = cds[0]
        # 代表尽量带上海报：自己没有就用兄弟分片的
        poster = rep_r.get("poster")
        if not poster:
            for r, _ in cds[1:]:
                if r.get("poster"):
                    poster = r["poster"]
                    break
        title = _clean_cd_title(rep_r.get("title") or "", rep_cd)
        db.update_media_fields(rep_r["id"], parent_id=None, season=None,
                               episode=rep_cd, poster=poster or None,
                               title=title or None)
        for r, cd in cds[1:]:
            db.update_media_fields(r["id"], parent_id=rep_r["id"], season=None, episode=cd)
        changed += len(cds)
    return changed


def prune_missing(library_name: Optional[str] = None, roots: Optional[list] = None,
                  progress: Callable[[str], None] = None) -> dict:
    """「扫描并删除失效的」：删掉索引里、但磁盘文件已不存在的记录（不动磁盘文件）。

    返回 {"removed": n}。删除后对每个目录重新归组，让失去代表的孤儿分片重新回到影片墙。
    """
    rows = db.media_for_prune(library=library_name)
    removed = 0
    for r in rows:
        fp = r.get("file_path")
        if fp and not os.path.exists(fp):
            db.delete_media(r["id"])
            removed += 1
            if progress and removed % 50 == 0:
                progress(f"已删除 {removed} 条失效记录…")
    for p in (roots or []):
        if p and os.path.isdir(p):
            group_cd_sets(p)
    return {"removed": removed}


# ---------- 单片重扫（v1.20.0：详情页「刷新」按钮） ----------
def _resolve_nfo_for(row: dict) -> Optional[str]:
    """为一个已入库的记录定位它的 nfo（用于单片重扫）。

    查找顺序（与整库扫描一致，逐条取第一个存在的）：
      记录里的 nfo_path → 同目录 `<视频名>.nfo` → `<CD 基名>.nfo` → `<文件夹名>.nfo` → movie.nfo → tvshow.nfo
    """
    p = row.get("nfo_path")
    if p and os.path.exists(p):
        return p
    fp = row.get("file_path") or ""
    folder = os.path.dirname(fp) if fp else None
    if not folder or not os.path.isdir(folder):
        return None
    stem = os.path.splitext(os.path.basename(fp))[0].lower() if fp else ""
    folder_name = os.path.basename(os.path.normpath(folder)).lower()
    cands = []
    if stem:
        cands.append(stem + ".nfo")
        base = _cd_base_stem(stem)
        if base != stem:
            cands.append(base + ".nfo")
    if folder_name:
        cands.append(folder_name + ".nfo")
    cands += ["movie.nfo", "tvshow.nfo"]
    try:
        # 用真实文件名大小写匹配（索引里可能存的是小写）
        entries = {e.lower(): e for e in os.listdir(folder)}
    except OSError:
        return None
    for c in cands:
        real = entries.get(c.lower())
        if real:
            full = os.path.join(folder, real)
            if os.path.isfile(full):
                return full
    return None


def rescan_one(media_id: int) -> dict:
    """对「单部影片」重新读取其 nfo 并回写数据库（详情页「刷新」按钮，v1.20.0）。

    与整库扫描的区别：
      - 只处理这一条记录，不遍历目录、不重扫其他片；
      - **保留用户态字段**：`favorite` / `play_count` 不参与覆盖（它们本就不在 nfo 字段里）；
        `user_rating` 在 nfo 未写 `<userrating>` 时保留库中已有的值，不会被清空；
      - 结构字段（kind / parent_id / season / episode）一律沿用原记录，避免把分集/选集打散。

    返回 {"ok": bool, "msg": str, "title": str}。
    """
    row = db.get_media(media_id)
    if not row:
        return {"ok": False, "msg": "索引中找不到该记录，可能已被移除"}
    nfo_path = _resolve_nfo_for(row)
    if not nfo_path:
        return {"ok": False,
                "msg": "未找到对应的 nfo 文件\n（已尝试：记录中的 nfo、同名 nfo、CD 基名 nfo、文件夹名 nfo、movie.nfo）"}
    try:
        info = nfo.parse_any(nfo_path)
    except Exception as e:
        return {"ok": False, "msg": f"nfo 解析失败：{e}"}
    if not info:
        return {"ok": False, "msg": "nfo 解析失败：文件可能已损坏或不是有效的影片信息"}

    # 结构字段沿用原记录（parse_episode 会把 parent_id 置空，直接写回会把分集打散）
    kind = (row.get("kind") or info.get("kind") or "movie").lower()
    info["kind"] = kind
    if kind == "episode":
        info.pop("parent_title", None)
        info["parent_id"] = row.get("parent_id")
        info["season"] = row.get("season")
        info["episode"] = row.get("episode")
    else:
        info.pop("parent_title", None)
        info.pop("season", None)
        info.pop("episode", None)
        info["parent_id"] = row.get("parent_id")

    # 用户评分：nfo 里没有就保留库中已有的（不被清空）
    if info.get("user_rating") is None and row.get("user_rating") is not None:
        info["user_rating"] = row.get("user_rating")

    file_path = row.get("file_path")
    folder = os.path.dirname(file_path) if file_path else os.path.dirname(nfo_path)
    try:
        _index_movie(info, file_path, folder, folder,
                     {"movie": 0, "tvshow": 0, "episode": 0},
                     None, row.get("library"), "overwrite")
    except Exception as e:
        return {"ok": False, "msg": f"写入数据库失败：{e}"}
    return {"ok": True, "msg": "已重新读取 nfo", "title": info.get("title") or ""}
