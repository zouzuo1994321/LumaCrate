# -*- coding: utf-8 -*-
"""流明盒 (LumaCrate) 启动入口 —— 独立桌面程序，不依赖浏览器。

v1.40.1（反馈 3）：本文件同时是「内置浏览器取 cookie」子进程的入口 ——
带 `--cf-browser` 参数启动时**不初始化 Qt**，直接把控制权交给 `cf_browser.main()`
（pywebview 要求 MainThread，见文件末尾的分流）。所以 Qt 相关 import 全部延迟到
`main()` 内部，避免子进程白白加载一遍 Qt。
"""
import os
import sys
import subprocess


def _app_resource(name):
    """定位打包 / 开发期的资源文件（logo-4.png 等）。

    打包后资源在 sys._MEIPASS；开发期 logo-4.png 放在项目根目录（src 的上级）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(getattr(sys, "_MEIPASS", ""))
        candidates.append(os.path.dirname(sys.executable))
    else:
        candidates.append(here)                       # src/
        candidates.append(os.path.dirname(here))      # 项目根（logo-4.png 在此）
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


def _i18n_tip(text):
    """启动提示语按当前界面语言显示；i18n 还没初始化时原样返回中文。

    单独包一层是因为 `_i18n_tip()` 在 `set_lang()` **之前**就可能被调用（第一句提示
    在语言初始化前发出）—— 那时 `i18n.tr()` 返回的还是中文原文，属于预期行为，
    绝不能为了「第一句也翻」把语言初始化提到 `QApplication` 之前去。
    """
    try:
        import i18n
        return i18n.tr(text)
    except Exception:
        return text


def main():
    # v1.40.1（反馈 3）：Qt 相关 import 延迟到此处 —— 这样带 `--cf-browser` 启动的
    # 子进程（见文件末尾分流）不会白白加载一遍 Qt。
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    import database as db
    import version as ver
    import applog
    import splash as splash_mod
    from main_window import MainWindow, load_style

    applog.setup()                   # v1.13.0：先把「全部运行记录」的日志系统挂上
    applog.install_excepthook()      # 未捕获异常也写进日志（打包后没有控制台）
    applog.log(f"启动 {ver.APP_NAME} {ver.FULL_VERSION}  frozen={getattr(sys, 'frozen', False)}")
    _kill_other_instances()          # 先结束同名旧进程，再启动自身

    # v1.24.0（反馈 4）：蓝色启动画面。先建 QApplication（Qt 控件必须有 app），
    # 再用真实启动步骤驱动进度；LMC_NO_SPLASH=1 时 make_splash 返回 None，全流程照常。
    app = QApplication(sys.argv)

    # v1.39.3：**必须显式指定 QStyle 为 Fusion**。
    # Qt 6 在 Windows 11 上默认用 `windows11` 风格，它是**唯一画不出
    # QTreeView::indicator（树控件行内复选框）的风格** —— 真机实测：
    #   windows11    → checkbox 矩形 16x19 非零，但复选框填充/描边色**一个像素都没有**
    #   windowsvista → 770 像素     Windows → 820 像素     Fusion → 820 像素
    # 也就是 `QStyleSheetStyle` 画的 `QTreeView::indicator` 与 windows11 的原生
    # checkbox 绘制路径冲突，导致「演员检测」结果树的「选择」列一格不画。
    # ⚠ 这也说明 v1.39.0 / v1.39.2 两轮「改 indicator 背景色」的修复方向是错的：
    #   颜色从来不是问题，离屏探针之所以全绿是因为 offscreen 后端不用 windows11。
    #   **凡是验「控件是否真画出来」的探针，必须在 `QT_QPA_PLATFORM=windows` 下跑。**
    # Fusion 与 windowsvista 的观感差异对本软件（深色玻璃主题 + 全局 QSS）不可见，
    # 换来的是所有控件在所有 Windows 版本上表现一致。
    try:
        from PySide6.QtWidgets import QStyleFactory
        _st = QStyleFactory.create("Fusion")
        if _st is not None:
            app.setStyle(_st)
    except Exception as e:
        applog.log("设置 Fusion 风格失败，沿用系统默认：%s" % e)

    app.setApplicationName(ver.APP_NAME)
    app.setApplicationVersion(ver.VERSION)
    logo = _app_resource("logo-4.png")   # v1.35.1：新品牌图标（金色胶片 LumaCrate）
    if logo:
        app.setWindowIcon(QIcon(logo))        # v1.22.0（反馈 3）：logo 作为窗口/任务栏图标

    sp = splash_mod.make_splash(logo)
    if sp is not None:
        sp.fade_in(520)
        sp.setProgress(8, _i18n_tip("正在检查运行环境…"))

    # v1.32.0（反馈 3）：界面语言要在**建任何界面之前**生效 ——
    # 主窗、启动画面、设置窗都会读 i18n.tr()，晚一步就会先渲染一遍中文再被覆盖。
    try:
        import config as _cfg
        import i18n as _i18n
        _lang = _cfg.get_settings().language()
        _i18n.set_lang(_lang)
        applog.log("界面语言：%s（%s）" % (_lang, _i18n.cn_name(_lang)))
    except Exception as e:
        applog.log("读取界面语言失败，按基准语言启动：%s" % e)

    # v1.41.2（方案B 修复）：把「用内置浏览器抓取」开关的**持久值**同步到浏览器会话单例。
    # 以前 set_enabled 只在「设置页打开 / 切换开关」时调用，重启后 SESSION._enabled 停在
    # 默认 False → scraper.http_get 的回退门 is_enabled()=False → 方案B 从不触发
    # （症状：站点验证显示「会话已托管」，但实际刮削 / 复测仍走无头、照旧失败）。
    try:
        import browser_session as _bs
        import config as _cfgs
        _bs.SESSION.set_enabled(bool(_cfgs.get_settings().scraper.get("browser_scrape", False)))
    except Exception as e:
        applog.log("同步「用内置浏览器抓取」开关失败：%s" % e)

    db.init_db()
    if sp is not None:
        sp.setProgress(34, _i18n_tip("正在打开媒体索引…"))
    applog.log("数据库就绪")

    load_style(app)
    if sp is not None:
        sp.setProgress(62, _i18n_tip("正在载入界面样式…"))

    win = MainWindow(logo_path=logo)
    if sp is not None:
        sp.setProgress(86, _i18n_tip("正在统计媒体库…"))
    win.show()
    if sp is not None:
        sp.setProgress(100, _i18n_tip("准备就绪"))
        sp.fade_out(win, 420)
        applog.log("启动画面结束，主窗口显示")

    rc = app.exec()
    applog.log(f"退出 rc={rc}")
    os._exit(rc if isinstance(rc, int) else 0)   # 彻底退出，不保留后台进程


if __name__ == "__main__":
    # v1.40.1（反馈 3）：内置浏览器取 cookie 的**子进程入口**。
    # 打包成单文件 exe 后，`cf_browser.py` 没法再由「python 脚本路径」启动 ——
    # 于是约定用 exe 自身 + `--cf-browser` 开关：这里第一时间分流，把控制权交给
    # `cf_browser.main()`（pywebview 要求 MainThread，所以必须是**新进程**）。
    if len(sys.argv) > 2 and sys.argv[1] == "--cf-browser":
        import cf_browser
        del sys.argv[1]                 # 让 cf_browser 只看到自己的参数
        sys.exit(cf_browser.main())
    main()
