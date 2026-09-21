# -*- coding: utf-8 -*-
"""运行日志（v1.13.0 新增）
=========================
把软件的**全部运行记录**写到 `<exe 同级>/index_data/logs/app.log`，便于出 BUG 时排查。

- 纯标准库（logging 轮转文件处理器），不依赖网络/浏览器。
- 任何写日志失败都不得影响主流程 —— 全部 try/except 兜底。
- 通过 `setup()` 在启动时安装，`log(msg)` 记一条；`export_logs(zip)` 打包导出。
"""
import os
import sys
import zipfile
import logging
from logging.handlers import RotatingFileHandler

_LOG_DIR_NAME = ("index_data", "logs")
_LOG_FILE = "app.log"
_logger = None


def base_dir() -> str:
    """数据根目录：打包后在 exe 同级，开发期在项目根（与 database.db_path 一致）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log_dir() -> str:
    d = os.path.join(base_dir(), *_LOG_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def log_path() -> str:
    return os.path.join(log_dir(), _LOG_FILE)


def setup() -> logging.Logger:
    """初始化（幂等）。返回 logger。"""
    global _logger
    if _logger is not None:
        return _logger
    lg = logging.getLogger("lmc")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    try:
        h = RotatingFileHandler(log_path(), maxBytes=2 * 1024 * 1024,
                                backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg.addHandler(h)
    except Exception:
        try:
            lg.addHandler(logging.NullHandler())
        except Exception:
            pass
    _logger = lg
    return lg


def log(msg, level: str = "info"):
    """记一条日志；任何异常都吞掉，绝不影响主流程。"""
    try:
        lg = setup()
        fn = getattr(lg, level, None) or lg.info
        fn(str(msg))
    except Exception:
        pass


def install_excepthook():
    """把未捕获异常写进日志（打包后没有控制台，这是唯一的现场）。"""
    def _hook(exc_type, exc, tb):
        try:
            import traceback
            log("未捕获异常:\n" + "".join(
                traceback.format_exception(exc_type, exc, tb)), "error")
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)
    try:
        sys.excepthook = _hook
    except Exception:
        pass


def log_files() -> list:
    """当前目录下的所有日志文件（含轮转备份），按修改时间倒序。"""
    try:
        d = log_dir()
        fs = [os.path.join(d, f) for f in os.listdir(d)
              if os.path.isfile(os.path.join(d, f))]
        return sorted(fs, key=os.path.getmtime, reverse=True)
    except Exception:
        return []


def export_logs(dest_zip: str) -> dict:
    """把日志目录打包成一个 zip，便于发给开发者排查。返回 {'ok','count','path'/'error'}。"""
    try:
        fs = log_files()
        if not fs:
            return {"ok": False, "error": "暂无日志文件"}
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for f in fs:
                z.write(f, arcname=os.path.join("logs", os.path.basename(f)))
        return {"ok": True, "count": len(fs), "path": dest_zip}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
