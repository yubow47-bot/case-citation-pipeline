# -*- coding: utf-8 -*-
"""run_all.py — 隔离全量运行入口（阶段 0）

一次调用按固定依赖顺序跑完五层：extract → classify → merge → decide（院内×2 + 跨院）
→ select，全部产物落进**显式指定的**输出目录。

用法
    python pipeline/run_all.py --out data/run_20260912_demo
    python pipeline/run_all.py --out data/run_smoke --limit-batches 1   # 烟雾测试

规则（规格 §6，本轮约束）
  * 输出目录必须不存在或为空——已有目录**绝不**被当成可续跑的；失败的 run 目录原样
    保留，重试用新目录。旧 progress.json / last_batch 永不作为续跑依据（extract 在
    全新目录里从零跑，天然满足）。
  * run_manifest.json 记：语料 SHA-256、生产代码内容指纹（未提交的代码也算数，
    git HEAD 不够）、各层 schema 版本、Python/依赖版本、全部归一化参数、逐层状态。
  * 成功收尾时 status=complete；任何一步失败 status=failed 并带失败步骤，目录保留，
    exit 1。失败/半成品目录对下游**永远不是** complete。
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import sys

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from storage import preflight, compact_run, GiB, StorageLimitError
from corpus_fields import POLICY_EN, POLICY_FALLBACK, POLICIES

COURTS = tuple(c for c in os.environ.get("PIPELINE_COURTS", "SCC,ONCA,BCCA").split(",") if c)  # 2026-09-18 用户裁定 BCCA 并入主线语料范围；PIPELINE_COURTS 仍可覆盖（临时/实验用）
ACTIVE_RUNNER = None

# 各层 schema 版本。candidates-2.0 是本轮（D1–D5）的新抽取 schema：旧 kept/superseded
# 路线仍是 extract v1.4 封版口径（--fixture-check 继续钉它），新全候选路线另发版本号，
# 不再声称沿用 v1.4（约束十）。
SCHEMA_VERSIONS = {
    "extract_legacy_kept_superseded": "v1.4 (frozen, diagnostic only)",
    "extract_candidates": "candidates-2.4 + native decision year and bounded following context",
    "classify": "10 + source-verified compound locator and document zones",
    "merge": "10 + in-source arbitration, identity keys v2, bound parallel runs",
    "decide": "17 (conflicted-key guards, ruling uncertainty and source quarantine)",
    "select": "12 (full-data default; optional frequency profiles)",
    "edges": "4 (positive mention provenance; separate source quarantine audit)",
    # #88/#89：run 级全局判决登记簿（merge 之后、decide 之前生成）
    "registry": "3 (native English/French metadata/header proof; canonical source identity)",
    "source_integrity": "1 (native date, source binding, measurable-source disposition)",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# R2-10：输入身份 = 生产代码 + 全部被消费的决策表 + select 配置 + 语料 + 参数/环境。
# 启动时算一次、**不可变**地写进 manifest（后续 manifest 更新绝不重算覆盖）；
# 收尾时重算比对，不一致 → status=failed（不是 complete）。
def input_identity(root=ROOT, courts=COURTS, params=None, corpus_dir=None):
    files = {}
    pipe = os.path.join(root, "pipeline")
    for n in sorted(os.listdir(pipe)):
        if re.fullmatch(r"[a-z_0-9]+\.py", n):
            files["pipeline/" + n] = sha256_file(os.path.join(pipe, n))
    dec = os.path.join(root, "decisions")
    if os.path.isdir(dec):
        for n in sorted(os.listdir(dec)):
            if n.endswith(".csv"):
                files["decisions/" + n] = sha256_file(os.path.join(dec, n))
    cfg = os.path.join(root, "select_config.yaml")
    if os.path.exists(cfg):
        files["select_config.yaml"] = sha256_file(cfg)
    for relative in ("tools/storage.py", "tools/check_run.py"):
        path = os.path.join(root, relative)
        if os.path.isfile(path):
            files[relative] = sha256_file(path)
    consumed = tuple(dict.fromkeys(tuple(courts) + tuple((params or {}).get("anchor_corpus", []))))
    actual_corpus = corpus_dir or os.path.join(root, "corpus")
    for c in consumed:
        p = os.path.join(actual_corpus, c + ".parquet")
        if os.path.exists(p):
            files["corpus/" + c + ".parquet"] = sha256_file(p)
    # #89：锚语料可能来自仓库外的语料目录（实验线只读引用别人的语料，不复制）。
    # 它同样进输入身份——收尾验证要能发现「跑的过程中语料变了」。
    ext = corpus_dir or ""
    if ext and os.path.abspath(ext) != os.path.abspath(os.path.join(root, "corpus")):
        for n in sorted(os.listdir(ext)) if os.path.isdir(ext) else []:
            if n.endswith(".parquet"):
                files["corpus_dir/" + n] = sha256_file(os.path.join(ext, n))
    total = hashlib.sha256(
        ("".join("%s:%s\n" % (k, files[k]) for k in sorted(files))
         + "params:" + json.dumps(params or {}, sort_keys=True, default=str)
         + "\n").encode("utf-8")).hexdigest()
    return {"fingerprint": total, "files": files, "params": params or {}}


def verify_unchanged(start_identity, root=ROOT, courts=COURTS, params=None,
                     corpus_dir=None):
    now = input_identity(root=root, courts=courts, params=params,
                         corpus_dir=corpus_dir)
    return now["fingerprint"] == start_identity["fingerprint"], now


def dep_versions():
    out = {"python": sys.version.replace("\n", " ")}
    for mod in ("pyarrow", "yaml"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", "?")
        except ImportError:
            out[mod] = "MISSING"
    return out


def stop_and_reap(proc):
    """On any guard/communication failure, terminate, escalate, and reap the child.

    A broken communicate() must not prevent wait() from collecting an exited process.
    Cleanup errors are diagnostic data; the original step failure remains the cause.
    """
    errors = []
    stdout = stderr = ''

    def capture(exc):
        nonlocal stdout, stderr
        for key in ('stdout', 'stderr'):
            value = getattr(exc, key, None)
            if value:
                value = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
                if key == 'stdout':
                    stdout = value
                else:
                    stderr = value

    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    except BaseException as exc:
        errors.append('terminate: %s: %s' % (type(exc).__name__, exc))
    try:
        out, err = proc.communicate(timeout=10)
        return out or stdout, err or stderr, errors
    except BaseException as exc:
        capture(exc)
        errors.append('communicate after terminate: %s: %s' % (type(exc).__name__, exc))
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    except BaseException as exc:
        errors.append('kill: %s: %s' % (type(exc).__name__, exc))
    try:
        out, err = proc.communicate(timeout=10)
        return out or stdout, err or stderr, errors
    except BaseException as exc:
        capture(exc)
        errors.append('communicate after kill: %s: %s' % (type(exc).__name__, exc))
    try:
        proc.wait(timeout=10)
    except BaseException as exc:
        errors.append('wait: %s: %s' % (type(exc).__name__, exc))
    return stdout, stderr, errors


class Runner(object):
    def __init__(self, out_root, args, courts=COURTS, anchor_courts=(), reused_upstream=None):
        self.out = out_root
        self.args = args
        self.courts = tuple(courts)
        self.anchor_courts = tuple(anchor_courts)
        self.corpus_dir = os.path.abspath(args.corpus_dir or
                                          os.path.join(ROOT, "corpus"))
        self.manifest_path = os.path.join(out_root, "run_manifest.json")
        self.manifest = None
        # R2-10：启动身份，算一次即冻结；params 一起进指纹
        self.params = {"batch_size": args.batch_size,
                       "year_from": args.year_from,
                       "limit_batches": args.limit_batches,
                       "courts": list(self.courts),
                       # #89：锚语料只供登记簿，不抽取不计数；它进参数 = 进指纹，
                       # 不同锚集合的 run 天然不是同一个输入身份
                       "anchor_corpus": list(self.anchor_courts),
                       "corpus_dir": self.corpus_dir,
                       "text_policy": getattr(args, "text_policy", POLICY_EN),
                       "registry_gate": getattr(args, "registry_gate", "literal"),
                       "parallel_min_sources": getattr(args, "parallel_min_sources", 1),
                       "compact": getattr(args, "compact", True),
                       "storage_budget_gb": getattr(args, "storage_budget_gb", 12),
                       "min_free_gb": getattr(args, "min_free_gb", 2),
                       "mixed_key_holdout": bool(getattr(args, "mixed_key_holdout", False)),
                       "select_config": "select_config.yaml (verbatim in select manifest)",
                       "threshold_dd_semantics": "unchanged (constraint 6)"}
        if reused_upstream is not None:
            self.params["reused_upstream"] = reused_upstream
            self.params["full_scope"] = {key: self.params[key] for key in
                ("batch_size", "year_from", "limit_batches", "courts", "anchor_corpus", "corpus_dir", "text_policy")}
        self.start_identity = input_identity(root=ROOT, courts=self.courts, params=self.params,
                                             corpus_dir=self.corpus_dir)
        self.identity_verified = None

    def write_manifest(self, status, failed_step=None):
        m = self.manifest or {}
        m.update({
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "failed_step": failed_step or "",
            "schema_versions": SCHEMA_VERSIONS,
            "params": self.params,
            # R2-10：启动身份只在这里算一次；后续更新原样携带，绝不重算覆盖
            "input_identity": self.start_identity,
            "input_identity_verified_unchanged": self.identity_verified,
            "dependency_versions": dep_versions(),
            "steps_done": m.get("steps_done", []),
            "note": ("complete 之外的 status（running/failed）对下游不是可消费的"
                     "完整批次；失败目录保留，重试用新目录。status=complete 要求"
                     "收尾时输入身份与启动时逐字节一致（R2-10）"),
        })
        self.manifest = m
        tmp = self.manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.manifest_path)

    def run_step(self, name, cmd):
        print("[run_all] %s: %s" % (name, " ".join(cmd)))
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc, stdout, stderr = None, '', ''
        failure, phase, cleanup_errors = None, 'spawn', []
        try:
            proc = subprocess.Popen([sys.executable] + cmd, cwd=ROOT,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", env=env)
            while True:
                phase = 'communicate'
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    phase = 'storage_monitor'
                    # Stop with headroom before the user-visible project cap.
                    maximum = int(getattr(self.args, "storage_budget_gb", 12) * GiB)
                    preflight(ROOT, 0, max_project_bytes=maximum - min(256 * 1024**2, maximum // 20),
                              min_free_bytes=int(getattr(self.args, "min_free_gb", 2) * GiB))
        except BaseException as exc:
            failure = exc
            if proc is not None:
                stdout, stderr, cleanup_errors = stop_and_reap(proc)
        p = argparse.Namespace(returncode=proc.returncode if proc else None, stdout=stdout, stderr=stderr)
        log_path = os.path.join(self.out, "step_%s.log" % name)
        with open(log_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("cmd: %s\nexit: %s\n\nstdout:\n%s\n\nstderr:\n%s\n"
                    % (" ".join(cmd), p.returncode, p.stdout, p.stderr))
            if failure is not None:
                f.write('\nfailure_phase: %s\nfailure_type: %s\nfailure: %s\nchild_reaped: %s\ncleanup_errors: %s\n' %
                        (phase, type(failure).__name__, failure, proc is None or proc.returncode is not None,
                         json.dumps(cleanup_errors, ensure_ascii=False)))
        if failure is not None:
            self.manifest['step_execution_failure'] = {
                'step': name, 'phase': phase, 'exception': type(failure).__name__, 'message': str(failure),
                'child_reaped': proc is None or proc.returncode is not None, 'cleanup_errors': cleanup_errors}
            if isinstance(failure, StorageLimitError):
                self.manifest["storage_failure"] = str(failure)
                self.write_manifest("failed", failed_step="storage_budget_" + name)
                raise SystemExit("Storage guard stopped step " + name + ": " + str(failure)) from failure
            self.write_manifest("failed", failed_step=phase + '_' + name)
            raise failure
        if p.returncode != 0:
            self.write_manifest("failed", failed_step=name)
            tail = (p.stderr or p.stdout or "")[-2000:]
            raise SystemExit("step %s 失败（exit %d），日志 %s\n%s"
                             % (name, p.returncode, log_path, tail))
        self.manifest["steps_done"].append(name)
        self.write_manifest("running")
        try:
            preflight(ROOT, 0, max_project_bytes=int(getattr(self.args, "storage_budget_gb", 12) * GiB),
                      min_free_bytes=int(getattr(self.args, "min_free_gb", 2) * GiB))
        except BaseException as exc:
            detail = {'step': name, 'phase': 'after_step_storage_monitor', 'exception': type(exc).__name__,
                      'message': str(exc), 'child_reaped': proc.returncode is not None, 'cleanup_errors': []}
            self.manifest['step_execution_failure'] = detail
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write('\nafter_step_storage_monitor_failure: %s\n' % json.dumps(detail, ensure_ascii=False))
            self.write_manifest('failed', failed_step='after_step_storage_monitor_' + name)
            raise

    def check_dir(self):
        if os.path.lexists(self.out) and (os.path.islink(self.out) or getattr(os.lstat(self.out), "st_file_attributes", 0) & 0x400):
            raise SystemExit("Output must not be a link or junction")
        if os.path.exists(self.out) and os.listdir(self.out):
            raise SystemExit("输出目录已存在且非空：%s\n"
                             "已有目录绝不当成可续跑的；失败目录保留，重试用新目录。"
                             % self.out)
        os.makedirs(self.out, exist_ok=True)


def main():
    global ACTIVE_RUNNER
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True,
                    help="本次运行的输出目录（必须不存在或为空）")
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--limit-batches", type=int, default=None,
                    help="每语料只跑前 N 批（烟雾测试）")
    ap.add_argument("--court", action="append", default=None,
                    help="本次实际抽取的法院（可重复）。默认 = 环境变量 "
                         "PIPELINE_COURTS（逗号分隔），再默认 SCC,ONCA,BCCA")
    ap.add_argument("--anchor-corpus", action="append", default=[],
                    help="#89：锚语料法院码（可重复）。该语料**只生成判决登记簿，"
                         "不抽取、不分类、不计数**；不传 = 行为与改动前一致")
    ap.add_argument("--corpus-dir", default=None,
                    help="语料目录（默认仓库 corpus/）；锚语料只读引用，"
                         "实验线用它可以不复制语料")
    # 2026-09-17：用户裁定设为默认开启，与 decide.py 一致（PROBLEMS #88 销账）
    ap.add_argument("--mixed-key-holdout", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="PROBLEMS #88：混合键（提及既印折叠目标的案名、又印别的"
                         "案名）不折叠、抑制案名、退出身份根竞争。默认开启；"
                         "--no-mixed-key-holdout 关闭以复现旧行为")
    ap.add_argument("--registry-gate", default="registered",
                    choices=("literal", "own_or_registry", "registered_only", "registered"),
                    help="#88：登记簿在笔误闸里的参与方式。默认 registered 使用全局"
                         "登记簿保护真实判决编号；其他取值保留供实验与历史复现")
    ap.add_argument("--parallel-min-sources", type=int, default=1)
    ap.add_argument("--compact", action=argparse.BooleanOptionalAction, default=True,
                    help="Verify and gzip output CSVs before completing; default on")
    ap.add_argument('--text-policy', choices=POLICIES, default=POLICY_FALLBACK,
                    help='Prefer English; fall back to French only when English is absent')
    ap.add_argument("--storage-budget-gb", type=float, default=12,
                    help="Project peak budget in GiB; checked before and between steps")
    ap.add_argument("--min-free-gb", type=float, default=2,
                    help="Disk free-space reserve in GiB; checked before and between steps")
    args = ap.parse_args()

    courts = tuple(args.court) if args.court else \
        tuple(c for c in os.environ.get("PIPELINE_COURTS", "").split(",") if c) or COURTS
    anchor_courts = tuple(dict.fromkeys(args.anchor_corpus))
    corpus_dir = os.path.abspath(args.corpus_dir or os.path.join(ROOT, "corpus"))
    target = os.path.realpath(os.path.abspath(args.out))
    data_root = os.path.realpath(os.path.join(ROOT, "data"))
    if os.path.commonpath((target, data_root)) != data_root or os.path.dirname(target) != data_root:
        ap.error("New run must be a direct plain directory in this project's data/ folder")
    if not os.path.basename(target).startswith("run_"):
        ap.error("Run directory name must start with run_")
    if args.parallel_min_sources < 1:
        ap.error("parallel-min-sources must be positive")
    if args.storage_budget_gb <= 0 or args.batch_size <= 0 or (args.limit_batches is not None and args.limit_batches <= 0):
        ap.error("Storage budget, batch size and limit must be positive")
    if not math.isfinite(args.min_free_gb) or args.min_free_gb < 0:
        ap.error("Disk free-space reserve must be finite and nonnegative")
    corpus_bytes = sum(os.path.getsize(os.path.join(corpus_dir, c + ".parquet")) for c in courts)
    estimated = 64 * 1024**2 if args.limit_batches == 1 and args.batch_size <= 20 else max(4 * GiB, 5 * corpus_bytes)
    try:
        budget = preflight(ROOT, estimated, max_project_bytes=int(args.storage_budget_gb * GiB),
                           min_free_bytes=int(args.min_free_gb * GiB))
    except StorageLimitError as exc:
        raise SystemExit("Storage preflight refused the run: " + str(exc))

    r = Runner(args.out, args, courts=courts, anchor_courts=anchor_courts)
    ACTIVE_RUNNER = r
    r.check_dir()
    r.write_manifest("running")
    r.manifest["storage_preflight"] = budget

    source_cmd = [os.path.join("pipeline", "source_integrity.py"),
                  "--corpus-dir", corpus_dir, "--text-policy", args.text_policy,
                  "--out", os.path.join(args.out, "source_integrity"),
                  "--batch-size", str(args.batch_size)]
    if args.limit_batches is not None:
        source_cmd += ["--limit-batches", str(args.limit_batches)]
    for court in courts:
        source_cmd += ["--court", court]
    r.run_step("source_integrity", source_cmd)

    ex = [os.path.join("pipeline", "extract.py"),
          "--out", os.path.join(args.out, "extract_out"),
          "--batch-size", str(args.batch_size)]
    ex += ['--text-policy', args.text_policy]
    if args.year_from is not None:
        ex += ["--year-from", str(args.year_from)]
    if args.limit_batches is not None:
        ex += ["--limit-batches", str(args.limit_batches)]
    if args.corpus_dir:
        ex += ["--corpus-dir", corpus_dir]
    for c in courts:
        ex += ["--corpus", c]
    r.run_step("extract", ex)
    # 阶段 1 起：classify/merge 吃 candidates.csv（candidates-2.0 全候选）；
    # extracted.csv / extracted_superseded.csv 降为 v1.4 旧去重路线的诊断产物
    cand_in = os.path.join(args.out, "extract_out", "candidates.csv")
    for court in courts:
        r.run_step("classify_" + court,
                   [os.path.join("pipeline", "classify.py"),
                    "--court", court, "--input", cand_in,
                    "--output", os.path.join(args.out, "classify_out", court),
                    "--corpus", os.path.join(corpus_dir, court + ".parquet"),
                    "--text-policy", args.text_policy])
    for court in courts:
        r.run_step("merge_" + court,
                   [os.path.join("pipeline", "merge.py"),
                    "--court", court,
                    "--input", os.path.join(args.out, "classify_out", court,
                                            "classified.csv"),
                    "--output", os.path.join(args.out, "merge_out", court)])

    run_downstream(r)
    finalize(r)


def run_downstream(r):
    """Generate registry/decide/select/edges using this Runner and its guards."""
    args, courts, anchor_courts, corpus_dir = r.args, r.courts, r.anchor_courts, r.corpus_dir
    # ---- #88/#89：全局判决登记簿 -------------------------------------------
    # 位置就在「所有合并层跑完之后、第一个裁定层开跑之前」——不打乱层序
    # （约束六）：登记簿是归并层产物的纯读取 + 锚语料的只读构键，不产生任何
    # 上游写入，也不参与抽取/计数。
    reg = [os.path.join("pipeline", "registry.py"),
           "--run-dir", args.out,
           "--extracted-courts", ",".join(courts)]
    reg += ['--text-policy', getattr(r, 'params', {}).get('text_policy', POLICY_EN)]
    if args.corpus_dir:
        reg += ["--corpus-dir", corpus_dir]
    for c in anchor_courts:
        reg += ["--anchor-corpus", c]
    r.run_step("build_registry", reg)
    registry_file = os.path.join(args.out, "registry", "decision_registry.csv")
    own_citations_file = os.path.join(args.out, "registry", "decision_own_citations.csv")

    def decide_cmd(court_args):
        cmd = [os.path.join("pipeline", "decide.py")] + court_args
        # PROBLEMS #105：判决自己印的引证，只用于剔自引（与笔误闸的登记簿无关，总是传）
        cmd += ["--own-citations", own_citations_file, "--corpus-dir", corpus_dir]
        source_records = os.path.join(args.out, "source_integrity", "source_records.csv")
        if os.path.isfile(source_records) or os.path.isfile(source_records + '.gz'):
            cmd += ["--source-records", source_records]
        # Every court consumes the global registry, including the main line.
        cmd += ["--registry", registry_file, "--registry-gate", args.registry_gate,
                "--parallel-min-sources", str(getattr(args, "parallel_min_sources", 1))]
        # PROBLEMS #88：与登记簿无关，单独开关；默认开启（decide.py 同默认），
        # 只在用户显式 --no-mixed-key-holdout 时才需要透传关闭
        if not getattr(args, "mixed_key_holdout", True):
            cmd += ["--no-mixed-key-holdout"]
        return cmd

    for court in courts:
        r.run_step("decide_" + court,
                   decide_cmd(["--court", court,
                               "--input", os.path.join(args.out, "merge_out", court,
                                                       "merged.csv"),
                               "--folded-log", os.path.join(args.out, "merge_out", court,
                                                            "folded_log.csv"),
                               "--decision-ids", os.path.join(args.out, "merge_out", court,
                                                              "decision_ids.csv"),
                               "--history-pairs", os.path.join(args.out, "merge_out", court,
                                                               "history_pairs.csv"),
                               "--parallel-runs", os.path.join(args.out, "merge_out", court, "parallel_runs.csv"),
                               "--output", os.path.join(args.out, "decide_out", court)]))
    r.run_step("decide_cross",
               decide_cmd(["--cross-court", "--inputs"] +
                          [os.path.join(args.out, "decide_out", c, "decided.csv")
                           for c in courts] +
                          ["--history-pairs"] +
                          [os.path.join(args.out, "merge_out", c, "history_pairs.csv")
                           for c in courts] +
                          ["--parallel-runs"] +
                          [os.path.join(args.out, "merge_out", c, "parallel_runs.csv") for c in courts] +
                          ["--output", os.path.join(args.out, "decide_out", "cross_court")]))
    # 天花板监测仪（规格 2.4，必做）：foreign 计数是「登记簿这条数据驱动路径
    # 的边界指示器」——外国法院判决原文在语料里不存在，补语料补不出来。
    r.run_step("registry_report",
               [os.path.join("pipeline", "registry_report.py"),
                "--run-dir", args.out])
    r.run_step("select",
               [os.path.join("pipeline", "select_layer.py"),
                "--input", os.path.join(args.out, "decide_out", "cross_court",
                                        "decided.csv"),
                "--config", os.path.join(ROOT, "select_config.yaml"),
                "--profile", "default",
                "--output", os.path.join(args.out, "select_out")])
    r.run_step("edges",
               [os.path.join("pipeline", "edges.py"),
                "--decided", os.path.join(args.out, "decide_out", "cross_court",
                                          "decided.csv"),
                "--effective", os.path.join(args.out, "decide_out", "cross_court",
                                            "effective_sources.csv"),
                "--merge-out", os.path.join(args.out, "merge_out"),
                "--output", os.path.join(args.out, "edges")])
    r.run_step("coverage_report",
               [os.path.join("pipeline", "coverage_report.py"), "--run-dir", args.out])



def finalize(r, before_seal=None):
    """Verify unchanged inputs, compact new CSVs, seal outputs, then complete."""
    args, courts = r.args, r.courts

    # R2-10：收尾验证——被消费的代码/决策表/配置/语料在运行期间不得变更
    r.identity_verified, _now = verify_unchanged(
        r.start_identity, root=ROOT, courts=courts, params=r.params,
        corpus_dir=r.corpus_dir)
    if not r.identity_verified:
        r.write_manifest("failed", failed_step="input_identity_changed")
        raise SystemExit("输入身份在运行期间发生变化（R2-10）：run 标记 failed，"
                         "不标 complete。重试用新目录。")
    if before_seal is not None:
        before_seal()
    r.write_manifest("finalizing")
    if args.compact:
        r.manifest["storage_compaction"] = compact_run(args.out)
    expected_outputs = {}
    if before_seal is not None:
        expected_outputs = before_seal() or {}
    output_files = {}
    for directory, _, names in os.walk(args.out):
        for name in sorted(names):
            path = os.path.join(directory, name)
            if name == "run_manifest.json" or name.endswith(".tmp"):
                continue
            relative = os.path.relpath(path, args.out).replace(os.sep, "/")
            digest = sha256_file(path)
            if relative in expected_outputs and digest != expected_outputs[relative]:
                raise RuntimeError("Reused output changed while sealing: " + relative)
            output_files[relative] = digest
    r.manifest["output_identity"] = {"files": output_files,
        "fingerprint": hashlib.sha256(json.dumps(output_files, sort_keys=True).encode()).hexdigest()}
    r.identity_verified, _now = verify_unchanged(r.start_identity, root=ROOT, courts=courts,
                                               params=r.params, corpus_dir=r.corpus_dir)
    if not r.identity_verified:
        raise RuntimeError("Inputs changed during finalization; refusing complete status")
    if before_seal is not None:
        before_seal()
    r.write_manifest("complete")
    print("[run_all] complete -> %s" % r.manifest_path)



def mark_active_failed(exc):
    """Both full runs and downstream replay keep the same failed-state contract."""
    if ACTIVE_RUNNER is not None and ACTIVE_RUNNER.manifest is not None \
            and ACTIVE_RUNNER.manifest.get("status") in ("running", "finalizing"):
        ACTIVE_RUNNER.manifest["failure_detail"] = str(exc)
        ACTIVE_RUNNER.write_manifest("failed", failed_step="execution_or_finalization")


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        mark_active_failed(exc)
        raise
