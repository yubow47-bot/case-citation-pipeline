# data/ 目录说明

整个 `data/` 被 gitignore：这里只有派生产物。事实源在 `decisions/`、代码在 `pipeline/`，
被删掉的 run 的身份登记在 **`implementation/run_registry.csv`**（进 git）。

2026-09-15 瘦身：46.8 GB → 约 9.6 GB。原来的 25 个 run/冒烟目录只剩 7 个。

## 现在有什么

| 目录 | 是什么 | 为什么留 |
|---|---|---|
| `run_20260914_r4c/` | **交付 run**，五层 + edges 完整 | 唯一交付物；USAGE §6b 的读法都指着它 |
| `run_20260913_r3e/` | 上一基线，完整 | `r4_invariance_check.py` / `r4_verify_stage4.py` 拿它比 r4c |
| `run_20260912_final/` | 只剩答案层（merge/decide/select + manifest + 日志） | 不可重建；`r2closure_delta.py` 的 Round-1 基线 |
| `run_20260912_stage2/` | 只剩答案层 | 不可重建；`diff_old_new.py`、`traceback.py` 用法示例 |
| `run_20260913_r2g/` | 只剩答案层 | 不可重建；`build_demo_examples.py` |
| `run_20260913_r3d/` | 只剩答案层 | 不可重建；4 个 `_probe_r3d_*.py` |
| `run_20260913_r2d_b/` | 只剩 `sensitivity_*`、`audit/`、manifest、日志 | 敏感性产物由 `r2closure_sensitivity.py` 事后生成，不在 run 指纹内 |
| `extract_out` `classify_out` `merge_out` `decide_out` `select_out` `coverage_out` | 老路线（candidates-1.x）产出 | `test_layers.py --golden` 与 USAGE §8 数字读的就是这里——**别动** |
| `audit/` | 改前快照（`before_task2/3/4`）与测量输出；`scratch_2026-09/` 是 09-09～09-14 的一次性探针 | 审计脚本的输入 |
| `canlii_cache/` | CanLII 列表缓存 | `decisions/tools/build_case_origin.py --offline` 依赖 |
| 根目录 5 个文件 | `corpus_manifest.json`、`.corpus_records.tsv`、`.tree_targets.tsv`、`neutral_triage.json`、`table_coverage.json` | `scripts/download_corpus.sh` 与 audit 脚本按这个路径读写 |

## 被删的 run 怎么找回

```bash
python implementation/rebuild_run.py --list
python implementation/rebuild_run.py run_20260913_r2i
```

可重建的 13 个（r2、r2c、r2d、r2d_b 五层、r2d_c、r2e、r2f、r2h、r2i、r3a、r3c、r4a、r4b）：
工具把登记的提交检出到临时工作树，用那个提交自己的 `run_all.py` 重跑（约 14 分钟），
并核对新 manifest 的输入指纹与登记值一致。2026-09-15 用 r4b 实测过：输入指纹逐字一致；
195 个文件中 174 个数据文件逐字节相同，其余 21 个（各层 manifest.json 与 step 日志）只差
生成时间、输出路径、运行耗时。

不可重建、已删的：r2b、r3b、stage3（当时代码未提交或无 manifest；仅台账提及，无脚本读）、
3 个冒烟目录。它们的结论在 git 提交与会话报告里。

## 保留规则（防止再堆到 47 GB）

每个完整 run 约 2.1 GB。**新 run 交付后：保留新交付 run + 上一基线，更老的那个**
先在 `implementation/run_registry.csv` 登记（提交 + 指纹），再删除。
