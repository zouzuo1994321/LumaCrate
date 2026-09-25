# v1.34.1 (Build 2609250048) 交付暂存

Z 盘根目录的**已存在文件**（README.md / src/*.py / 旧 exe）在本会话里  
一律拒绝改写与删除（ERROR_ACCESS_DENIED 5，Z: 实为 \Nas-1\绿联Nas-1 的 UNC 共享），  
所以把本次改动过的文件**原样另存到这个新目录**，需要时可手工覆盖回根目录。

## 目录内容

- `README.md` / `README_EN.md`：已更新徽章、下载名与 v1.34.1 迭代记录（中英文对照）
- `src/version.py`：v1.34.1 / 2609250048
- `src/config.py`：新增 `SPIN_MIN_W=131` / `SPIN_MAX_W=160`（数值框宽度口径）
- `src/main_window.py`：`guide_w` 不再 setFixedWidth(72)，改按 SPIN_MIN_W 给足
- `src/ui_settings.py`：`AutoFillDialog` 按 sizeHint 自适应高度 + 范围提示锁两行
- `src/style.qss`：数值框上下箭头按钮配色（保留原生箭头，只着色）
- `dev/smoke_v1341.py` / `dev/render_v1341.py` / `dev/_scratch/overlap_v1341.py`：专项冒烟与回归探针

## exe

- 最新版：`Z:/【01】自研软件/【26-19】本地影视中心/流明盒-v1.34.1-2609250048.exe`
- 历史留档：`.../history/流明盒-v1.34.1-2609250048.exe`
- ⚠️ 根目录里的 `流明盒-v1.34.0-2609240047.exe` 我这边删不掉（同样被拒绝访问），    
  已在 history/ 里留了同一份存档，**请手动删除根目录那一份**。
