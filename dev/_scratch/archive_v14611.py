# -*- coding: utf-8 -*-
"""v1.46.11 封存：给 archive_version.py 传本版摘要。"""
import runpy
import sys

NOTE = (
    "首页两条反馈：①「最近添加」列表右键批量操作——单选/多选（含 Ctrl+A 全选）都出同一套五项："
    "播放选中视频 / 打开视频文件夹 / 刷新数据 / 删除数据 / 删除源文件；多选时每项追加「（N 项）」。"
    "右键落在未选中行上会先改选该行（与系统习惯一致）；点空白处不弹菜单。动作实现全部在主窗口 "
    "_home_bulk()（那里才有 _toast/统计/确认框）：play=播放器 launch+mark_played+refresh_ids；"
    "folder=QDesktopServices 打开所在目录（>3 个目录先确认）；refresh=从库读回并 _set_row；"
    "delete_index 只清索引不动磁盘；delete_files 走 SHFileOperationW + FOF_ALLOWUNDO 进回收站"
    "（双 null 结尾的 pFrom），成功的与本就不存在的清索引、失败项汇总报错，绝不改硬删。"
    "确认框默认按钮固定「取消」（DestructiveRole+RejectRole）。②首页悬停「叠加显示」——根因是"
    "QTableWidgetItem.setToolTip() 与自定义 HoverPreview 浮层同时存在（停够约 1s 系统 tooltip 压在信息卡上），"
    "叠加的第二层还有 HoverCard 底色 rgba(24,20,16,232) 约 9% 透明让列表行文字透上来；"
    "已删 setToolTip 并把 QFrame#HoverCard 底色改成不透明 #17130f，悬停只剩一张实底信息卡"
    "（标题 / ★评分 · 年份 · 时长 / 演员 / 类型 / 制片 / 上映）。"
    "冒烟 292/292、单测 28/28；探针 FAILS: []；真机实测窗口标题 v1.46.11 (Build 2610280113)、"
    "悬停时本进程其它可见窗口仅 1 个（无 tooltip 叠层）、app.log 尾部零未捕获异常、退出 rc=0。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
