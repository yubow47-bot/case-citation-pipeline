# data/ 目录说明

整个 `data/` 被 gitignore：这里只有派生产物。事实源在 `decisions/`、代码在 `pipeline/`，
被删掉的 run 的身份登记在 **`implementation/run_registry.csv`**（进 git）。

2026-09-15 瘦身：46.8 GB → 约 9.6 GB。原来的 25 个 run/冒烟目录只剩 7 个。

## 现在有什么（2026-10-03 整理后）

| 目录 | 是什么 | 为什么留 |
|---|---|---|
| `run_20261003_selfcite/` | **当前基线**，五层 + edges 完整（SCC+ONCA+BCCA 主线）。修了 PROBLEMS #105 自引漏网（边 493,463→493,164） | 结果库 `foundation/research.db` 与检索索引都基于它 |
| `run_20261002_tables2/` | 上一基线（#105 修复前） | CanLII 校准的核实样本取自它（`audit/findings/canlii_crosscheck/run_20261002_tables2/`），`CROSSCHECK_RUN` 默认指向它 |
| `foundation/` | 结果库 `research.db`（SQLite，可由 run 重建）、向量缓存 `emb_cache.db`、中文问句改写缓存 `rewrite_cache.db` | 见 `tools/foundation/README.md`；删库不丢数据，重建约 70 秒，向量走缓存几乎不花钱 |
| `foundation_runtime/` | 结果库工具用的 sqlite-vec 与 pyarrow 副本 | `tools/foundation/common.py` 把它排在系统库之后 |
| `run_receipts/` | 已移走的旧 run 里 300 KB 以下的小文件（manifest、各步骤日志、registry 报告、sensitivity 小表）4.9 MB | PROBLEMS.md / 审计报告引用的数字仍能查到出处 |
| `extract_out` `classify_out` `merge_out` `decide_out` `select_out` `coverage_out` | 老路线（candidates-1.x）产出 | `test_layers.py --golden` 与 USAGE §8 数字读的就是这里——**别动** |
| `audit/` | 测量输出与 `scratch_2026-09/` 一次性探针 | 审计脚本的输入。改前快照（`before_task2/3/4`、`ab85_old`、`pre85_r21a`）已移出 |
| `canlii_cache/` | CanLII 列表缓存 | `decisions/tools/build_case_origin.py --offline` 依赖 |
| `recall/` | 经验库索引（SQLite + bge-m3 向量，`tools/recall/` 生成） | 见 `tools/recall/README.md` |
| `glm_audit/` | 外部模型审计产物 | 历史记录 |
| 根目录文件 | `corpus_manifest.json`、`neutral_triage.json`、`table_coverage.json`、三个 `run_*.log` | `scripts/download_corpus.sh` 与 audit 脚本按这个路径读写 |

## 已压缩归档的旧 run（2026-10-03）

14 个旧 run（含 `run_20261002_bilingual`、`D:\_cases_offload` 下全部目录）共 23.2 GB，压成 3.8 GB 的 zip，放在 **`E:\cases_archiveuns\`**（清单 `archive_log.jsonl`）。每个压缩包都测过完整性、文件数与大小和原目录一致，之后才删原目录。还原办法见 `D:\_cases_offload\README.txt`。`audit/jurisdiction_*.py` 写死的 `run_20260918_scc_onca_bcca` 要用得先解压回 `data/`。

## 已移出本目录的 run（2026-10-02，已于 2026-10-03 压缩，下面是当时的记录）

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

每个完整 run 约 2.1–3.3 GB。**新 run 交付后：保留新交付 run + 上一基线，更老的那个**
先在 `implementation/run_registry.csv` 登记（提交 + 指纹），再压缩归档（`E:\cases_archiveuns\`）或删除。
