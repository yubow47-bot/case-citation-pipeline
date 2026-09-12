# -*- coding: utf-8 -*-
"""decide_no_gate.py — 把案名支持度闸关掉跑一遍裁定层（审计环，只为重建「设闸前」的产出）

Task 3 的支持度闸改变的是裁定层的分组，要衡量它的净效应就得有一份「不设闸」的产出做
对照。为此不去改生产代码，而是在这里把 `decide.NAME_SUPPORT_BAR` 置 0 再调它的 main()。
**这只是审计仪器**：生产线永远按 `pipeline/decide.py` 里的常量跑。

用法（参数与 decide.py 完全相同）
    python audit/decide_no_gate.py --court SCC --input data/merge_out/SCC/merged.csv \
        --folded-log data/merge_out/SCC/folded_log.csv \
        --decision-ids data/merge_out/SCC/decision_ids.csv --output <目录>
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import decide                                                  # noqa: E402

decide.NAME_SUPPORT_BAR = 0.0                                  # 关闸
if __name__ == "__main__":
    decide.main()
