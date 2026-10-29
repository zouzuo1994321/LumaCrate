# -*- coding: utf-8 -*-
"""运行期小图标（QSS `image: url(...)` 用）—— v2.0.1
=====================================================
为什么要有这个模块
------------------
Qt 的样式表**画不了矢量图形**：`QCheckBox::indicator:checked` 只能换底色，
`QSpinBox::up-arrow` 只认 `image:`（`color:` 对箭头无效）。而 `image:` 只接受
URL —— 文件路径或 `:/` 资源，**不认内存里的 QPixmap**。

单文件 PyInstaller 打包下没有 `rcc` 步骤，做不了 `.qrc` 资源；于是这里在启动时
用 QPainter 把小图形画成 PNG 落到可写目录，再由 `main_window.render_style()`
把路径替换进 `style.qss` 的占位符（`__GLYPH_UP__` 等）。

几个硬约束（都是踩过的坑）
--------------------------
* **绝不能用 QPixmap 画**：QPixmap 必须先有 QGuiApplication，否则 qFatal 直接
  abort —— 打包后是「双击闪退、日志一个字都没有」。这里一律用 QImage。
* 画布尺寸按**设备像素**给（17px 的勾选框内区 ≈ 12px），不做 @2x 变体：本软件
  真机 dpr=1.0，多一套变体只会让路径与实际显示对不上。
* 字体不参与绘制（只画线），所以离屏 / 无 GUI 环境下也能跑。
* 生成失败**绝不抛异常**：返回空 dict，QSS 里对应占位符退化成 `none`，
  界面只是少一个小箭头，不影响启动。
"""
import os

import applog

#: 图形版本：改了绘制参数就把这里 +1，旧文件会被新名字顶掉，不用清缓存。
_VER = "v2"

#: 目标目录（与日志/索引同根：打包后在 exe 同级 index_data 下）
_DIR_NAME = ("index_data", "ui_glyphs")


def glyph_dir() -> str:
    d = os.path.join(applog.base_dir(), *_DIR_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _painter(pm):
    from PySide6.QtGui import QPainter
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    return p


def _check(path, size, color="#ffffff", thick=2.0):
    """白色对勾：起笔在左中、折到左下、再拉到右上。"""
    from PySide6.QtGui import QColor, QPen, QImage
    from PySide6.QtCore import Qt, QPointF

    pm = QImage(size, size, QImage.Format_ARGB32)
    pm.fill(Qt.transparent)
    p = _painter(pm)
    pen = QPen(QColor(color))
    pen.setWidthF(thick)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m = thick / 2.0 + 0.6
    p.drawPolyline([QPointF(m, size * 0.54),
                    QPointF(size * 0.38, size - m),
                    QPointF(size - m, m + 0.3)])
    p.end()
    return pm.save(path)


def _chevron(path, size, up=True, color="#a1a1aa", thick=1.9):
    """粗圆头折线箭头（与用户给的图标同款：宽扁、圆头、无尖角）。"""
    from PySide6.QtGui import QColor, QPen, QImage
    from PySide6.QtCore import Qt, QPointF

    pm = QImage(size, size, QImage.Format_ARGB32)
    pm.fill(Qt.transparent)
    p = _painter(pm)
    pen = QPen(QColor(color))
    pen.setWidthF(thick)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m = thick / 2.0 + 0.6
    cy = size / 2.0
    dy = size * 0.19
    tip = cy - dy if up else cy + dy
    foot = cy + dy if up else cy - dy
    p.drawPolyline([QPointF(m, foot), QPointF(size / 2.0, tip),
                    QPointF(size - m, foot)])
    p.end()
    return pm.save(path)


#: key → (文件名主干, 尺寸, 画笔参数)
_SPECS = {
    "check":      ("check_%s" % _VER, 12, dict(thick=2.1)),
    "arrow_up":   ("arrow_up_%s" % _VER, 11, dict(up=True, thick=1.8)),
    "arrow_down": ("arrow_down_%s" % _VER, 11, dict(up=False, thick=1.8)),
}

#: 写盘格式候选。PNG 走 Qt 的 imageformats 插件，BMP 是内置的 ——
#: 万一打包漏了 qpng.dll，退回 BMP 仍然能用（QSS 只看路径，不看后缀）。
_FORMATS = (".png", ".bmp")

_CACHE = None


def _draw(handler, d, base, size, kw, force=False):
    """按候选格式尝试写盘，返回真正落盘的文件路径（全失败返回 None）。

    ⚠ 覆盖写而不是「先删后写」：本机对 os.remove 有安全拦截，删不掉就会永远
    走不到写盘分支。QImage.save 同路径会直接覆盖，够用。
    """
    for ext in _FORMATS:
        path = os.path.join(d, base + ext)
        try:
            if not force and os.path.exists(path) and os.path.getsize(path) >= 64:
                return path
            if handler(path, size, **kw):
                return path
        except Exception:
            continue
    return None


def ensure(force: bool = False) -> dict:
    """生成（或复用）三个小图标，返回 {key: 绝对路径}。失败的项目直接缺席。"""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    out = {}
    d = glyph_dir()
    if not os.path.isdir(d):
        _CACHE = out
        return out
    for key, (base, size, kw) in _SPECS.items():
        try:
            handler = _check if key == "check" else _chevron
            path = _draw(handler, d, base, size, kw, force=force)
            if path:
                out[key] = path
            else:
                applog.log("生成界面小图标 %s 失败（所有格式都写不出）" % key, "warning")
        except Exception as e:
            applog.log("生成界面小图标 %s 失败：%s" % (key, e), "warning")
    _CACHE = out
    return out


def url(key: str, fallback: str = "none") -> str:
    """给 QSS 用的 `url("...")` 文本；缺图标时返回 `none`（合法值，整条声明仍生效）。"""
    p = ensure().get(key)
    if not p:
        return fallback
    return 'url("%s")' % p.replace("\\", "/")
