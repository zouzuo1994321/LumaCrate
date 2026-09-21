# -*- coding: utf-8 -*-
"""流明盒 (LumaCrate) 启动入口 —— 独立桌面程序，不依赖浏览器。"""
import os
import sys
import subprocess

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

import database as db
import version as ver
import applog
import splash as splash_mod
from main_window import MainWindow, load_style


def _app_resource(name):
    """定位打包 / 开发期的资源文件（logo.png 等）。

    打包后资源在 sys._MEIPASS；开发期 logo.png 放在项目根目录（src 的上级）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(getattr(sys, "_MEIPASS", ""))
        candidates.append(os.path.dirname(sys.executable))
    else:
        candidates.append(here)                       # src/
        candidates.append(os.path.dirname(here))      # 项目根（logo.png 在此）
    for c in candidates:
        if c:
            p = os.path.join(c, name)
            if os.path.exists(p):
                return p
    return None


def _kill_other_instances():
    """单实例：打开新 exe 时关闭同名旧进程。仅打包后生效。

    关键：PyInstaller `--onefile` 下**引导器(bootloader)父进程与真正的应用子进程同名**，
    我们运行在子进程里。若只排除自身 pid，就会把「同名」的父引导器一起 taskkill /t，
    从而把进程树（连同自己）杀掉 —— 表现为「双击一闪就退、根本打不开」。
    因此必须同时排除自身 pid 与自己的父进程 pid(os.getppid())。

    旧实例同样是「父引导器 + 子应用」一对：杀掉其任一（带 /t）即可让旧实例整体退出。
    """
    if not getattr(sys, "frozen", False):
        return
    my_pid = os.getpid()
    my_ppid = os.getppid()          # 自己的 onefile 引导器父进程，绝不能杀
    my_name = os.path.basename(sys.executable).lower()
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=8,
            creationflags=no_window).stdout
    except Exception:
        return
    for line in out.splitlines():
        parts = line.split('","')
        if len(parts) < 2:
            continue
        name = parts[0].strip('"').lower()
        pid = parts[1].strip('"') if len(parts) > 1 else ""
        if name == my_name and pid.isdigit() and int(pid) not in (my_pid, my_ppid):
            try:
                subprocess.run(["taskkill", "/pid", pid, "/f", "/t"], timeout=8,
                               capture_output=True, creationflags=no_window)
            except Exception:
                pass


def main():
    applog.setup()                   # v1.13.0：先把「全部运行记录」的日志系统挂上
    applog.install_excepthook()      # 未捕获异常也写进日志（打包后没有控制台）
    applog.log(f"启动 {ver.APP_NAME} {ver.FULL_VERSION}  frozen={getattr(sys, 'frozen', False)}")
    _kill_other_instances()          # 先结束同名旧进程，再启动自身

    # v1.24.0（反馈 4）：蓝色启动画面。先建 QApplication（Qt 控件必须有 app），
    # 再用真实启动步骤驱动进度；LMC_NO_SPLASH=1 时 make_splash 返回 None，全流程照常。
    app = QApplication(sys.argv)
    app.setApplicationName(ver.APP_NAME)
    app.setApplicationVersion(ver.VERSION)
    logo = _app_resource("logo.png")
    if logo:
        app.setWindowIcon(QIcon(logo))        # v1.22.0（反馈 3）：logo 作为窗口/任务栏图标

    sp = splash_mod.make_splash(logo)
    if sp is not None:
        sp.fade_in(520)
        sp.setProgress(8, "正在检查运行环境…")

    db.init_db()
    if sp is not None:
        sp.setProgress(34, "正在打开媒体索引…")
    applog.log("数据库就绪")

    load_style(app)
    if sp is not None:
        sp.setProgress(62, "正在载入界面样式…")

    win = MainWindow(logo_path=logo)
    if sp is not None:
        sp.setProgress(86, "正在统计媒体库…")
    win.show()
    if sp is not None:
        sp.setProgress(100, "准备就绪")
        sp.fade_out(win, 420)
        applog.log("启动画面结束，主窗口显示")

    rc = app.exec()
    applog.log(f"退出 rc={rc}")
    os._exit(rc if isinstance(rc, int) else 0)   # 彻底退出，不保留后台进程


if __name__ == "__main__":
    main()
