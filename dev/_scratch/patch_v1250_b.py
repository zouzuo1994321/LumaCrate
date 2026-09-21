# -*- coding: utf-8 -*-
"""v1.25.0 批量补丁 _b：config(HLS 派生) / style.qss / main_window / recommend / ui_home。

同样是「锚点精确匹配 + 命中数断言」，任何一处对不上立刻抛错、绝不半改。
写文件统一 newline="" —— Edit/Write 工具在本项目会把 LF 转成 CRLF（已踩过）。
"""
import os

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
REPORT = []


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    with open(os.path.join(SRC, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch(rel, label, old, new, count=1):
    s = read(rel)
    n = s.count(old)
    if n != count:
        raise SystemExit(f"✗ [{rel} :: {label}] 锚点命中 {n} 次，期望 {count} 次\n"
                         f"----- 锚点 -----\n{old[:400]}\n----------------")
    write(rel, s.replace(old, new))
    REPORT.append(f"OK  {rel:16s} {label}")


def subst(rel, label, pairs):
    """按顺序做多次 replace-all，逐项断言命中数。"""
    s = read(rel)
    for old, new, cnt in pairs:
        n = s.count(old)
        if n != cnt:
            raise SystemExit(f"✗ [{rel} :: {label}] {old!r} 命中 {n} 次，期望 {cnt} 次")
        s = s.replace(old, new)
    write(rel, s)
    REPORT.append(f"OK  {rel:16s} {label} ({len(pairs)} 组替换)")


# ===========================================================================
# 1) config.py —— accent_shades 改用 HSL 派生
# ===========================================================================
patch("config.py", "import colorsys",
      "import os\nimport re\nimport sys\nimport json\nimport time\n",
      "import os\nimport re\nimport sys\nimport json\nimport time\nimport colorsys\n")

patch("config.py", "accent_shades -> HSL 派生",
      'def accent_shades(hexv: str = None) -> dict:\n'
      '    """由高亮色派生出一组明暗变体，供 QSS 令牌使用。\n'
      '\n'
      '    base = 原色；dark = 按下/选中底；deep = hover 底；light = 描边。\n'
      '    按比例缩放并夹到 0~255 —— 换任何基础色，层次关系都保持一致\n'
      '    （默认朱红缩放后与原先写死的几个色值基本重合，所以老用户观感不变）。\n'
      '    """\n'
      '    r, g, b = accent_rgb(hexv)\n'
      '\n'
      '    def scale(f):\n'
      '        return (_clamp8(r * f), _clamp8(g * f), _clamp8(b * f))\n'
      '\n'
      '    return {"base": (r, g, b), "dark": scale(0.73), "deep": scale(0.85),\n'
      '            "light": scale(1.17)}\n',
      'def accent_shades(hexv: str = None) -> dict:\n'
      '    """由高亮色派生出一组明暗变体，供 QSS 令牌使用。\n'
      '\n'
      '    base = 原色；dark = 按下/选中底；deep = 主按钮底；light = 亮描边。\n'
      '\n'
      '    **为什么在 HSL 里派生，而不是 RGB 等比缩放**：原来的调色板是人工挑的，\n'
      '    并不是同一个色的等比缩放 —— 例如朱红 #c0392b 在 QSS 里的描边色是 #e05243，\n'
      '    它在 RGB 下的通道倍率是 (1.17, 1.44, 1.56)，三个通道根本不一致。用等比缩放\n'
      '    的话，换成任何颜色描边都会偏灰偏暗（朱红描边会从 (224,82,67) 掉到 (225,67,50)），\n'
      '    而描边恰恰是用户最容易看见「高亮效果」的地方。改成只动 HSL 里的明度/饱和度、\n'
      '    保留色相，实测朱红能复现出 (223,84,68) ≈ 原来的 (224,82,67)；换成玉白这种\n'
      '    极浅色时也不会缩放着缩着就糊成一团白。\n'
      '    """\n'
      '    r, g, b = accent_rgb(hexv)\n'
      '    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)\n'
      '\n'
      '    def vari(l_delta, s_delta, l_lo=0.16, l_hi=0.94):\n'
      '        ll = max(l_lo, min(l_hi, l + l_delta))\n'
      '        ss = max(0.0, min(1.0, s + s_delta))\n'
      '        rr, gg, bb = colorsys.hls_to_rgb(h, ll, ss)\n'
      '        return (_clamp8(rr * 255), _clamp8(gg * 255), _clamp8(bb * 255))\n'
      '\n'
      '    return {"base": (r, g, b),\n'
      '            "dark": vari(-0.135, +0.05),     # 按下 / 列表选中底\n'
      '            "deep": vari(-0.080, +0.03),     # 主按钮底\n'
      '            "light": vari(+0.110, +0.08)}    # 亮描边 / 悬停边框\n')

# ===========================================================================
# 2) style.qss —— 红值全部令牌化 + 新增 #Seg
# ===========================================================================
patch("style.qss", "头部令牌说明",
      '   经典暗色主题下四个令牌都是 255（完全不透明）。\n',
      '   经典暗色主题下四个令牌都是 255（完全不透明）。\n'
      '\n'
      '   另有 4 个「高亮色」令牌（v1.25.0 反馈 5），由 render_style() 按\n'
      '   「外观 → 高亮色」那一项现算。它们替换出来的是 **"r, g, b" 三通道文本**\n'
      '   （QSS 的 rgba() 通道位写不了十六进制），所以用法固定是 rgba(令牌, 透明度)：\n'
      '     ACCENT        基础色 —— hover 描边 / 焦点框 / 滑块 / 进度条 / 勾选框\n'
      '     ACCENT_DARK   按下 / 列表与表格选中底\n'
      '     ACCENT_DEEP   主按钮底\n'
      '     ACCENT_LIGHT  亮描边 —— 主按钮边框 / chip 选中边框\n'
      '   （上面的名字在 QSS 里前后各加两个下划线。）四个变体由 accent_shades()\n'
      '   在 HSL 空间一起派生，换任何基础色，明暗层次关系都保持一致。\n')

subst("style.qss", "红值令牌化", [
    ("rgba(192, 57, 43, ", "rgba(__ACCENT__, ", 10),
    ("rgba(140, 31, 26, ", "rgba(__ACCENT_DARK__, ", 9),
    ("rgba(224, 82, 67, ", "rgba(__ACCENT_LIGHT__, ", 5),
    ("rgba(163, 42, 32, ", "rgba(__ACCENT_DEEP__, ", 3),
    ("rgba(189, 51, 38, ", "rgba(__ACCENT__, ", 1),
    ("rgba(160, 38, 30, ", "rgba(__ACCENT_DEEP__, ", 1),
    ("#e05243", "__ACCENT_LIGHT__", 3),
    ("#c0392b", "__ACCENT__", 3),
])

patch("style.qss", "新增 #Seg（首页快捷筛选选中态）",
      '/* 影片墙「筛选」按钮**展开时高亮**（v1.17.0：FacetBar 默认收缩，点开才展开） */\n'
      'QPushButton#Ghost:checked {\n'
      '    background: rgba(__ACCENT_DARK__, 0.85); border-color: rgba(__ACCENT_LIGHT__, 0.9); color: #ffffff;\n'
      '}\n',
      '/* 影片墙「筛选」按钮**展开时高亮**（v1.17.0：FacetBar 默认收缩，点开才展开） */\n'
      'QPushButton#Ghost:checked {\n'
      '    background: rgba(__ACCENT_DARK__, 0.85); border-color: rgba(__ACCENT_LIGHT__, 0.9); color: #ffffff;\n'
      '}\n'
      '\n'
      '/* ---------- 首页模块快捷筛选（v1.25.0 反馈 6） ----------\n'
      '   首页顶部「最近添加 / 我的收藏 / 合集」这三个按钮原来复用 #Ghost：选中后只有\n'
      '   一点点极淡的描边，用户反馈「不知道是不是点了这个」。\n'
      '   这里单独一套「选中 = 实心强调底 + 亮描边 + 加粗白字」，未选中仍是玻璃质感。\n'
      '   注意：**不能**直接给 #Ghost 加 :checked —— `#Ghost:checked` 已经被「影片墙 → 筛选」\n'
      '   的展开态占用，两个控件共用同一个选择器会互相串样式，所以另开一个 objectName。 */\n'
      'QPushButton#Seg {\n'
      '    background: rgba(255, 255, 255, 0.04);\n'
      '    border: 1px solid rgba(255, 255, 255, 0.12); color: #d3cabb;\n'
      '}\n'
      'QPushButton#Seg:hover {\n'
      '    background: rgba(255, 255, 255, 0.10);\n'
      '    border-color: rgba(__ACCENT__, 0.75); color: #f7e3b4;\n'
      '}\n'
      'QPushButton#Seg:checked {\n'
      '    background: rgba(__ACCENT_DARK__, 0.92);\n'
      '    border: 1px solid __ACCENT_LIGHT__; color: #ffffff; font-weight: 600;\n'
      '}\n'
      'QPushButton#Seg:checked:hover { background: rgba(__ACCENT_DEEP__, 0.96); }\n')

# ===========================================================================
# 3) main_window.py —— 高亮色令牌 + 外发光 + 自绘卡片取色
# ===========================================================================
patch("main_window.py", "import QGraphicsDropShadowEffect",
      "    QCheckBox, QProgressBar, QComboBox, QLayout, QButtonGroup,\n)\n",
      "    QCheckBox, QProgressBar, QComboBox, QLayout, QButtonGroup,\n"
      "    QGraphicsDropShadowEffect,\n)\n")

patch("main_window.py", "模块级 ACCENT_RGB",
      'STYLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")\n',
      'STYLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")\n'
      '# v1.25.0（反馈 5）：当前「高亮色」的 RGB。由 render_style() 在每次重载样式表时刷新，\n'
      '# 自绘控件（PosterCard / ActorCard 的选中描边、选中卡的外发光）读它取色 ——\n'
      '# QSS 那边走令牌替换，两边拿到的必须是同一个值，否则描边和光晕会串色。\n'
      'ACCENT_RGB = (192, 57, 43)\n')

patch("main_window.py", "render_style 注入高亮色令牌",
      '    veil, panel = cfg.appearance_alphas(appearance or cfg.get_settings().appearance)\n'
      '    surf = min(255, int(panel) + 30)\n'
      '    dlg = min(255, max(int(surf), 232))\n'
      '    for token, val in (("__VEIL__", veil), ("__PANEL__", panel),\n'
      '                       ("__SURF__", surf), ("__DLG__", dlg)):\n'
      '        qss = qss.replace(token, str(int(val)))\n'
      '    return qss\n',
      '    ap = appearance or cfg.get_settings().appearance\n'
      '    veil, panel = cfg.appearance_alphas(ap)\n'
      '    surf = min(255, int(panel) + 30)\n'
      '    dlg = min(255, max(int(surf), 232))\n'
      '    for token, val in (("__VEIL__", veil), ("__PANEL__", panel),\n'
      '                       ("__SURF__", surf), ("__DLG__", dlg)):\n'
      '        qss = qss.replace(token, str(int(val)))\n'
      '    # v1.25.0（反馈 5）：高亮色令牌。QSS 的 rgba() 通道位写不了十六进制，\n'
      '    # 所以这里替换成 "r, g, b" 文本；同时刷新模块级 ACCENT_RGB，让自绘控件同步换色。\n'
      '    # 先替换长令牌再替换短令牌（__ACCENT_DARK__ 里不含 __ACCENT__，顺序其实无所谓，\n'
      '    # 但写成从长到短以后再加令牌就不会踩坑）。\n'
      '    global ACCENT_RGB\n'
      '    acc_hex = (ap or {}).get("accent")\n'
      '    ACCENT_RGB = cfg.accent_rgb(acc_hex)\n'
      '    shades = cfg.accent_shades(acc_hex)\n'
      '    for token, key in (("__ACCENT_LIGHT__", "light"), ("__ACCENT_DARK__", "dark"),\n'
      '                       ("__ACCENT_DEEP__", "deep"), ("__ACCENT__", "base")):\n'
      '        qss = qss.replace(token, ", ".join(str(v) for v in shades[key]))\n'
      '    return qss\n')

patch("main_window.py", "_select_card 挂外发光",
      '    # ---------- 卡片选中（粉色流光高亮，全局唯一） ----------\n'
      '    def _select_card(self, card):\n'
      '        if self._selected_card is card:\n'
      '            return\n'
      '        if self._selected_card:\n'
      '            self._selected_card.set_selected(False)\n'
      '        self._selected_card = card\n'
      '        if card:\n'
      '            card.set_selected(True)\n',
      '    # ---------- 卡片选中（强调色流光 + 外发光，全局唯一） ----------\n'
      '    def _select_card(self, card):\n'
      '        if self._selected_card is card:\n'
      '            return\n'
      '        old = self._selected_card\n'
      '        if old is not None:\n'
      '            try:\n'
      '                old.set_selected(False)\n'
      '                old.setGraphicsEffect(None)     # 摘掉外发光（Qt 会连带删掉旧 effect）\n'
      '            except RuntimeError:\n'
      '                pass\n'
      '        self._selected_card = card\n'
      '        if card:\n'
      '            card.set_selected(True)\n'
      '            self._apply_card_glow(card)\n'
      '\n'
      '    def _apply_card_glow(self, card):\n'
      '        """给选中的卡片挂一层真正「向外扩散」的光晕（v1.25.0 反馈 5）。\n'
      '\n'
      '        卡片 paintEvent 里那圈描边是画在控件内部的，超出边界的部分会被裁掉，\n'
      '        所以只能算「内发光」；要让光溢到卡片之外，得靠 QGraphicsDropShadowEffect\n'
      '        （blur radius 撑开模糊半径、offset 归零 = 四周均匀发光）。\n'
      '        effect 由卡片自己持有（setGraphicsEffect 会转移所有权），页面重建时随卡片一起销毁。\n'
      '        """\n'
      '        if not _qt_alive(card):\n'
      '            return\n'
      '        r, g, b = ACCENT_RGB\n'
      '        try:\n'
      '            eff = QGraphicsDropShadowEffect(card)\n'
      '            eff.setBlurRadius(38)\n'
      '            eff.setOffset(0, 0)\n'
      '            eff.setColor(QColor(r, g, b, 215))\n'
      '            card.setGraphicsEffect(eff)\n'
      '            card.raise_()\n'
      '        except RuntimeError:\n'
      '            pass\n')

patch("main_window.py", "PosterCard 选中描边取高亮色",
      '        if self._selected:\n'
      '            alpha = int(175 + 55 * (0.5 + 0.5 * math.sin(self._phase)))\n'
      '            p.setPen(QPen(QColor(255, 120, 190, 45), 6))     # 外发光\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '            p.setPen(QPen(QColor(255, 110, 180, alpha), 2.6))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '        else:\n'
      '            p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))\n',
      '        if self._selected:\n'
      '            # v1.25.0（反馈 5）：色相跟「外观 → 高亮色」走，描边加粗、呼吸幅度加大。\n'
      '            # 这里画的是**内**圈光晕（超出控件边界的会被裁掉）；真正往卡片外扩散的\n'
      '            # 那层由 _select_card() → _apply_card_glow() 的 QGraphicsDropShadowEffect 负责。\n'
      '            ar, ag, ab = ACCENT_RGB\n'
      '            alpha = int(205 + 50 * (0.5 + 0.5 * math.sin(self._phase)))\n'
      '            p.setPen(QPen(QColor(ar, ag, ab, 95), 7))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '            p.setPen(QPen(QColor(ar, ag, ab, alpha), 3.2))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '        else:\n'
      '            p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))\n')

patch("main_window.py", "ActorCard 选中描边取高亮色",
      '        if self._selected:\n'
      '            alpha = int(175 + 55 * (0.5 + 0.5 * math.sin(self._phase)))\n'
      '            p.setPen(QPen(QColor(255, 120, 190, 45), 6))     # 外发光\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '            p.setPen(QPen(QColor(255, 110, 180, alpha), 2.6))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '        else:\n'
      '            p.setPen(QPen(border, 1.4))\n',
      '        if self._selected:\n'
      '            # v1.25.0（反馈 5）：与 PosterCard 同一套规则（高亮色 + 加粗 + 外发光）\n'
      '            ar, ag, ab = ACCENT_RGB\n'
      '            alpha = int(205 + 50 * (0.5 + 0.5 * math.sin(self._phase)))\n'
      '            p.setPen(QPen(QColor(ar, ag, ab, 95), 7))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '            p.setPen(QPen(QColor(ar, ag, ab, alpha), 3.2))\n'
      '            p.drawRoundedRect(r, radius, radius)\n'
      '        else:\n'
      '            p.setPen(QPen(border, 1.4))\n')

patch("main_window.py", "_apply_appearance 同步刷新外发光",
      '    def _apply_appearance(self):\n'
      '        """重载样式表 + 应用/关闭系统模糊（磨砂玻璃）。"""\n'
      '        s = cfg.get_settings()\n'
      '        load_style(QApplication.instance() or QApplication([]), s.appearance)\n',
      '    def _apply_appearance(self):\n'
      '        """重载样式表 + 应用/关闭系统模糊（磨砂玻璃）。"""\n'
      '        s = cfg.get_settings()\n'
      '        load_style(QApplication.instance() or QApplication([]), s.appearance)\n'
      '        # v1.25.0（反馈 5）：换了高亮色之后，当前已选中卡片的外发光也要立刻跟着换\n'
      '        # （否则要取消选中再重新点一下才变色）。\n'
      '        sel = getattr(self, "_selected_card", None)\n'
      '        if sel is not None:\n'
      '            self._apply_card_glow(sel)\n')

# ===========================================================================
# 4) recommend.py —— 指定模型 + 根因修复「换一批其实没避让」
# ===========================================================================
patch("recommend.py", "list_models/resolve_model/probe_ollama/ai_status/_ollama_expand",
      '# ---------------------------------------------------------------- AI 引擎探测\n'
      'def probe_ollama(timeout=0.5):\n'
      '    """本机是否有可用的 Ollama（纯本地、离线）。返回模型名或 None。"""\n'
      '    try:\n'
      '        with urllib.request.urlopen(_OLLAMA + "/api/tags", timeout=timeout) as r:\n'
      '            data = json.loads(r.read().decode("utf-8", "replace"))\n'
      '        models = [m.get("name") for m in (data.get("models") or []) if m.get("name")]\n'
      '        return models[0] if models else None\n'
      '    except Exception:\n'
      '        return None\n'
      '\n'
      '\n'
      'def ai_status():\n'
      '    """给「工具 → 智能推荐」页显示的状态。"""\n'
      '    model = probe_ollama()\n'
      '    if model:\n'
      '        return {"engine": "ollama", "label": f"本地 Ollama（{model}）",\n'
      '                "detail": "离线扩词已启用：会把偏好种子词交给本地模型做语义扩展。"}\n'
      '    return {"engine": "builtin", "label": "内置离线联想引擎",\n'
      '            "detail": "未检测到本地 Ollama，使用内置的标签共现联想（纯本地、无需依赖）。"\n'
      '                      "需要更聪明的语义扩词时：装好 Ollama 后执行「ollama pull qwen2.5:7b」"\n'
      '                      "（或任意模型），再点一次「检测本地 AI 引擎」即可，全程不出网。"}\n'
      '\n'
      '\n'
      'def _ollama_expand(seed_terms, limit=40, timeout=25):\n'
      '    """让本地模型把种子词扩成同类词（离线）。失败一律返回 []。"""\n'
      '    if not seed_terms:\n'
      '        return []\n'
      '    prompt = (\n'
      '        "你是影视标签推荐助手。下面是用户收藏影片的高频标签/片商/演员名。\\n"\n'
      '        "请再给出 30 个**同类且更具体**的标签词（只输出词，逗号分隔，不要解释、不要编号）。\\n"\n'
      '        "种子：" + "、".join(seed_terms[:60]))\n'
      '    body = json.dumps({\n'
      '        "model": probe_ollama() or "llama3",\n'
      '        "prompt": prompt,\n'
      '        "stream": False,\n'
      '        "options": {"temperature": 0.4, "num_predict": 220},\n'
      '    }).encode("utf-8")\n',
      '# ---------------------------------------------------------------- AI 引擎探测\n'
      'def list_models(timeout=0.5) -> list:\n'
      '    """本机 Ollama 里已经装好的模型名（= 命令行 `ollama list` 的第一列）。\n'
      '\n'
      '    v1.25.0（反馈 1）：给「自己输入想调用的模型」用 —— 用户填的名字对不对，\n'
      '    靠它来校验，而不是先发一次注定失败的 /api/generate。不可用时返回 []。\n'
      '    """\n'
      '    try:\n'
      '        with urllib.request.urlopen(_OLLAMA + "/api/tags", timeout=timeout) as r:\n'
      '            data = json.loads(r.read().decode("utf-8", "replace"))\n'
      '    except Exception:\n'
      '        return []\n'
      '    out = []\n'
      '    for m in (data.get("models") or []):\n'
      '        name = m.get("name") or m.get("model")\n'
      '        if name:\n'
      '            out.append(str(name))\n'
      '    return out\n'
      '\n'
      '\n'
      'def configured_model() -> str:\n'
      '    """用户在设置里填的模型名（空 = 自动挑本机第一个）。"""\n'
      '    try:\n'
      '        return str((cfg.get_settings().recommend or {}).get("ai_model") or "").strip()\n'
      '    except Exception:\n'
      '        return ""\n'
      '\n'
      '\n'
      'def resolve_model(model=None) -> str:\n'
      '    """决定这次到底调用哪个模型。\n'
      '\n'
      '    优先级：显式传入 > 设置里填的 > 本机第一个已装模型 > llama3（兜底）。\n'
      '    """\n'
      '    want = str(model or "").strip() or configured_model()\n'
      '    if want:\n'
      '        return want\n'
      '    names = list_models()\n'
      '    return names[0] if names else "llama3"\n'
      '\n'
      '\n'
      'def probe_ollama(timeout=0.5, model=None):\n'
      '    """本机是否有可用的 Ollama（纯本地、离线）。返回**这次要用的模型名**或 None。\n'
      '\n'
      '    与 v1.24.x 的区别：不再无条件取 /api/tags 的第一个 —— 如果用户在设置里指定了\n'
      '    模型，就按指定的来；指定了但本机没装，返回 None（调用方会静默降级到内置联想，\n'
      '    页面上的检测文案会明确告诉用户「这个模型没找到」以及列出本机已装的模型）。\n'
      '    """\n'
      '    names = list_models(timeout)\n'
      '    if not names:\n'
      '        return None\n'
      '    want = str(model or "").strip() or configured_model()\n'
      '    if want:\n'
      '        return want if want in names else None\n'
      '    return names[0]\n'
      '\n'
      '\n'
      'def ai_status():\n'
      '    """给「工具 → 智能推荐」页显示的状态（v1.25.0 反馈 1 后按模型是否装好分三种）。"""\n'
      '    names = list_models()\n'
      '    want = configured_model()\n'
      '    if not names:\n'
      '        return {"engine": "builtin", "label": "内置离线联想引擎",\n'
      '                "detail": f"未检测到本地 Ollama（探测 {OLLAMA_HOST}），使用内置的标签共现联想"\n'
      '                          "（纯本地、无需依赖）。需要更聪明的语义扩词时：启动 Ollama 后执行"\n'
      '                          "「ollama list」查看已装模型，「ollama pull qwen2.5:7b」装一个"\n'
      '                          "（或任意模型），再点一次「检测本地 AI 引擎」即可，全程不出网。"}\n'
      '    shown = "、".join(names[:8])\n'
      '    more = "…" if len(names) > 8 else ""\n'
      '    if want and want not in names:\n'
      '        return {"engine": "builtin", "label": f"内置离线联想引擎（指定模型 {want} 未安装）",\n'
      '                "detail": f"设置里指定的是「{want}」，但本机 Ollama 里没有这个模型，"\n'
      '                          f"已自动降级为内置联想。本机已装：{shown}{more}。"\n'
      '                          f"可在设置里改成上面其中之一，或执行「ollama pull {want}」把它装上。"}\n'
      '    use = want or names[0]\n'
      '    tail = "（自动选取本机第一个）" if not want else "（设置里指定的）"\n'
      '    return {"engine": "ollama", "label": f"本地 Ollama（{use}）{tail}",\n'
      '            "detail": f"离线扩词已启用：会把偏好种子词交给本地模型做语义扩展，全程不出网。\\n"\n'
      '                      f"本机已装 {len(names)} 个模型：{shown}{more}。"}\n'
      '\n'
      '\n'
      'def _ollama_expand(seed_terms, limit=40, timeout=25, model=None):\n'
      '    """让本地模型把种子词扩成同类词（离线）。失败一律返回 []。\n'
      '\n'
      '    v1.25.0（反馈 1）：`model` 不再是「探到谁就用谁」，而是走 resolve_model()\n'
      '    —— 用户在设置里填的模型优先。\n'
      '    """\n'
      '    if not seed_terms:\n'
      '        return []\n'
      '    prompt = (\n'
      '        "你是影视标签推荐助手。下面是用户收藏影片的高频标签/片商/演员名。\\n"\n'
      '        "请再给出 30 个**同类且更具体**的标签词（只输出词，逗号分隔，不要解释、不要编号）。\\n"\n'
      '        "种子：" + "、".join(seed_terms[:60]))\n'
      '    body = json.dumps({\n'
      '        "model": resolve_model(model),\n'
      '        "prompt": prompt,\n'
      '        "stream": False,\n'
      '        "options": {"temperature": 0.4, "num_predict": 220},\n'
      '    }).encode("utf-8")\n')

patch("recommend.py", "recommend 签名加 ai_model",
      '    def recommend(self, limit=24, algo="normal", library=None, exclude_ids=(),\n'
      '                  explore=0.25, diversity=None, progress=None, with_reasons=True):\n',
      '    def recommend(self, limit=24, algo="normal", library=None, exclude_ids=(),\n'
      '                  explore=0.25, diversity=None, progress=None, with_reasons=True,\n'
      '                  ai_model=None):\n')

patch("recommend.py", "exclude 解析容错",
      '        exclude = {int(i) for i in exclude_ids if str(i).isdigit()}\n',
      '        exclude = set()\n'
      '        for i in (exclude_ids or ()):\n'
      '            try:\n'
      '                exclude.add(int(i))\n'
      '            except (TypeError, ValueError):\n'
      '                continue\n')

patch("recommend.py", "候选池真正应用 exclude（根因修复）",
      '        for r in rows:\n'
      '            if r.get("favorite"):\n'
      '                continue                       # 已经收藏的不再推荐\n'
      '            if excl_watched and int(r.get("play_count") or 0) > 0:\n'
      '                continue\n',
      '        for r in rows:\n'
      '            if r.get("favorite"):\n'
      '                continue                       # 已经收藏的不再推荐\n'
      '            # v1.25.0（反馈 3）**根因修复**：`exclude` 上面算出来了，但这个循环里\n'
      '            # 一直没有用它 —— 也就是说「换一批」从 v1.24.0 起实际从未生效，\n'
      '            # 每点一次拿到的还是同一批 24 部（只是顺序可能不同）。补上真正的避让。\n'
      '            if r["id"] in exclude:\n'
      '                continue\n'
      '            if excl_watched and int(r.get("play_count") or 0) > 0:\n'
      '                continue\n')

patch("recommend.py", "AI 扩词传指定模型",
      '            extra = _ollama_expand(seeds)\n',
      '            extra = _ollama_expand(seeds, model=ai_model or rec.get("ai_model"))\n')

patch("recommend.py", "模块级 recommend 按轮次避让",
      'def recommend(page=1, limit=24, algo=None, library=None, progress=None):\n'
      '    """给 UI 用的一步函数：`page` 递增 = 换一批（避开上一批推荐过的）。"""\n'
      '    s = cfg.get_settings()\n'
      '    algo = algo or (s.recommend or {}).get("algo", "normal")\n'
      '    seen = list(s.seen_smart or []) if page > 1 else []\n'
      '    r = Recommender(s)\n'
      '    res = r.recommend(limit=limit, algo=algo, library=library,\n'
      '                      exclude_ids=seen, progress=progress)\n'
      '    ids = [p["id"] for p in res.get("picks", [])]\n'
      '    if ids:\n'
      '        s.remember_smart(ids)\n'
      '    return res\n',
      'def recommend(page=1, limit=24, algo=None, library=None, progress=None):\n'
      '    """给 UI 用的一步函数：`page` 递增 = 换一批。\n'
      '\n'
      '    v1.25.0（反馈 3）：避让范围从「只看上一批」改成「最近 N 轮」—— N 由\n'
      '    「工具 → 智能推荐 → 推荐范围与偏好 → 已经推荐的 N 轮内不再出现」决定\n'
      '    （0 = 不限制）。另外**不管第几页都会避让**：v1.24.x 只在 page > 1 时避让，\n'
      '    于是重新进推荐页（page 回到 1）永远看到同一批。\n'
      '    """\n'
      '    s = cfg.get_settings()\n'
      '    algo = algo or (s.recommend or {}).get("algo", "normal")\n'
      '    excl = s.recent_smart_ids()\n'
      '    r = Recommender(s)\n'
      '    res = r.recommend(limit=limit, algo=algo, library=library,\n'
      '                      exclude_ids=excl, progress=progress,\n'
      '                      ai_model=(s.recommend or {}).get("ai_model"))\n'
      '    ids = [p["id"] for p in res.get("picks", [])]\n'
      '    if ids:\n'
      '        s.push_smart_round(ids)\n'
      '    res["excluded"] = len(excl)\n'
      '    res["round"] = (s.smart_history[-1]["round"] if s.smart_history else 0)\n'
      '    return res\n')

patch("recommend.py", "__all__ 增补",
      '__all__ = ["Recommender", "recommend", "ai_status", "probe_ollama", "DIMS", "dim_cn",\n'
      '           "OLLAMA_URL", "OLLAMA_HOST"]\n',
      '__all__ = ["Recommender", "recommend", "ai_status", "probe_ollama", "list_models",\n'
      '           "resolve_model", "configured_model", "DIMS", "dim_cn",\n'
      '           "OLLAMA_URL", "OLLAMA_HOST"]\n')

# ===========================================================================
# 5) ui_home.py —— 首页三个快捷筛选改为「选中态可见」
# ===========================================================================
patch("ui_home.py", "chips 用 #Seg + checkable",
      '        self._chip_defs = [("recent", "最近添加"), ("favorites", "我的收藏"), ("collections", "合集")]\n'
      '        for key, label in self._chip_defs:\n'
      '            if s.home_modules.get(key):\n'
      '                b = QPushButton(label)\n'
      '                b.setObjectName("Ghost")\n'
      '                b.clicked.connect(lambda _c, k=key: self._apply_chip(k))\n'
      '                tl.addWidget(b)\n',
      '        self._chip_defs = [("recent", "最近添加"), ("favorites", "我的收藏"), ("collections", "合集")]\n'
      '        # v1.25.0（反馈 6）：这三个按钮原来复用 #Ghost，点下去只有一点点极淡的描边，\n'
      '        # 用户反馈「不知道是不是点了这个」。改成 checkable + 独立的 #Seg 样式，\n'
      '        # 选中就是实心强调底 + 亮描边 + 加粗白字；再点一次同一项 = 取消筛选。\n'
      '        self._chip_btns = {}\n'
      '        self._active_chip = None\n'
      '        for key, label in self._chip_defs:\n'
      '            if s.home_modules.get(key):\n'
      '                b = QPushButton(label)\n'
      '                b.setObjectName("Seg")\n'
      '                b.setCheckable(True)\n'
      '                b.setToolTip(f"只看「{label}」的作品（再点一次取消）")\n'
      '                b.clicked.connect(lambda _c, k=key: self._click_chip(k))\n'
      '                tl.addWidget(b)\n'
      '                self._chip_btns[key] = b\n')

patch("ui_home.py", "_load 复位 chip 选中态",
      '        self._media = db.search_media(limit=100000, light=True, top_only=True)\n'
      '        self._view = list(self._media)\n'
      '        self._apply_view()\n',
      '        self._media = db.search_media(limit=100000, light=True, top_only=True)\n'
      '        self._view = list(self._media)\n'
      '        self._set_active_chip(None)      # v1.25.0（反馈 6）：回到全量列表 → 取消选中态\n'
      '        self._apply_view()\n')

patch("ui_home.py", "_click_chip / _set_active_chip",
      '    def _apply_chip(self, key):\n'
      '        if key == "recent":\n',
      '    def _click_chip(self, key):\n'
      '        """点同一个快捷筛选第二次 = 取消筛选，回到全部作品（v1.25.0 反馈 6）。\n'
      '\n'
      '        用 `_media` 这份缓存列表还原，不重新查库 —— 47k 条重查一次要好几秒。\n'
      '        """\n'
      '        if self._active_chip == key:\n'
      '            self._set_active_chip(None)\n'
      '            if self._media:\n'
      '                self._view = list(self._media)\n'
      '                self._apply_view()\n'
      '            else:\n'
      '                self._load()\n'
      '            return\n'
      '        self._apply_chip(key)\n'
      '\n'
      '    def _set_active_chip(self, key):\n'
      '        """维护「同一时刻只有一个亮着」，并同步按钮的 checked 态。"""\n'
      '        self._active_chip = key\n'
      '        for k, b in (getattr(self, "_chip_btns", None) or {}).items():\n'
      '            try:\n'
      '                b.setChecked(k == key)\n'
      '            except RuntimeError:\n'
      '                pass                          # 控件已随页面销毁\n'
      '\n'
      '    def _apply_chip(self, key):\n'
      '        self._set_active_chip(key)\n'
      '        if key == "recent":\n')

print("\n".join(REPORT))
print(f"patch _b 完成：{len(REPORT)} 项")
