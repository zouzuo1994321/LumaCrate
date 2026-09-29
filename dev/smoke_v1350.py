# -*- coding: utf-8 -*-
"""v1.35.0 离屏冒烟：验证三项新增功能不崩（构建期）。

仅验证「能建出来 / 逻辑对」，不验证像素级 UI。
- 1) SettingsDialog 能完整构建（含新「AI引擎设置」页），且导航能切到它；
- 2) VectorEditorDialog 能构建（含新的「从收藏的演员自动填充」按钮）；
- 3) recommend.resolve_guide_tokens_fuzzy 模糊解析返回所有含输入子的 tag。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"

from PySide6.QtWidgets import QApplication

# 设置 / 索引重定向到临时目录，绝不碰真实数据
_tmp = tempfile.mkdtemp(prefix="lmc_smoke_v1350_")
os.environ["LMC_CONFIG"] = os.path.join(_tmp, "settings.json")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import database as db
import recommend as rec_mod

# --- 桩：让 resolve_guide_tokens_fuzzy 不依赖真实大库 ---
_FAKE_PEOPLE = [
    {"id": 1, "name": "さつき芽衣", "role_type": "Actor", "works": 30},
    {"id": 2, "name": "巨乳田中", "role_type": "Actor", "works": 5},
    {"id": 3, "name": "名导XX", "role_type": "Director", "works": 8},
]
_FAKE_ROWS = [
    {"genres": "巨乳,超巨乳,爆乳系,OL担当", "studio": "MOODYZ", "collection": "系列A"},
    {"genres": "巨乳,单体位,颜射", "studio": "S1 NO.1 STYLE", "collection": "系列B"},
]


def _fake_people(role):
    if role == "Actor":
        return [p for p in _FAKE_PEOPLE if p["role_type"] == "Actor"]
    return [p for p in _FAKE_PEOPLE if p["role_type"] == "Director"]


def _fake_rows(library=None):
    return _FAKE_ROWS


db.all_people_ordered = _fake_people
db.media_for_insight = _fake_rows

# --- 1) 模糊解析逻辑 ---
cands = rec_mod.resolve_guide_tokens_fuzzy("巨乳")
tags = sorted([k for _t, _d, k in cands if _d in ("tag", "studio", "series")])
print("[模糊解析] 输入『巨乳』命中标签/片商/系列：", tags)
assert "巨乳" in tags, "应命中精确 tag『巨乳』"
assert "超巨乳" in tags, "应命中『超巨乳』（包含子串）"
assert "爆乳系" not in tags, "『爆乳系』不含『巨乳』，不应被包含匹配"
people = [k for _t, _d, k in cands if _d in ("actor", "director")]
print("[模糊解析] 命中的人：", people)
assert "巨乳田中" in people, "输入『巨乳』应前缀命中演员『巨乳田中』"
assert "さつき芽衣" not in people, "『さつき芽衣』与巨乳无关，不应命中"

# 精确/前缀演员应命中
cands_p = rec_mod.resolve_guide_tokens_fuzzy("さつき")
assert "さつき芽衣" in [k for _t, _d, k in cands_p if _d == "actor"], \
    "输入『さつき』应命中演员『さつき芽衣』"

cands2 = rec_mod.resolve_guide_tokens_fuzzy("S")
print("[模糊解析] 输入『S』(1字) 命中数：", len(cands2))
assert len(cands2) == 0, "单字不应泛匹配"


# --- 2) 构建 SettingsDialog（含新页） ---
import config as cfg
app = QApplication.instance() or QApplication(sys.argv)
cfg.get_settings()  # 触发加载（落临时 settings.json）

import ui_settings as ui

dlg = ui.SettingsDialog()
# 导航到新页：确保 _pg_aiengine 已注册且能切换
assert hasattr(dlg, "_pg_aiengine"), "缺少 _pg_aiengine 页"
dlg._show("AI引擎设置")
cur = dlg.stack.currentWidget()
assert cur is dlg._pg_aiengine, "切到 AI引擎设置页失败"
# 关键控件存在性
for attr in ("ae_state", "ae_test", "ae_ed_model", "ae_btn_models",
             "ae_cb_model", "ae_autostart", "ae_launch", "ae_launch_state"):
    assert hasattr(dlg, attr), f"AI引擎设置页缺少控件 {attr}"
print("[设置页] AI引擎设置页构建 OK，控件齐全")

# 智能推荐页简化：不应再含模型输入控件
assert not hasattr(dlg, "ed_ai_model"), "智能推荐页不应再有 ed_ai_model"
assert not hasattr(dlg, "cb_ai_model"), "智能推荐页不应再有 cb_ai_model"
print("[设置页] 智能推荐页已简化为检测方式分组")

# --- 3) 向量编辑对话框构建（含新按钮） ---
ved = ui.VectorEditorDialog(dlg)
assert hasattr(ved, "_autofill_fav"), "向量编辑缺少 _autofill_fav"
print("[向量编辑] 对话框构建 OK，含『从收藏的演员自动填充』")

print("\nSMOKE_V1350_OK")
