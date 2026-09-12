# Demo 修复工作记录（D1–D6）

本文件是本轮修复的持续工作记录。只记事实：做了什么、跑了什么、结果是什么、卡在哪。
最终验收不属于本轮工作，本文件不作任何「通过」声明。

## 目标与范围

把现有五层管线（extract → classify → merge → decide → select）修到能端到端演示：

来源判决 → 引证候选 → 分类与重叠仲裁 → 案件身份 → 案件来源地 → 去重后的外国引证边及频次 → 返回原文与判断依据。

允许 UNKNOWN / UNDETERMINED / CONFLICT；不得用未经核实的判断填满未知项。

本轮修复项：D1（去重按最长占位）、D2（非重叠扫描漏候选）、D3（跨界解析 `2011 ONCA, 2011`）、
D4（括注系列不捕获）、D5（罗马页码丢出键）、D6（来源地只能产出 CA）。
暂缓：D8（历史脚注案名关联）、D9（大规模人工标注）。

方案 A：extract 保留全部候选 → classify 逐候选 → merge 先做判决内重叠仲裁再跨行聚合 →
decide 管身份与来源 → select 保持原 dd 门槛语义。

## 起始状态（2026-09-12）

- 起始提交：`cde643ec8c17a97662da13f44860b9611af5a974`（master）
- 工作区：5 个用户未提交文件，本轮不碰、不提交：
  `audit/glm_prep.py`、`audit/glm_verify.py`、`audit/zcode_recheck.py`、`audit/zcode_recheck2.py`、`audit/zcode_recheck3.py`
- 未找到 AGENTS.md；适用说明为 README.md、USAGE.md、decisions/README.md、技术规格 §12
- 环境：Python 3.11.9（`C:\Users\hp\AppData\Local\Programs\Python\Python311`），pyarrow 25.0.0，PyYAML 6.0.3
- 语料指纹（旧 extract manifest 所记，运行时重新计算）：
  SCC `8e79cd40…6da6`，ONCA `58c31f93…3775`

### 基线测试（改动前，均退出码 0）

| 命令 | 结果 |
|---|---|
| `python pipeline/tests/run_regression.py --selftest` | exit 0，normalize_equivalence 三例 identical |
| `python pipeline/extract.py --fixture-check` | exit 0，A18 / B15 / C27 / D6 / E0 / F0，pass |
| `python pipeline/tests/test_layers.py` | exit 0，120 条断言全部通过 |
| `python pipeline/tests/test_layers.py --golden` | exit 0，与金标一致 |

## 阶段状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 隔离运行入口 + run manifest | **完成**（commit 见 git log） |
| 1 | 候选全量枚举、逐候选分类、判决内重叠仲裁（D1/D2/D3） | 未开始 |
| 2 | 系列与页码身份字段（D4/D5），全量重跑 + 新旧差分 | 未开始 |
| 3 | 来源地最小闭环（D6） | 未开始 |
| 4 | 外国边输出、追溯工具、演示样例、交接 | 未开始 |

## 续跑记录（2026-09-12，第二次会话）

- 本文件与 `pipeline/shapes.py` 的一处未提交修改（D4 捕获组：`series_paren`/`paren_note`，
  只加捕获组不改匹配集合）由上一会话建立；shapes.py 该修改有「2026-09 demo 修复 D4」标记，
  属本任务自己的工作，随后续阶段提交。`audit/` 下 5 个文件属用户，不碰、不提交。
- 基线复测（含 shapes.py 修改后）：
  - `python pipeline/tests/run_regression.py --selftest` → exit 0
  - `python pipeline/extract.py --fixture-check` → exit 0，A18/B15/C27/D6/E0/F0 pass
  - `python pipeline/tests/test_layers.py` → exit 0，120 条断言全部通过
- 依赖版本实测：Python 3.11.9（MSC v.1938 AMD64）、pyarrow 25.0.0、PyYAML 6.0.3。
  本轮**不新增依赖**，故不建 venv：全局环境是用户既有环境，本轮只读不改（隔离手段=
  输出目录隔离，见阶段 0 决定一）。

## 决定记录

（按阶段追加）

### 阶段 0

1. **隔离手段 = 输出目录隔离，不建 venv**：本轮零新增依赖（pyarrow 25.0.0、PyYAML 6.0.3
   已在用户既有环境里），建 venv 只会复制既有解释器、还得重装 550MB 的 pyarrow。
   隔离的实际风险是「新旧批次混跑」，由 run_all 的输出目录规则承担（下条）。
2. **续跑规则**：`--out` 目录必须不存在或为空，否则拒绝启动（绝不把已有目录当可续跑）；
   失败 run 目录原样保留、状态记 failed；重试用新目录。extract 的 progress.json 续跑
   机制在全新目录里天然从零开始。
3. **代码指纹**：`code_fingerprint()` 对 pipeline/*.py（不含 tests/）逐文件 SHA-256 后
   再总哈希——未提交的修改进指纹，git HEAD 单独不够。
4. run_manifest.json 里 status ∈ {running, complete, failed}；非 complete 对下游不是
   完整批次。各层 stdout/stderr 落 step_*.log。

## 运行记录

（按阶段追加：命令、退出码、输出目录）

### 阶段 0

| 命令 | 退出码 | 产物 |
|---|---|---|
| `python pipeline/run_all.py --out data/stage0_smoke --limit-batches 1` | 0 | `data/stage0_smoke/`（run_manifest.json status=complete，9 步全过） |

第一次试跑抓到一个自己的 bug：run_all 定义了 extract 命令却没调 run_step（classify 报
FileNotFoundError 暴露）；修后全过。失败目录两次均已删除重建（规则 2 的重试用新目录）。

## 阻塞与下一步

（按阶段追加）

### 当前

- 下一步：阶段 1 —— extract 全候选枚举（重叠扫描 + 边界闸）、D3 跨界解析标注、
  classify 逐候选、merge 判决内仲裁；全语料同起点不同解析测量。
- 无外部阻塞。
