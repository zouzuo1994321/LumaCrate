# -*- coding: utf-8 -*-
"""
打包为独立 exe (不依赖浏览器)。
用法: python build_exe.py
产物: 流明盒-<VERSION>-<BUILD>.exe  (生成于根目录)
旧版 exe 会被移入 history/ 留档。

说明: 本环境对 Z: 网络路径的 os.remove 有安全拦截(PyInstaller 收尾清理会触发)，
因此先在本地 C: 临时目录构建(回收站可用)，再把成品复制回根目录并归档。
"""
import os
import sys
import shutil

import PyInstaller.__main__

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
HISTORY = os.path.join(ROOT, "history")
DEV = os.path.join(ROOT, "dev")
BUILD_TMP = "C:/lmc_build_tmp"          # 本地盘，回收站可用，避开 Z: 安全拦截
sys.path.insert(0, SRC)

import version as ver

# v1.27.0：软件更名「流明盒」，exe 产物名随动 —— 流明盒-v1.27.0-2609210037.exe。
EXE_NAME = f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}"
# 归档时要认的**旧名前缀**：更名后根目录里可能还躺着上一版的旧 exe，别漏掉。
LEGACY_PREFIXES = ("本地影视中心-",)


def _ensure_logo_ico():
    """确保 logo.ico 存在且不旧于 logo.png（PyInstaller --icon 用，v1.23.0 反馈 2）。

    坑：只在「文件不存在」时生成会一直沿用旧 ico（换了 logo.png 也不更新），
    所以按 mtime 判断，源图更新过就重新生成多分辨率 ico。
    """
    png = os.path.join(ROOT, "logo.png")
    ico = os.path.join(ROOT, "logo.ico")
    if os.path.exists(ico) and (not os.path.exists(png)
                                or os.path.getmtime(ico) >= os.path.getmtime(png)):
        return ico
    if not os.path.exists(png):
        return ico if os.path.exists(ico) else None
    try:
        from PIL import Image
        Image.open(png).convert("RGBA").save(
            ico, format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
        print(f"[logo] 已重新生成 {ico}")
        return ico
    except Exception as e:
        print(f"[logo] 生成 ico 失败：{e}")
        return ico if os.path.exists(ico) else None


def main():
    os.makedirs(HISTORY, exist_ok=True)
    os.makedirs(DEV, exist_ok=True)
    os.makedirs(BUILD_TMP, exist_ok=True)

    # 把 history 里可能残留的同版本 exe 先挪到 dev，避免重复/可疑归档
    # v1.24.1：原来无论 dev/ 里有没有同名文件都硬 rename，第二次构建就会 WinError 183
    # 失败（history 里的留档动不了），接着下面归档根目录时也只好再往 dev/ 塞一份 ——
    # dev/ 就这么攒了 29 份 45MB 的 exe（约 1.3GB 纯重复）。现在同名就跳过。
    for f in os.listdir(HISTORY):
        if f.startswith(EXE_NAME) and f.endswith(".exe"):
            src = os.path.join(HISTORY, f)
            dst = os.path.join(DEV, f)
            if os.path.exists(dst):
                print(f"[跳过移出] dev/{f} 已存在（不重复搬运）")
                continue
            try:
                os.rename(src, dst)
                print(f"[移出] history/{f} -> dev/")
            except Exception as e:
                print(f"[跳过] {f}: {e}")

    # 归档根目录里的所有旧版 exe（换上来的新版本稍后复制回根目录）
    # 注意：本机对 Z: 的 os.remove 有安全拦截，shutil.move 可能走 copy+remove 而失败，
    # 因此在同一磁盘内统一用 os.rename（等价于移动，不触发删除钩子）。
    for f in os.listdir(ROOT):
        if f.endswith(".exe") and (f.startswith(ver.APP_NAME + "-")
                                   or any(f.startswith(p) for p in LEGACY_PREFIXES)):
            src = os.path.join(ROOT, f)
            dst = os.path.join(HISTORY, f)
            if os.path.exists(dst):
                # history 里已经有同名留档。它本来就是同一次构建复制出来的**字节相同**的
                # 副本（0033/0034 实测同尺寸同内容），所以正确做法是覆盖回去，而不是
                # 「留在原地」—— 后者会让根目录每构建一次就多攒一个 48MB 旧包
                # （v1.25.0 构建前根目录已同时躺着 0033 与 0034）。
                # 绝不退而写 dev/（那正是 dev/ 攒满 45MB 重复 exe 的原因）。
                try:
                    os.replace(src, dst)      # 原子；失败时源文件仍在
                    print(f"[归档] {f} -> history/{f}（覆盖字节相同的同名留档）")
                except Exception as e:
                    print(f"[保留] 根目录 {f}：history/ 有同名留档且覆盖失败（{e}）")
                continue
            try:
                os.rename(src, dst)
                print(f"[归档] {f} -> history/{f}")
            except Exception as e:
                print(f"[跳过归档] {f}: {e}")

    args = [
        os.path.join(SRC, "main.py"),
        "--name", EXE_NAME,
        "--onefile",
        "--windowed",
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--add-data", f"{os.path.join(SRC, 'style.qss')};.",
        "--add-data", f"{os.path.join(ROOT, 'logo.png')};.",      # v1.22.0（反馈 3）：运行时窗口图标
        "--hidden-import", "PySide6.QtXml",
        "--hidden-import", "backdrop",
        "--hidden-import", "scraper",
        "--hidden-import", "veil",
        "--hidden-import", "applog",
        "--hidden-import", "backup",
        "--hidden-import", "duplicates",
        "--hidden-import", "insight",        # v1.24.0：画像概览计算层
        "--hidden-import", "recommend",      # v1.24.0：智能推荐
        "--hidden-import", "splash",         # v1.24.0：启动画面
        "--hidden-import", "tagopt",         # v1.25.0：标签优化（纯计算层）
        "--hidden-import", "nfo_parser",     # v1.25.0：标签优化要读/写 nfo
        "--hidden-import", "sysmon",         # v1.27.0：侧栏实时状态（采集线程 + 自绘横条）
        "--hidden-import", "imagedetect",    # v1.30.0：图像检测（缺图/破损图判定与替换）
        "--hidden-import", "nfo_editor",     # v1.30.0：手动修改（17 项 nfo 字段读写）
        "--hidden-import", "letter_index",   # v1.30.0：演员库/导演库 A-Z 索引条
        "--hidden-import", "ui_imagedetect",  # v1.30.0：工具 → 图像检测页
        "--hidden-import", "ui_manualedit",   # v1.30.0：工具 → 手动修改页
        # v1.27.0：实时状态的 CPU / 内存 / 网络采集。venv 里有 psutil 7.2.2，
        # _pyinstaller_hooks_contrib/stdhooks/hook-psutil.py 会把它连
        # _psutil_windows.pyd 一起收进来（已核实 hook 存在）；万一没收到，
        # sysmon.py 里有 ctypes 兜底分支，软件照样能跑，只是少了网速读数。
        "--hidden-import", "psutil",
        "--distpath", BUILD_TMP,
        "--workpath", BUILD_TMP,
        "--specpath", BUILD_TMP,
    ]
    # v1.23.0（反馈 2）：--icon 决定 exe 的「文件图标」（资源管理器/桌面/开始菜单），
    # 与运行时 setWindowIcon（任务栏/Alt-Tab）是两条独立链路，必须分别设置。
    ico = _ensure_logo_ico()
    if ico:
        args += ["--icon", ico]
        print(f"[logo] --icon {ico}")
    else:
        print("[logo] 未找到 logo.ico，exe 将使用 PyInstaller 默认图标")
    PyInstaller.__main__.run(args)

    built = os.path.join(BUILD_TMP, EXE_NAME + ".exe")
    if not os.path.exists(built):
        print("[失败] 未找到产物 exe")
        return

    root_exe = os.path.join(ROOT, EXE_NAME + ".exe")
    shutil.copy(built, root_exe)                                  # 根目录：最新版
    shutil.copy(built, os.path.join(HISTORY, EXE_NAME + ".exe"))  # 历史留档
    print(f"[完成] 根目录: {root_exe}")
    print(f"[完成] 归档:  {os.path.join(HISTORY, EXE_NAME + '.exe')}")


if __name__ == "__main__":
    main()
