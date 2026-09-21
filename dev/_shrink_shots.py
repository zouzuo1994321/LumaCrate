# -*- coding: utf-8 -*-
"""把界面截图缩成宽 860 的 JPG，方便快速读图核对（离屏预览 + 真机验收都吃）。

用法（不带参数 = 两个目录都缩）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/_shrink_shots.py', run_name='__main__')"
    ... _shrink_shots.py 只缩某一个目录

产出：同级 `small/` 子目录里的 `s_<原名>.jpg`。

为什么需要：PNG 有 1~2MB，直接读图既慢又费上下文；缩到宽 860 的 JPG 只要 ~100KB。
**注意读图工具会按路径缓存**：改了源图后若输出同名，读到的可能还是旧图 ——
所以这里统一加 `s_` 前缀，需要重看时换个前缀（或改 SALT）即可绕开缓存。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = [
    os.path.join(ROOT, "dev", "screenshots_v1241"),      # 离屏预览（preview_v1241.py，当前版本）
    os.path.join(ROOT, "dev", "screenshots_v1240"),      # 离屏预览（preview_v1240.py）
    os.path.join(ROOT, "dev", "screenshots"),            # 真机验收（live_verify.py）
]
TARGET_W = 860
SALT = "s_"


def main(argv):
    try:
        from PIL import Image
    except Exception as e:
        print("PIL 不可用：", e)
        return 1
    picked = [d for d in DIRS if (not argv or any(a in d for a in argv))]
    for src_dir in picked:
        if not os.path.isdir(src_dir):
            print("[跳过] 不存在：", src_dir)
            continue
        dst_dir = os.path.join(src_dir, "small")
        os.makedirs(dst_dir, exist_ok=True)
        names = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".png"))
        for n in names:
            im = Image.open(os.path.join(src_dir, n)).convert("RGB")
            if im.width > TARGET_W:
                im = im.resize((TARGET_W,
                                max(1, int(round(im.height * TARGET_W / im.width)))),
                               Image.LANCZOS)
            out = os.path.join(dst_dir, SALT + os.path.splitext(n)[0] + ".jpg")
            im.save(out, "JPEG", quality=84)
            print(f"  {os.path.relpath(out, ROOT)}  {im.size[0]}x{im.size[1]}")
        print(f"[{os.path.relpath(src_dir, ROOT)}] 共 {len(names)} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
