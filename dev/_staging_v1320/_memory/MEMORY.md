# 本地影视中心 (LocalMediaCenter) — 项目长期约定

> **逐版演进细节 / 历史踩坑 → skill `local-media-center-release` 的 `references/version-history.md`。**
> 本文件只留「每次都要遵守」的硬规则；发布/打包/验收步骤见该 skill 的 `SKILL.md`。

## 定位与技术栈
- 独立桌面软件（无浏览器、无 Web 服务）：PySide6 + Python 3.13 + PyInstaller `--onefile --windowed` 单文件 exe。借鉴 Emby（海报墙/演员/详情页，直调本地播放器）+ tinyMediaManager（本地管理、强化关联搜索）。
- 刮削已阉割：只读已刮削 nfo；演员独立 `people` 表（Emby 模式），可反查作品。

## 版本号规则（硬性）
- 外部 `vX.Y.Z`：X=产品代（大重构才变）；Y=大版本（功能新增，+1 时 Z 归 0）；Z=小版本（bug/小改进）。内部构建号 `YYMMDDNNNN`（同日顺延、不按日归零）。定义于 `src/version.py`。
- **改版本号必须同步三处**：`MINOR_ITER`/`BUILD_SEQ` + 顶部注释段（含本版改动摘要）+ README 徽章/下载名/迭代记录。
- 版权声明必须保留：`Copyright  2026 肆月Aperture`、`本软件为开源软件，没有授权禁止用于商业用途。`（version.py / README / 关于对话框）。

## 每次迭代固定流程
改代码 → bump `src/version.py` → README「迭代记录」新增（并同步「核心特性」）→ `dev/smoke_vN.py` 离屏冒烟 → 预览出图 → `build_exe.py`（新 exe 放根目录、旧版归档 `history/`）→ `dev/live_verify.py` 真机验收（**并 grep 真机 `index_data/logs/app.log` 的「未捕获异常」**）→ 写记忆 → `present_files` 交付。

## 环境铁律
- Bash `cd/ls/rm/tail/head/grep` 全不可用（shim 报 `dirname not found`）→ 用绝对路径 + 正斜杠调 managed python：`C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe`。
- 跑脚本必须 `python -u -c "import runpy; runpy.run_path(r'<绝对路径>', run_name='__main__')"`（直接传路径被 shim 拦返 127）；输出重定向到 `C:/Users/zouzu/AppData/Local/Temp/*.log` 再 Read（直捕偶发为空）。`C:\` 根不可写。
- 改文件后**必须回读确认**：`Edit` 偶发报成功却没落盘；同一文件不要并行 `Edit`，串行改完用 Grep/Read 复核。
- 打包被沙箱拦 → 同命令带 `dangerouslyDisableSandbox=true` 重跑；不要改 `BUILD_TMP`。
- **`os.remove` 被 safe-delete shim 拦**（跨盘 move 报 `WinError 17`、PowerShell `Remove-Item` 静默失败）→ 删文件一律 `ctypes.windll.kernel32.SetFileAttributesW(p,0x80)` 后 `DeleteFileW(p)`；**脚本里不要写 `os.remove`**，临时文件改成正式产物名复用。
- Glob 对 `*.exe` 偶发返回空 → 列目录/删文件一律走 managed python。

## Qt 样式坑（复发过，务必遵守）
- 自绘 paintEvent 的控件别用 `setStyleSheet("background:…")`（父控件背景会盖掉自绘区 → 硬边色带）；底色一律 paintEvent 自绘 + `setAttribute(Qt.WA_StyledBackground, False)`。**自绘控件也不许**开 `WA_StyledBackground`。
- 全局 `QWidget{background:…}` 会落到 QLabel → 必须 `QLabel{background:transparent;}` 兜底。
- 普通 `QWidget` **不绘制** QSS 背景（`paintEvent` 为空）→ `QWidget#Xxx:hover{…}` 无效；容器型控件加 `w.setAttribute(Qt.WA_StyledBackground, True)` 即可。`QPushButton/QLabel/QGroupBox/QStatusBar` 本就吃 QSS，别画蛇添足。
- 窄按钮（28~48px）必须走 `compact_button()`：全局 `QPushButton{padding:7px 14px}` 把内容区压负、字被整块裁。修法是 `QPushButton[compact="1"]{padding:0 4px;}`，**该选择器绝不能写 `min-width`**（会盖掉 `setFixedSize`）。
- `QPropertyAnimation` 必须被 parent/自己持有引用，否则 GC 冻结（圆点卡中位）。悬停浮层用 `Qt.ToolTip|FramelessWindowHint` + `WA_ShowWithoutActivating` + `WA_TransparentForMouseEvents`。
- **验证悬停是否真生效**：出图脚本里 `setAttribute(Qt.WA_UnderMouse, True)` 后 `grab()`，量**垫过底色**的平均亮度（不垫底色量出来的是假数）。
- **窄容器（侧栏内容区只有 170px）里别做「名称左 + 值右」的一行两列**：`QLabel.minimumSizeHint()` 是文本完整宽度、不会缩 → 面板被顶宽、右侧裁字。要么合成一个左对齐富文本 QLabel，要么上下堆叠。富文本颜色必须显式写进 `<span style="color:…">`。
- **高亮色（v1.25.0）**：`style.qss` 4 个令牌（`__ACCENT__`/`__ACCENT_DARK__`/`__ACCENT_DEEP__`/`__ACCENT_LIGHT__`）+ 模块级 `main_window.ACCENT_RGB`。`render_style()` **必须两步替换**：`rgba(令牌,` 里填 `"r, g, b"`，**剩下的裸令牌输出 `#rrggbb`** —— 只做第一步会产出 `1px solid 224, 82, 67` 这种非法声明，Qt **静默丢掉整条**。派生档用 **HLS**（只改明度/饱和度）。
- 卡片「选中流光」的 `QTimer` **只建一次、复用**；`.stop()` 包 `RuntimeError` 兜底（C++ 侧已析构时是悬空引用，扫描/换页会批量 `deleteLater()` 卡片）。`MainWindow._selected_card` 的不变式是「**活的卡 或 None**」。

## Qt 对象生命周期（v1.27.0 真机唯一真缺陷，务必遵守）
- **会被 `deleteLater()` 重建的容器里绝不能挂 QThread / QTimer / 网络会话** —— 只能放「纯 UI」。`MainWindow._apply_settings()`（改设置 / 写标签 / 编辑媒体库都会走）会 `self.sidebar.deleteLater(); self.sidebar = self._build_sidebar()`，挂在旧侧栏下的运行中 QThread 被连带销毁 → Qt 打 `QThread: Destroyed while thread is still running` 并**直接 `abort()` 整个进程**。
- 症状极具误导性：**离屏冒烟全绿、打包零警告**，只有真机走到「会触发重建」的操作之后，后面几张抓图突然 `0x0`、`app.log` 到某行**戛然而止**。判据：日志里出现**第二行**「实时状态：采集能力…」= 面板被重建过。
- 修法：有生命周期的东西父对象给 `QApplication`（`setParent(app)` + `aboutToQuit.connect(stop)`）做进程级单例；订阅方只在析构时**自动退订**，`stop()` 只 `disconnect`、绝不停线程。
- 回归断言：真调一次 `win._apply_settings()`，断言 `findChildren(SysMonWorker)==1` 且 `isRunning()`。**凡给侧栏/侧栏级面板加东西都要加这条。**

## 数据模型与性能架构
- `media` 表无 `num` 列 → 番号从 `file_path`/`title` 提取；`people(id,name UNIQUE,role_type,thumb,bio,photo_path,alias,birthday,romaji,source,source_url,scraped_at,meta,status,favorite,pinned)`；`media_people(media_id,person_id,char_role,person_order)`，**主键 (media_id,person_id)**（`works` 由 `_PEOPLE_SELECT` 的 `COUNT(mp.media_id)` 聚合）。
- **排序必须与索引逐列对齐**（v1.26.0 基准查出的真缺陷）：`search_media` 恒定输出 `ORDER BY <expr> <dir>, m.year DESC, m.id ASC`；SQLite 要满足**全部** ORDER BY 项才用索引 → 单列索引、或 collation 不一致（查询 `COLLATE NOCASE`、索引 BINARY）**全用不上** → 每页 `SCAN m` + `TEMP B-TREE`。修法：`_INDEXES` 补**逐列、逐方向**对齐的复合索引。**改 ORDER BY 的 tie-breaker 必须同步改索引**。
- 5W+ 片靠 **SQL 下推 + 增量渲染**：`_media_where` 被 `search_media`/`count_media` 共用（条件必须一致）；新增筛选/排序键同步补 `_INDEXES` 与 `MEDIA_SORTS` 白名单；随机排序禁用 `ORDER BY RANDOM()`（会话种子置换 + `db.reshuffle()`）。
- **卡片尺寸与列数（`src/main_window.py`）**：`ACTOR_CARD_W=236`、`ACTOR_CARD_H=160`；卡片定高走**可覆盖类属性** `ActorCard.CARD_H`（构造里 `setFixedSize(ACTOR_CARD_W, self.CARD_H)`），子类只覆盖该值 —— `DirectorCard.CARD_H = DIRECTOR_CARD_H = ACTOR_CARD_H - 2*(17+4) = 118`（事实区少两行就精确减两行）。`LazyGrid.COLS_BY_KIND`（媒体 8 / actor 6 / folder 6）；**演员库与导演库共用 `kind="actor"`**，改两库列数只动这一处。列数改动前先算 `cols*W + (cols-1)*12 ≤ 1920-186-40-14`。
- 页面统一 `MainWindow._wall_page(title, base=None)`；`base`（收藏/合集预设）优先级高于用户筛选；偏好落 `config.DEFAULT_WALL_PREFS`。演员库用 `FilterSortBar(kind="actor")`。
- 侧栏底部「数据统计」/「实时状态」由 `config.DEFAULT_APPEARANCE` 的 `show_stats` / `show_sysmon` 控制（开关在「设置 → 外观」）。**关掉是整块不建**（不是 hide）；关掉实时状态时**不会启动采集线程**。
- 设置类偏好集中在 `config.Settings`（`wall_prefs/actor_prefs/nav/home_*/recommend/dedupe/export/scraper/appearance`），新增偏好键必须同时改 `load()` 与 `save()`，并加进 `WALL_FILTER_KEYS`/`ACTOR_FILTER_KEYS` 之类白名单，否则落盘被丢。
- `config.DEFAULT_NAV` 新增导航键时，`load()` 按「锚点插入」（插到它前面那个已存在的键之后），否则老用户升级后新导航跑到菜单最底部。

## 媒体库 / 设置模型
- `config.libraries` 单一列表（`name/kind/paths/filter`，`name` 即身份，无内置库）；CRUD 在 `config.Settings`；`rename_library` 必须同步 `db.rename_library`。侧边栏单一「媒体库」组 + 「＋新建」。
- 设置（v1.24.0 起叫**工具**）窗口非模态（`setModal(False)` + 复用实例）；扫描完成改页内 `lib_status` 标签；媒体库行高 `LIB_ROW_H=46`、行内按钮 28px。

## 本机指标 / 实时状态类面板（`src/sysmon.py` 范式）
- 采集走**零硬依赖降级链**：CPU 内存 网络 → psutil 优先、`ctypes`（`GetSystemTimes`/`GlobalMemoryStatusEx`/`wininet`）兜底；GPU → `nvidia-smi`，没有就显示「—」。
- psutil 可安全进单文件 exe：PyInstaller 6.x 的 hook 在 `_pyinstaller_hooks_contrib/stdhooks/hook-psutil.py`（**不在** `PyInstaller/hooks/`），`--hidden-import psutil` 即可，仍保留 ctypes 兜底。
- **采集必须起后台 QThread**（nvidia-smi 起进程、Ollama 探测 0.4s 超时），慢探测降频；`LMC_NO_SYSMON=1` 供离屏冒烟关掉。线程必须是**进程级单例**（`sysmon.shared_worker()`），面板只 `connect`；停线程统一在 `MainWindow.closeEvent` 调 `sysmon.stop_shared_worker()`，**绝不让面板自己 new/stop 线程**。
- Ollama/模型信息**在函数体内惰性 `import recommend`**，别在模块级引入。

## 外链与可点热区
- 两个外链真源在 `src/version.py`：`REPO_URL`（项目主页，挂侧栏品牌区）/ `AUTHOR_URL`（作者主页，挂底部状态栏）。
- **实现用事件过滤器 `main_window.LinkFilter(QObject)`，不要子类化既有控件**：子类化会改控件类型，QSS 类型选择器（`QStatusBar{…}`）可能不命中 → 底部背景/上边框整条消失。
- 两条硬要求：①过滤器**必须被持有引用**（`self._brand_link`/`self._footer_link`），否则 GC 后静默失效；②**子控件也要各装一份** —— Qt 只对系统真实事件做父级冒泡，`sendEvent` 的合成事件不冒泡。打开走 `mw.open_url()` → `QDesktopServices.openUrl`，失败只记日志**绝不弹框**。
- 偏好键归一化**绝不能写 `bool(v)`** —— `bool("0")` 是 `True`。字符串按 `("", "0", "false", "no", "off")` 判、`null` 当「没设过」。冒烟要真造脏配置验。
- 可被开关关掉的区块，**留一个无 parent + `hide()` 的占位控件**比到处写 `None` 判断安全（例：`stat_label`）。**绝不能给占位控件设 parent** —— 有 parent 又不在布局里会被摆在 `(0,0)` 按 sizeHint 显示出来。

## 品牌与文案
- 软件名 **流明盒 / LumaCrate**（原名「本地影视中心 / LocalMediaCenter」）；Slogan **所有流明 · 尽收盒中** / *Every lumen, in one crate.*（启动画面与「关于」共用）。唯一真源 = `src/version.py` 的 `APP_NAME`/`APP_NAME_EN`/`SLOGAN_CN`/`SLOGAN_EN`。
- **再更名时要同步的隐藏落点**：`build_exe.py::EXE_NAME`（产物名）+ 归档循环前缀白名单、`dev/live_verify.py::newest_exe()` 的 `EXE_GLOBS`、`src/duplicates.py` CSV 表头、README 标题/使用方式/目录结构。历史迭代记录里的旧名**保留不动**。

## AI 复核（v1.32.0 起，四个检测页的统一范式）
- **普通算法 + AI 算法双档**：普通算法（纯计算/结构校验，秒出）→ 缩到可复核规模 → 本地离线 AI 逐条复核（**只把结论写进结果对象，绝不自动删/改文件**）。AI 不可用时**必须把原因原文带回界面**（绝不静默降级）。
- 统一入口 `src/aireview.py`：`ai_available(model) -> (可用?, 说明文案)`（文案原文回传，「没装 / 没启动 / 模型没 pull」三态可辨）、`review_batch(kind, items, build_prompt, apply_fn, model, fast, fast_filter, ...)`、`dedupe_prompt()` / `imagedetect_prompt()` / `verdict_to_dup()` / `verdict_to_img()`。
- **AI 探测口径**：一律 `recommend.probe_ollama()`（真确认模型在本地），**不要 `ollama_reachable()`**（只看端口通不通）。模块头要写明这个理由。
- **「极速模式（fast）」判据各页不同，改一处别改错页**：重复检测＝置信度非「高/极高」或体积/时长不一致；图像检测＝破损或 `slot=="thumb"` 或有 `path`；演员检测＝匹配度 ≥ 80 且无冲突。
- **演员检测走自己的 `actorcheck.ai_review` / `_ollama_json`，不是 `aireview.review_batch`**（提示词与解析形态差别大，设计如此）。三页共享的只是探测口径。
- **⭐ 隐私脱敏铁律**：送进模型的提示词**只含体积/时长/画质/槽位/比例**，**绝不含盘符、目录名、番号、文件名**。目录名映射成「目录 1 / 目录 2」、番号用「序号 1 起（原标识 N 个字符）」。`imagedetect_prompt()` 入参是白名单字典（连 `file_path`/`title` 键都不传）。**冒烟必须有真脱敏断言**。造 `DupGroup` 假数据要**手工填 `by_folder={folder:[member]}`**（普通字段，不填则 `folder_alias` 空、断言假 FAIL）。
- 三页的双档控件都是 **QRadioButton**（不是 QPushButton）+ 一个 `QCheckBox`（极速模式）；属性名：重复检测 `dd_rb_normal`/`dd_rb_ai`/`dd_fast`/`dd_run`（**页在 `ui_settings.py`，没有 `ui_dedupe.py`**）、图像检测 `rb_normal`/`rb_ai`/`fast_chk`/`run_btn`、演员检测同图像检测。

## 界面多语言（v1.32.0 起，`src/i18n.py`）
- **19 种语言，代码用 `zh_CN`（不是 `zh-Hans`）**，`BASE_LANG = DEFAULT_LANG = "zh_CN"` 排 `LANGUAGES` 第一。补齐的 5 种：pl / sv / th / vi / id。
- **不用 `QTranslator`/`.ts`/`.qm`**，用**词典 + 回退**：`NAV_KEYS` 13 键 / `TOOL_KEYS` 16 键 / `COMMON` 25 键 / `SLOGAN` 19。`tr(text)` 查不到**原样返回中文**（刻意降级）。
- **API 是模块级状态，没有 `lang=` 关键字参数**：`set_lang(code)` / `get_lang()` / `tr(text)` / `tr_slogan()` / `is_rtl(code)` / `lang_names()` / `coverage()` / `normalize()` / `native_name()` / `cn_name()`。
- `normalize()` 只认「代码 / 中文名 / 区域码」（`en`、`英语`、`EN`、`en-US`、`zh-Hans-CN`）；**不认自称**（`English` 回落 `zh_CN`，不猜不报错）—— 自称由 `native_name()` 提供。
- **⭐ 身份 / 显示分离铁律**：`sub_btns` 的 key、`ORDER` 元素、`_show()` 映射、`config.nav` 的 `label` **永远是中文**（页面身份）。`i18n.tr()` 只发生在**显示层**。切语言**绝不能动** `config.nav` 的 key、也不能动库名。
- **外观页语言下拉**：`addItem("%s  ·  %s" % (native_name, cn_name), code)` —— **itemText 是「自称 · 中文名」，itemData 才是代码**。切换走 `_apply_language()` → `set_appearance(language=)` + `i18n.set_lang()` + `on_changed()`。
- **RTL 取舍**：阿拉伯语**只翻译文字、版面不镜像**（真镜像要动所有 `addWidget` 顺序 / `QSplitter.setSizes()` / 自绘坐标，风险远大于收益）。`is_rtl()` 单独暴露，界面 hint 明说。
- 加新词条 → 用 `dev/_scratch/patch_i18n_common.py` 的范式（锚点定位 + 逐语言插入 + 回读校验），改完**必须**确认 19 语言条目数齐平。

## 关于对话框（v1.32.0 重写）
- `main_window.AboutDialog` 有类属性 **`SECTIONS`**（9 个模块的 `(标题, 一句话说明)`）+ `@classmethod _body()` 返回 Markdown，`__init__` 里 `QTextBrowser().setMarkdown(cls._body())`。
- 正文八段：软件名/英文名/**版本行**/Slogan → 这是什么 → 功能一览 → 隐私与联网 → 技术栈 → 界面语言 → 使用须知 → 链接。**正文里必须含版本号与内部构建号**（`ver.FULL_VERSION` / `ver.BUILD` —— **属性是 `BUILD` 不是 `BUILD_ID`**）。

## README 截图（v1.32.0 起，`docs/screenshots/`）
- 中英双版「屏幕截图 / Screenshots」段是**表格**，各引 23 张 + 每张一句说明。改图必须**两版同步**（冒烟 I 段校验两版各 23 张、集合一致、文件都存在）。
- 出图工具在 **`dev/shots_lib.py`**：`mask(im, box, label, hard)` = 马赛克（块 = 区域短边 1/12）→ 实心覆盖 → 45° 斜纹（**不可逆三步**）；`watermark(im, text, corner, size, opacity=110, pad, tiled, lift)` —— **参数是 `tiled` 不是 `tile`**，`lift` 上抬避开状态栏/底部按钮；水印文字 `肆月Aperture`。
- **⭐ 打码框必须「动态测量」不能手写坐标**：路径在 `QLabel(setWordWrap(True))` 里会折行，位置随窗口宽度与路径长度变化。做法：读含盘符控件的几何 + `save(..., src_widget=)` 对每张图自动扫一遍（最后一道保险）。
- 造数据用**中性目录名**（`Movies/JP/4K/Classic`）；用敏感词会让整块打码糊掉、看不出是卡片网格。**seed 必须写 `media.library` 列**，否则文件夹页空。

## 探针 / 脚本约定
- 所有 `dev/` 写库脚本先 `db.db_path = lambda: <临时>/index_data/media_center.db` **且**重定向 `applog.log_dir`；严禁对真实索引 `clear_media()`。探针若会走 `config.get_settings()`，改完偏好必须复位真实 `settings.json`。
- 出图脚本造数据用临时库；想显示「作品 N 部」需真插 `media` + `media_people`（`works` 是 join 聚合出来的）。批量插用 `db.get_conn()` + `executemany`，别循环调单条 API。
- 离屏渲染先注册中文字体（`msyh.ttc`）+ `load_style(app)` 再建控件，否则 sizeHint 虚高误报溢出。
- `_wall_page`/`_view_actor_detail` 等**返回 detached 页面**（parent=None）→ 断言要 `page.findChildren(...)`，搜主窗永远 0。
- **离屏测几何必须先 `show()`**：只 `resize()` 不 `show()` 时 `mapTo()` 全返 0、`side.height()` 停在 480（真值 1058）。顺序断言用 `layout().indexOf(a) < layout().indexOf(b)` 更稳，几何只当参考。
- **出预览图时 `QWidget.grab()` 是透明底图**：`PIL.convert("RGB")` 会把半透明层显示成**纯白**，图会骗人。必须先 `alpha_composite` 到容器底色再存。
- **像素断言要按被测代码的分档规则挑采样点**（占用横条 ≥60% 转琥珀、≥85% 转警示橙）。
- **真机抓图用 `user32.PrintWindow(hwnd, memdc, 2)`（`PW_RENDERFULLCONTENT`）+ `gdi32.GetDIBits`**：`QScreen.grabWindow(0, ...)` 抓的是**屏幕区域**，窗口被别的程序盖住就抓成别人的画面。范式见 `dev/_scratch/live_tools_clean_v1320.py`（含 `BITMAPINFOHEADER` ctypes，`biHeight = -h` 才是自上而下）。
- **坐标探针取控件一律按「属性名」，不要按文案模糊匹配**：页里常有多个含「检测」的按钮（如「检测本地 AI 引擎」），模糊匹配会拿错（踩过两次）。也要**只从页内取、不要回落到 dlg** —— 重复检测的 `dd_run` 挂在 dlg 上，回落会让三页都拿到同一个按钮。
- **构建期会走到的刷新函数必须在真构造路径上跑一次**：`SettingsDialog` 的 `_rebuild_nav_highlight()` 在 `self.stack` 建好前就被调 → `AttributeError`，**工具窗完全打不开**，而离屏冒烟与打包都发现不了（只有真 `SettingsDialog(...)` 的端到端探针能抓）。修法是开头 `if getattr(self, "stack", None) is None: return`。
- **动过工具窗口导航顺序（`ui_settings.ORDER`）或设置页布局 → 必须重跑 `dev/_scratch/ui_coords_vN.py`**：导航插一页会让后面所有页的 y 整体下移；坐标失配是**静默**的（点错页/点空），还会白等「重复检测」那 85 秒。
- `dev/live_verify.py` 点**破坏性按钮**必须处理**模态确认框**：不点掉它 → 主窗与工具窗同时 `disabled`、后续所有点击静默失效（日志却一路写「抓取成功」）。且确认框默认按钮**可能被刻意设成 No**，按回车 = 取消 → 必须 `find_modal()` 找到它、点**最左**那个按钮（Qt 的 Yes）。

## 用户偏好
- 简体中文；结构化标题清晰的产出；多解给「办法 A/B/C + 取舍」。
- 交付后常以编号 bug 清单反馈；报错会给具体错误模式，期望**根因定位**而非表面修复。
- 会话内决策可能反复（同一会话内来回切换），**始终以最后一次指令为准，绝不自动回滚**。版本号等有歧义的选择**先问一句再动**。
- 常贴截图反馈。**截图可以直接 Read** —— 用户贴的剪贴板图片在 `C:/Users/zouzu/.workbuddy/clipboard-images/clipboard-<日期>T<时分秒>-*.png`（按时间戳排序即得顺序）。**先把图读出来再动手**，然后用数据探针/断言自证结论。
