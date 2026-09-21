# -*- coding: utf-8 -*-
"""写记忆：今天的日志（追加）+ 项目 MEMORY.md（长期硬规则）。

日志 append-only；MEMORY.md 就地插入 3 条「每次都要遵守」的新规则。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
MEM = os.path.join(ROOT, ".workbuddy", "memory")

# ------------------------------------------------------------------ 日志
LOG_ADD = '''
## v1.25.0（已发布，Build 2609210035）用户 6 条反馈 + 修掉 4 处静默失效 + 2 处工具链问题

**6 条反馈与落点**
1. **AI 智能推荐可自填模型** → 「推荐算法」组新增 调用模型 输入框 + 读取本机模型 + 本机模型下拉；页面上写明了「先启动 Ollama，再在命令行执行 `ollama list`」并给 5 个可照抄的示例（`qwen2.5:7b` / `llama3.1:8b` / `qwen3:4b` / `gemma3:12b` / `muse-glimmer:latest`）。解析链 `recommend.resolve_model()`：显式传入 > 设置里填的 > 本机第一个已装 > `llama3` 兜底；**填了但本机没装**时 `probe_ollama()` 直接返 `None`（不再「随便挑一个别的模型照跑」），`ai_status()` 明写「指定模型 X 未安装」+ 列出本机装了哪些 + `ollama pull X`。模型名落盘清洗（`[^0-9A-Za-z_.:/-]`，64 字）。
2. **数据导出/导入页间距** → 该页分组内层行距统一 10，并去掉勾选区原来的 `setSpacing(2)`。
3. **「已经推荐的 N 轮内不再重复出现」** → `QSpinBox` 0–50（默认 3）+ 实时「已记录 N 轮 / 当前避让 M 部」+ 清空推荐历史。**根因**：`Recommender.recommend()` 里 `exclude_ids` 早就被解析成 `exclude` 集合，**但候选池那个 `for r in rows` 循环从头到尾没用过它** —— 「换一批」自 v1.24.0 上线起实际从未生效；而且模块级 `recommend()` 只在 `page > 1` 时才避让，所以「退出推荐页再进来」永远看到同一批。现补真正的避让 + **任何页都避让**。历史按轮存（`smart_history=[{round,ids,ts}]`），保留轮数自动 ≥ `max(20, N*3+5)`。
4. **工具箱新增「标签优化」** → 新增 `src/tagopt.py`（**不 import Qt**，纯计算 + 磁盘 IO，便于离屏单测）+ 工具页（导航里插在「智能推荐」之后）。范围 单一文件 / 文件夹 / 媒体库；算法 普通智能（本地规则）/ AI 智能（叠加本地 Ollama，不可用静默降级，模型与智能推荐页共用）；**两段式** 扫描并预览（只读）→ 执行写入（点前弹确认）；只改 `<genre>` 节点、默认先另存 `*.nfo.bak-<时间戳>`、写完同步 `media.genres`；日语转中文是独立开关且可选**是否覆盖源标签**。词典是**拿真机数据对齐**出来的（`中出し→中出` 22,545 次、`単体作品→单体作品` 27,899 次…）。
5. **12 色高亮 + 选中外发光** → `config.ACCENT_COLORS` 12 组（朱红/绯粉/杏橙/鎏金/竹青/青碧/天青/靛蓝/紫棠/藕荷/玉白/石墨）；实现是 **QSS 令牌替换**（4 个令牌、35 处硬编码色令牌化）+ 模块级 `ACCENT_RGB`（自绘控件同步）；派生档用 **HLS**（只改明度/饱和度）而不是 RGB 等比缩放 —— 原调色板本就不是同一个色的等比缩放，等比会让「描边」偏灰；外发光用 `QGraphicsDropShadowEffect`（blur 38、offset 归零 = 四周均匀）。
6. **首页三个快捷筛选的选中态** → 改 `checkable` + **独立 `#Seg` 样式**（选中 = 实心强调底 + 亮描边 + 加粗白字 + `✓` 对比），同一时刻只有一个亮着，再点同一个即取消筛选。

**写断言 / 读运行日志时才暴露的 4 处静默失效（均已修 + 补断言）**
1. **纯汉字日语标签永远译不出来** —— `tagopt.to_zh()` 一进门就 `if not has_kana(t): return ""`，而词典里一大批条目是纯汉字（`単体作品`/`専属`/`企画`/`大乱交`/`総集编`…）→ 永远命中不了；返回空串时调用方「原样保留」，**界面上完全看不出异常**。改：整串命中词典提到 `has_kana` 之前。真机词表对齐 **16/20 → 17/20**。
2. **裸高亮色令牌被替换成非法 CSS** —— `render_style()` 一律替换成 `"r, g, b"`（因为 QSS 的 `rgba()` 通道位写不了十六进制），但 QSS 里有一部分令牌是**裸用**的（`border: 1px solid __ACCENT_LIGHT__`）→ 变成 `1px solid 224, 82, 67`，**不是合法 CSS，Qt 把整条声明丢掉**（表现为「换了高亮色但某些描边/选中底不跟着变」且不报错）。改：两步替换 —— `rgba(` 内填 `r, g, b`，**剩下的裸令牌输出 `#rrggbb`**。
3. **选中卡片流光定时器「已析构」崩溃**（**不在反馈里，是打包后 grep 真机 app.log 捡到的**）—— `09:25:33`（v1.24.1 Build 0033 的一次真实会话，`09:24:49` 刚做过媒体库扫描）留下 `main_window.py in mousePressEvent → _select_card → set_selected`：`RuntimeError: libshiboken: Internal C++ object (PySide6.QtCore.QTimer) already deleted.` 根因：`set_selected(True)` **每次都新建一个 QTimer 并覆盖旧引用**，旧的那个虽然还挂在卡片下不泄漏，但一旦被析构，`self._timer` 就成了「已析构的 C++ 对象」，下次进来在 `self._timer.stop()` 处直接抛；而扫描/换页会批量 `deleteLater()` 上一批卡片，此时事件队列里恰好还压着投给卡片的鼠标事件。改：**定时器只建一次、之后复用**；`stop()` 包一层 `RuntimeError` 兜底（真析构了就丢引用按需重建）；并把 `MainWindow._selected_card` 的不变式坐实为「**活的卡 或 None**」。
4. **「补全标签」会悄悄删掉技术标签** —— `plan_one()` 的 `before` 取自 `nfo_parser.parse_any()["genres"]`，那个字段是**给卡片徽章用的、已滤掉技术标签**（1080p/HEVC/WEB-DL…）→ 磁盘上的 `<genre>1080p</genre>` 不在 `before` 里，写回时被删，与本模块「原有标签一个不丢」的承诺矛盾。改：新增 `nfo_parser.read_genres()` 读全部 `<genre>` 原文。

**顺带修掉的两处工具链问题（不影响 exe 内容，但都会让人白跑一轮）**
- `build_exe.py` 归档遇到 `history/` 已有同名留档就打印 `[保留]` **原地不动** → 副作用是**根目录每构建一次就多攒一个 48MB 旧包**（构建 0035 前根目录同时躺着 0033 与 0034）。改为 `os.replace` 覆盖那份字节相同的留档（原子；失败退回 `[保留]`）→ 现在根目录只剩最新那一个。
- `dev/live_verify.py` 点**破坏性按钮**会被**模态确认框整段废掉验收**：主窗与工具窗同时被置 `disabled`，之后所有 `PostMessage` 点击**全部静默失效** —— 日志一路写「抓取成功」、截图与上一张逐字节相同、目标文件一个字节没变。更坑的是该确认框的**默认按钮被刻意设成 `No`**（破坏性动作的安全默认），所以「按回车确认」等于取消。现新增 `find_modal()`（门槛放低到 `w>150 and h>80`，否则漏掉 ~420×180 的确认框）+ `bottom_button_centers()`（扫截图底部亮像素聚类定位按钮，**不写死坐标**）+ `confirm_modal_yes()`（点**最左**那个 = Qt 的 Yes）。

**验证**
- `dev/smoke_v1250.py` **292 断言 / 0 失败**（A~J 十段；J 段专钉上面第 3 条崩溃）。`dev/smoke_v1241.py` 回归 105/107（两条失败全部是它自己的版本号断言，属预期）。
- 真机 `dev/live_verify.py`：页面全 1920×1080（首页那张正好验反馈 6 的芯片选中态）、工具 6 页全 1000×900；**「标签优化」在打包版里跑完整回环** —— 扫描 3 个夹具 nfo → 执行写入 → 确认框 → 落盘。事后读回：`中出し` 旁补出 `中出`、**`単体作品` 旁补出 `单体作品`**（第 1 条修复生效）、`潮吹き→潮吹`、`顔射→颜射`，`1080p` **原样保留**（第 4 条修复生效），并推断出 `片商:冒烟社`/`系列:冒烟系列`；`<studio>/<set>/<uniqueid>/<plot>` 与缩进未动；3 份 `*.nfo.bak-20260921103601`。
- 会话日志证据链：`10:30:46 启动 v1.25.0 (Build 2609210035) frozen=True` → `10:32:15 [智能推荐] ai → 24 部` → `10:33:47 [画像概览] 我的收藏：101 部` → `10:36:01 [标签优化] ✓ 完成：写入 3 个 · 跳过 0 个 · 失败 0 个 · 数据库同步 0 条` → `10:38:47 [重复检测] 完成：0 组重复`，**全程 0 条「未捕获异常」**。
- 打包 **`本地影视中心-v1.25.0-2609210035.exe`（48,111,735 B）**，根目录 + `history/` 双份。
- ⚠ **仍待用户确认**：`dev/` 里 26 个与 `history/` 同名的重复 exe（合计 1,179.0 MB）是否可删（历史归档 bug 的遗产）。
'''

lp = os.path.join(MEM, "2026-09-21.md")
with open(lp, encoding="utf-8", newline="") as f:
    s = f.read()
if "## v1.25.0（已发布" in s:
    print("[跳过] 今日日志已有 v1.25.0 段")
else:
    if not s.endswith("\n"):
        s += "\n"
    with open(lp, "w", encoding="utf-8", newline="") as f:
        f.write(s + LOG_ADD.lstrip("\n"))
    print("[OK] 已追加今日日志")


# ------------------------------------------------------------ MEMORY.md
def patch_keep_newline(path, label, old, new):
    with open(path, encoding="utf-8", newline="") as f:
        t = f.read()
    n = t.count(old)
    if n != 1:
        print(f"[失败] {label}: 锚点命中 {n} 次（期望 1）")
        raise SystemExit(1)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(t.replace(old, new, 1))
    print(f"[OK] {label}")


mp = os.path.join(MEM, "MEMORY.md")

patch_keep_newline(
    mp, "MEMORY：流程加 grep app.log",
    "→ `dev/live_verify.py` 真机验收 → 写记忆 → `present_files` 交付。",
    "→ `dev/live_verify.py` 真机验收（**并 grep 真机 `index_data/logs/app.log` 的「未捕获异常」**）→ 写记忆 → `present_files` 交付。",
)

patch_keep_newline(
    mp, "MEMORY：Qt 样式坑加高亮色令牌 + 定时器复用",
    "- `QPropertyAnimation` 必须被 parent/自己持有引用，否则 GC 冻结（圆点卡中位）。悬停浮层用 `Qt.ToolTip|FramelessWindowHint` + `WA_ShowWithoutActivating` + `WA_TransparentForMouseEvents`。",
    """- `QPropertyAnimation` 必须被 parent/自己持有引用，否则 GC 冻结（圆点卡中位）。悬停浮层用 `Qt.ToolTip|FramelessWindowHint` + `WA_ShowWithoutActivating` + `WA_TransparentForMouseEvents`。
- **高亮色（v1.25.0）**：`style.qss` 里 4 个令牌（`__ACCENT__`/`__ACCENT_DARK__`/`__ACCENT_DEEP__`/`__ACCENT_LIGHT__`）+ 模块级 `main_window.ACCENT_RGB`。`render_style()` **必须两步替换**：`rgba(令牌,` 里填 `"r, g, b"`（QSS 的 `rgba()` 通道位不认十六进制），**剩下的裸令牌输出 `#rrggbb`** —— 只做第一步会产出 `1px solid 224, 82, 67` 这种非法声明，Qt **静默丢掉整条**（换色后部分描边/选中底不跟着变、且不报错）。派生档用 **HLS**（只改明度/饱和度）而非 RGB 等比缩放。
- 卡片「选中流光」的 `QTimer` **只建一次、复用**（`set_selected` 里别每次 `new`）；`.stop()` 要包 `RuntimeError` 兜底 —— C++ 侧已析构时 `self._timer` 就是悬空引用，而扫描 / 换页会批量 `deleteLater()` 卡片、此时事件队列里恰好还压着鼠标事件。同理 `MainWindow._selected_card` 的不变式是「**活的卡 或 None**」（长期挂在 `_selected_card` 上的这类引用都要这么维护）。""",
)

patch_keep_newline(
    mp, "MEMORY：探针约定加真机脚本两条",
    "- `_wall_page`/`_view_actor_detail` 等**返回 detached 页面**（parent=None）→ 断言要 `page.findChildren(...)`，搜主窗永远 0。",
    """- `_wall_page`/`_view_actor_detail` 等**返回 detached 页面**（parent=None）→ 断言要 `page.findChildren(...)`，搜主窗永远 0。
- **动过工具窗口导航顺序（`ui_settings.ORDER`）或设置页布局 → 必须重跑 `dev/_scratch/ui_coords.py`**：导航插一页会让后面所有页的 y 整体下移，页内加一行控件也会让按钮漂移；坐标失配是**静默**的（点错页 / 点空），还会白等「重复检测」那 85 秒。
- `dev/live_verify.py` 点**破坏性按钮**必须处理**模态确认框**：不点掉它，主窗与工具窗会同时 `disabled`、后续所有点击静默失效（日志却一路写「抓取成功」）。而且确认框的默认按钮**可能被刻意设成 No**，按回车 = 取消 → 必须 `find_modal()` 找到它、点**最左**那个按钮（Qt 的 Yes）。""",
)

mb = open(mp, "rb").read()
print("MEMORY.md", len(mb), "字节 / CRLF =", mb.count(b"\r\n"))
lb = open(lp, "rb").read()
print("今日日志", len(lb), "字节 / CRLF =", lb.count(b"\r\n"))
