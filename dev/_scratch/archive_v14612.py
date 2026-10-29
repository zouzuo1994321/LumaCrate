# -*- coding: utf-8 -*-
"""v1.46.12 封存：给 archive_version.py 传本版摘要。"""
import runpy
import sys

NOTE = (
    "一条反馈：导入 / 导出偏好没有进度，软件直接「未响应」。先查根因（真机实测，不是猜）："
    "两个动作原来都**同步跑在 GUI 线程**，一次导入 7.09s 期间事件循环**一次都不跳**"
    "（50ms 定时器 0 次触发、IsHungAppWindow 28/128 为真），Windows 只要 5 秒不泵消息"
    "就给窗口打「未响应」。7.09s 的构成：import_prefs 4.67s（其中 415 个 nfo 逐个回写"
    "占 4.24s —— 每个文件 exists + ET.parse + tree.write 三次盘操作）+ 结尾 on_changed() "
    "整页刷新 1.73s；导出本身只要 0.07s（所以卡死只发生在导入）。"
    "改法：① prefs.export_prefs/import_prefs 新增 progress(done, total, label) 回调，"
    "按阶段上报（读库 → 建番号索引 → 合并影片 → 合并人物 → 提交），回调返回 True 即中止；"
    "② 新增 PrefsWorker(QThread)，真活挪到后台线程，界面只收信号；"
    "③ 偏好管理组里加一条真进度（不定长 → 定量）+ 阶段与条数 + 「停止」按钮，"
    "中途两个按钮禁用，结束按结果弹汇总（含「已停止，已处理部分已保存」）；"
    "④ 收尾「正在刷新界面…」单独显示 —— _apply_settings() 那 1.73s 是剩下唯一的长任务，"
    "远低于 5 秒阈值；⑤ 关闭工具窗先 request_stop()+wait()，绝不让 QThread 跟着对话框被销毁。"
    "改后真机复测：IsHungAppWindow 0/218 次为真，最长停摆 1.74s 且正好是「正在刷新界面…」。"
    "冒烟 320/320（新增 ㉓ 段 28 条）、单测 28/28；真机 exe v1.46.12 启动 → 开工具窗 → "
    "数据管理页截图确认进度行默认隐藏、两按钮就位；两次运行均 rc=0 且零未捕获异常。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
