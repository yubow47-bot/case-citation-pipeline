# data/ 目录说明

整个 `data/` 被 gitignore：这里只有派生产物。事实源在 `decisions/`、代码在 `pipeline/`，
被删掉的 run 的身份登记在 **`implementation/run_registry.csv`**（进 git）。

2026-09-15 瘦身：46.8 GB → 约 9.6 GB。原来的 25 个 run/冒烟目录只剩 7 个。

## 现在有什么（2026-10-02 整理后）

| 目录 | 是什么 | 为什么留 |
|---|---|---|
| `run_20261002_bilingual/` | **当前基线**，五层 + edges 完整（SCC+ONCA+BCCA 主线，输入表状态 = 提交 `adfef95`） | 2026-10-02 表改动后重跑的对照基线 |
| `run_receipts/` | 已移走的旧 run 里 300 KB 以下的小文件（manifest、各步骤日志、registry 报告、sensitivity 小表）4.9 MB | PROBLEMS.md / 审计报告引用的数字仍能查到出处 |
| `extract_out` `classify_out` `merge_out` `decide_out` `select_out` `coverage_out` | 老路线（candidates-1.x）产出 | `test_layers.py --golden` 与 USAGE §8 数字读的就是这里——**别动** |
| `audit/` | 测量输出与 `scratch_2026-09/` 一次性探针 | 审计脚本的输入。改前快照（`before_task2/3/4`、`ab85_old`、`pre85_r21a`）已移出 |
| `canlii_cache/` | CanLII 列表缓存 | `decisions/tools/build_case_origin.py --offline` 依赖 |
| `recall/` | 经验库索引（SQLite + bge-m3 向量，`tools/recall/` 生成） | 见 `tools/recall/README.md` |
| `glm_audit/` | 外部模型审计产物 | 历史记录 |
| 根目录文件 | `corpus_manifest.json`、`neutral_triage.json`、`table_coverage.json`、三个 `run_*.log` | `scripts/download_corpus.sh` 与 audit 脚本按这个路径读写 |

## 已移出本目录的 run（2026-10-02）

为重跑腾出空间，下列 run 移到了仓库外的 `D:\_cases_offload\`（不在 git，不在本目录）：

- `backup_to_external/run_20260918_scc_onca_bcca`（3.1 GB）：10-02 管辖权证据审计读的就是它。**应拷到移动硬盘**。`audit/jurisdiction_*.py` 与 `audit/canlii_crosscheck/*.py` 里写死了这个路径，用时须先放回 `data/` 或改指向新 run
- `remove/`（约 16 GB）：`run_20260912_final`、`stage2`、`r2d_b`、`r2g`、`r3d`、`r3e`、`r4c`、`r21a`、`85date`、`run_20260918_final`、`smoke_88_89` 与 `audit/` 里的 5 个改前快照。重跑对比完成、确认无人需要后可整体删除
- **注意**：`run_20260916_85date` 与 `run_20260918_final` **不在** `implementation/run_registry.csv`，删除后无法用 `rebuild_run.py` 重建；其余均已登记

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
