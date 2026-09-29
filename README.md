<div align="center">

# 🎬 流明盒 (LumaCrate)

**本地影视管理 · Emby 风海报墙 + tinyMediaManager 式关联搜索 · 单文件 exe**

**所有流明 · 尽收盒中** · *Every lumen, in one crate.*

![Version](https://img.shields.io/badge/version-v1.35.0%20\(2609300052\)-c0392b?style=flat-square)

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078d6?style=flat-square\&logo=windows)

![Python](https://img.shields.io/badge/python-3.13-3776ab?style=flat-square\&logo=python)

\!\[Qt\](<https://img.shields.io/badge/UI-PySide6%20(Qt%206\\\\)-41cd52?style=flat-square\\\\\\\&logo=qt>)

![Offline](https://img.shields.io/badge/network-只读nfo%20不联网-2c3e50?style=flat-square)

![License](https://img.shields.io/badge/license-开源·禁止未授权商用-orange?style=flat-square)

</div>

---

## ✨ 它是什么

一个**本地优先**的 Windows 桌面影视管理软件：借鉴 Emby 的海报墙 / 演员 / 详情页，以及 tinyMediaManager 的本地管理与强化关联搜索。全部界面用 PySide6 实现，PyInstaller 打成**单个 exe**，双击即用。

- **纯本地、不联网刮削**：只读取影片目录里已刮削好的 `.nfo`，不访问任何在线元数据服务；片单、番号、演员信息完全留在自己机器上。
- **演员 / 导演独立成表（Emby 模式）**：`people` 表独立存储，可从任意演员 / 导演反查其全部作品。
- **单文件 exe**：`--onefile --windowed`，无需安装、无需 Python。

> Copyright 2026 肆月Aperture · 本软件为开源软件，没有授权禁止用于商业用途。

---

## 📸 界面预览

<p align="center">    
  <img src="logo-3.png" width="200" alt="流明盒 Logo">    
</p>

> 软件以 Emby 风格的海报墙、演员库、详情页呈现。完整界面截图随 GitHub Release 资源发布。

---

## 🎯 功能一览

<details>

<summary><b>浏览与媒体库</b></summary>

| 模块        | 说明                                        |
| --------- | ----------------------------------------- |
| 海报墙 / 媒体库 | 多媒体库管理，海报墙瀑布流浏览；支持收藏（★）与合集                |
| 演员库 / 导演库 | 独立人物档案（`people` 表），可反查作品；支持收藏、按姓名 / 罗马音检索 |
| 详情页       | Emby 风格作品详情：演职员、标签、片商、系列等                 |
| 收藏 / 合集   | 一键收藏（★），合集把跨媒体库的片子归到一组                    |

</details>

<details>

<summary><b>智能推荐</b></summary>

| 模块   | 说明                                                                  |
| ---- | ------------------------------------------------------------------- |
| 重复检测 | 普通算法 + 本地 AI 引擎（Ollama）双模式，揪出重复片                                    |
| 演员检测 | 罗马音归并 / 别名互指 + AI 复核，揪出「不同艺名同一人」                                    |
| 图像检测 | 纯 Python 结构校验，揪出缺图 / 截断图并逐个替换                                       |
| 标签优化 | 基于收藏画像的高频标签 / 片商 / 系列 / 演员 / 导演榜                                    |
| 向量编辑 | 手工编写各维度向量权重；支持「从画像自动填充」与 **「从收藏的演员自动填充」**                           |
| 引导向量 | 在推荐墙输入一个艺人 / 标签 / 片商 / 系列，本次推荐即明显偏向它（**模糊匹配**：含该词的标签 / 片商 / 系列全部加强） |

</details>

<details>

<summary><b>工具与 AI 引擎</b></summary>

| 模块                   | 说明                                                 |
| -------------------- | -------------------------------------------------- |
| 媒体库管理                | 新建 / 编辑 / 删除媒体库，指定扫描路径                             |
| 手动修改                 | 17 项 nfo 字段 + 三槽位上传，写回索引                           |
| 外观                   | 19 种界面语言（即时切换、无需重启）、高亮色、侧栏面板开关                     |
| **AI 引擎设置**（v1.35.0） | 统一管理调用模型、读取本机模型、自动拉起 Ollama（开机自启 + 立即启动），拉起后自动填满下拉 |

</details>

<details>

<summary><b>侧栏与关于</b></summary>

| 模块   | 说明                                              |
| ---- | ----------------------------------------------- |
| 数据统计 | 侧栏底部「数据统计」，可在外观里开关                              |
| 实时状态 | CPU / 内存 / 网络 / GPU / Ollama 采集面板（进程级单例，可开关）    |
| 关于   | 九个模块各自职责、数据存放位置、是否联网、隐私与免责，全部取自 `version.py` 真源 |

</details>

---

## 🚀 下载与运行

**无需安装 Python、无需联网、不依赖浏览器。**

1. 到 [Releases](../../releases) 下载 `流明盒-v1.35.0-2609300052.exe`（约 46 MB，单文件）。
2. 双击运行 —— 首次启动会在 **exe 同目录** 生成 `index_data/`（索引库）与 `settings.json`。
3. 运行期数据生成在 **exe 同目录**，可随 exe 一起移动。

> ⚠️ 因为是 PyInstaller 单文件 exe，部分杀软会误报。源码完全开放，可自行核对或从源码构建。

---

## 🖱️ 怎么用

- **建立媒体库**：工具 → 媒体库 → 新建媒体库，添加本地影片目录（建议目录内已备 `.nfo`）。
- **扫描建索引**：保存后软件读取 nfo 建立本地索引（演员 / 导演 / 标签等）。
- **浏览**：海报墙按媒体库 / 收藏 / 合集切换；演员库、导演库可反查作品。
- **智能推荐**：
  - 向量编辑 → 从画像自动填充 / **从收藏的演员自动填充**，调出你的内容偏好；
  - 推荐墙「引导向量」输入艺人名 / 标签，临时偏向往某方向。
- **AI 引擎**（可选）：基础工具 → AI引擎设置，开启「自动拉起 Ollama」或点「立即启动」，检测本地引擎后在下拉选调用模型。

---

## 📁 目录结构

```
流明盒/
├── 流明盒-v1.35.0-2609300052.exe   # 单文件可执行
├── logo-3.png                     # 品牌图标（金色胶片）
├── logo.ico                       # exe 图标
├── README.md / README_EN.md
├── src/                           # 源码（PySide6）
│   ├── main.py  splash.py  main_window.py
│   ├── version.py  config.py  database.py
│   ├── recommend.py  ui_settings.py  ...
├── build_exe.py                   # 打包脚本
├── dev/                           # 冒烟 / 探针脚本
├── index_data/                    # 运行期生成的索引库与日志（settings.json / media_center.db / logs）
└── history/                       # 历史版本 exe 留档
```

---

## 🛠️ 从源码构建

```bash
# 1) 依赖（建议虚拟环境）
pip install PySide6 pyinstaller

# 2) 直接跑（源码态）
python src/main.py

# 3) 打成单文件 exe
python build_exe.py        # 产出 流明盒-vX.Y.Z-YYMMDDNNNN.exe，落到根目录与 history/
```

- 打包参数（`--onefile --windowed`、图标 `logo.ico`、捆绑 `logo-3.png`）写在 `build_exe.py` 里，不用命令行长参数。
- 最新版 exe 放根目录，历史版本自动归档到 `history/`。

---

## 🧪 开发校验

`dev/` 下为离屏（`QT_QPA_PLATFORM=offscreen`）冒烟脚本，不需要真实显示器：

| 脚本                                              | 作用                                                      |
| ----------------------------------------------- | ------------------------------------------------------- |
| `smoke_v1350.py`                                | v1.35.0 离屏冒烟：模糊解析 / AI引擎设置页 / 向量编辑自动填充等断言 **全过 / 0 失败** |
| `smoke_v1343.py`                                | 模块属性审计与检测页控件断言                                          |
| `live_verify_v1342.py` / `live_verify_v1343.py` | 真机验收：跑真实 exe 并核查 `app.log` 未捕获异常                        |

---

## 📄 许可证

```
Copyright 2026 肆月Aperture
本软件为开源软件，没有授权禁止用于商业用途。
```

第三方组件：

- [PySide6](https://doc.qt.io/qtforpython/) (Qt 6, LGPLv3) — 界面
- [PyInstaller](https://pypi.org/project/pyinstaller) — 单文件打包
- [psutil](https://pypi.org/project/psutil) — 本机指标采集（含 ctypes 兜底，可安全进单文件 exe）

---

## 📮 联系作者

|        |                                    |
| ------ | ---------------------------------- |
| GitHub | <https://github.com/zouzuo1994321> |
| 哔哩哔哩   | <https://space.bilibili.com/13715> |
| 微博     | <https://weibo.com/u/5189652182>   |
| 邮箱     | <921103025@qq.com>                 |

---

## 📚 迭代记录

<details>

<summary><b>v1.35.0 (Build 2609300052) — 2026-09-30</b></summary>

> 三项功能新增（智能推荐 / AI 引擎）

- 智能推荐「推荐算法」简化为「普通 / AI 单选 + 引擎状态 + 检测」模式，模型设置搬到新开的 **AI引擎设置** 页。
- AI 引擎支持 **自动拉起 Ollama**（开机自启 + 立即启动），拉起后自动读本机模型。
- 引导向量 **模糊匹配**：输入不必精确命中 tag，含子串的标签 / 片商 / 系列全部加强。
- 向量编辑新增 **从收藏的演员自动填充**。

</details>

<details>

<summary><b>v1.34.3 (Build 2609260051) — 2026-09-26</b></summary>

- 修复演员检测 / 图像检测运行时 `AttributeError`（构建镜像 7 个陈旧模块整体覆盖到最新快照，全模块属性审计 0 缺失）。
- 标签优化页新增显式「检测本地 AI 引擎」按钮。
- 修复演员检测「最少作品数」SpinBox 与上下箭头重合（统一 `SPIN_MIN_W`/`SPIN_MAX_W` 口径）。

</details>

<details>

<summary><b>v1.34.2 (Build 2609250050) — 2026-09-25</b></summary>

- 收紧「统计范围」组框高度，去掉下方留白（根因：`lb_scope_tip` 误开自动换行被拉伸到 3 行高）。
- 「取前 N 个」上限 200 → 999，并真正支持到 999（面板吞第 3 位 + `insight` 榜单截断两端同修）。

</details>

<details>

<summary><b>v1.34.1 (Build 2609250048) — 2026-09-25</b></summary>

- 三处数值 SpinBox 与边框 / 箭头重叠（style.qss padding 吃掉内容区），统一 `SPIN_MIN_W=131`/`SPIN_MAX_W=160` 口径。
- 统计范围切「我的收藏」高度跳变（提示文案统一两行 + 对话框自适应高度）。
- 引导向量权重框与「加强」按钮挤在一起（同根因修复）。

</details>

<details>

<summary><b>v1.34.0 (Build 2609240047) — 2026-09-24</b></summary>

- 向量编辑「从画像自动填充」改为弹窗可选统计范围 / 取前 N / 权重 / 逐维度启用，并记住偏好。
- 推荐墙新增 **引导向量**：输入艺人 / 标签 / 片商 / 系列，本次推荐临时偏向它。

</details>

<details>

<summary><b>v1.33.x — 2026-09 上旬</b></summary>

- 四页扫描结果可导出 / 导入文件，跨次接着处理。
- 修复演员库 / 导演库 / 最近播放 / 合集工具行右侧白条。
- 删除未实现的「悬停显示预告片」开关。
- 外观新增 19 种界面语言（即时切换、无需重启）。
- 「关于」重写并接入 GitHub / Bilibili / 微博真实 logo 联系图标。

</details>

<details>

<summary><b>v1.32.0 — 2026-09</b></summary>

- 重复 / 图像 / 演员检测统一「普通 + AI」基座 `aireview.py`，新增「极速模式」只复核拿不准的条目。
- 送进模型的提示词做脱敏（不含盘符 / 目录 / 番号 / 文件名）。

</details>

<details>

<summary><b>v1.31.0 — 2026-09</b></summary>

- 工具窗左侧导航按「基础工具 / 数据优化 / 智能检测 / 数据分析」分组。
- 工具新增「演员检测」：普通（罗马音归并 / 别名互指）+ AI 复核，揪出不同艺名同一人。
- 演员卡「三围」前补罩杯并加粗。

</details>

<details>

<summary><b>v1.30.0 — 2026-09</b></summary>

- 工具新增「手动修改」（17 项 nfo 字段 + 三槽位上传写回索引）与「图像检测」（结构校验揪缺图 / 截断图）。
- 演员库 / 导演库右侧 A-Z 字母索引。

</details>

<details>

<summary><b>v1.28.x — 2026-09</b></summary>

- 侧栏「数据统计 / 实时状态」可在外观里开关；侧栏 logo 点开项目主页、底部状态栏点开作者主页。
- 导演卡去「简介」、卡片高度 160 → 118；演员库 / 导演库每行 5 → 6。

</details>

<details>

<summary><b>v1.27.0 — 更名</b></summary>

- 品牌更名 **流明盒 / LumaCrate**，Slogan「所有流明 · 尽收盒中」进启动画面与「关于」。
- 侧栏新增「实时状态」面板（进程级单例采集线程，避免重建崩溃）。

</details>
