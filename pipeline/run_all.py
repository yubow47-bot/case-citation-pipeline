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
import os
import re
import subprocess
import sys

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

COURTS = ("SCC", "ONCA")

# 各层 schema 版本。candidates-2.0 是本轮（D1–D5）的新抽取 schema：旧 kept/superseded
# 路线仍是 extract v1.4 封版口径（--fixture-check 继续钉它），新全候选路线另发版本号，
# 不再声称沿用 v1.4（约束十）。
SCHEMA_VERSIONS = {
    "extract_legacy_kept_superseded": "v1.4 (frozen, diagnostic only)",
    "extract_candidates": "candidates-2.0",
    "classify": "8 + parse/arbitration evidence columns",
    "merge": "9 + in-source arbitration, identity keys v2",
    "decide": "10",
    "select": "11 (threshold semantics unchanged)",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_fingerprint():
    """生产代码内容指纹：pipeline/*.py（不含 tests/）逐文件哈希后再总哈希。
    未提交的修改一样进指纹——git HEAD 单独不足以代表正在跑的代码。"""
    files = sorted(n for n in os.listdir(PIPE)
                   if re.fullmatch(r"[a-z_0-9]+\.py", n))
    per_file = {n: sha256_file(os.path.join(PIPE, n)) for n in files}
    total = hashlib.sha256(
        "".join("%s:%s\n" % (n, per_file[n]) for n in files)
        .encode("utf-8")).hexdigest()
    return {"fingerprint": total, "files": per_file}


def dep_versions():
    out = {"python": sys.version.replace("\n", " ")}
    for mod in ("pyarrow", "yaml"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", "?")
        except ImportError:
            out[mod] = "MISSING"
    return out


class Runner(object):
    def __init__(self, out_root, args):
        self.out = out_root
        self.args = args
        self.manifest_path = os.path.join(out_root, "run_manifest.json")
        self.manifest = None

    def write_manifest(self, status, failed_step=None):
        m = self.manifest or {}
        m.update({
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "failed_step": failed_step or "",
            "schema_versions": SCHEMA_VERSIONS,
            "params": {"batch_size": self.args.batch_size,
                       "year_from": self.args.year_from,
                       "limit_batches": self.args.limit_batches,
                       "courts": list(COURTS),
                       "select_config": "select_config.yaml (verbatim in select manifest)",
                       "threshold_dd_semantics": "unchanged (constraint 6)"},
            "corpus_sha256": {c: sha256_file(os.path.join(ROOT, "corpus", c + ".parquet"))
                              for c in COURTS},
            "code_fingerprint": code_fingerprint(),
            "dependency_versions": dep_versions(),
            "steps_done": m.get("steps_done", []),
            "note": ("complete 之外的 status（running/failed）对下游不是可消费的"
                     "完整批次；失败目录保留，重试用新目录"),
        })
        self.manifest = m
        tmp = self.manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.manifest_path)

    def run_step(self, name, cmd):
        print("[run_all] %s: %s" % (name, " ".join(cmd)))
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable] + cmd, cwd=ROOT,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        log_path = os.path.join(self.out, "step_%s.log" % name)
        with open(log_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("cmd: %s\nexit: %d\n\nstdout:\n%s\n\nstderr:\n%s\n"
                    % (" ".join(cmd), p.returncode, p.stdout, p.stderr))
        if p.returncode != 0:
            self.write_manifest("failed", failed_step=name)
            tail = (p.stderr or p.stdout or "")[-2000:]
            raise SystemExit("step %s 失败（exit %d），日志 %s\n%s"
                             % (name, p.returncode, log_path, tail))
        self.manifest["steps_done"].append(name)
        self.write_manifest("running")

    def check_dir(self):
        if os.path.exists(self.out) and os.listdir(self.out):
            raise SystemExit("输出目录已存在且非空：%s\n"
                             "已有目录绝不当成可续跑的；失败目录保留，重试用新目录。"
                             % self.out)
        os.makedirs(self.out, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True,
                    help="本次运行的输出目录（必须不存在或为空）")
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--limit-batches", type=int, default=None,
                    help="每语料只跑前 N 批（烟雾测试）")
    args = ap.parse_args()

    r = Runner(args.out, args)
    r.check_dir()
    r.write_manifest("running")

    ex = [os.path.join("pipeline", "extract.py"),
          "--out", os.path.join(args.out, "extract_out"),
          "--batch-size", str(args.batch_size)]
    if args.year_from is not None:
        ex += ["--year-from", str(args.year_from)]
    if args.limit_batches is not None:
        ex += ["--limit-batches", str(args.limit_batches)]

    r.run_step("extract", ex)
    # 阶段 1 起：classify/merge 吃 candidates.csv（candidates-2.0 全候选）；
    # extracted.csv / extracted_superseded.csv 降为 v1.4 旧去重路线的诊断产物
    cand_in = os.path.join(args.out, "extract_out", "candidates.csv")
    for court in COURTS:
        r.run_step("classify_" + court,
                   [os.path.join("pipeline", "classify.py"),
                    "--court", court, "--input", cand_in,
                    "--output", os.path.join(args.out, "classify_out", court)])
    for court in COURTS:
        r.run_step("merge_" + court,
                   [os.path.join("pipeline", "merge.py"),
                    "--court", court,
                    "--input", os.path.join(args.out, "classify_out", court,
                                            "classified.csv"),
                    "--output", os.path.join(args.out, "merge_out", court)])
    for court in COURTS:
        r.run_step("decide_" + court,
                   [os.path.join("pipeline", "decide.py"),
                    "--court", court,
                    "--input", os.path.join(args.out, "merge_out", court, "merged.csv"),
                    "--folded-log", os.path.join(args.out, "merge_out", court,
                                                 "folded_log.csv"),
                    "--decision-ids", os.path.join(args.out, "merge_out", court,
                                                   "decision_ids.csv"),
                    "--output", os.path.join(args.out, "decide_out", court)])
    r.run_step("decide_cross",
               [os.path.join("pipeline", "decide.py"), "--cross-court",
                "--inputs"] +
               [os.path.join(args.out, "decide_out", c, "decided.csv")
                for c in COURTS] +
               ["--output", os.path.join(args.out, "decide_out", "cross_court")])
    r.run_step("select",
               [os.path.join("pipeline", "select.py"),
                "--input", os.path.join(args.out, "decide_out", "cross_court",
                                        "decided.csv"),
                "--config", os.path.join(ROOT, "select_config.yaml"),
                "--profile", "default",
                "--output", os.path.join(args.out, "select_out")])
    r.run_step("edges",
               [os.path.join("pipeline", "edges.py"),
                "--decided", os.path.join(args.out, "decide_out", "cross_court",
                                          "decided.csv"),
                "--merge-out", os.path.join(args.out, "merge_out"),
                "--output", os.path.join(args.out, "edges")])

    r.write_manifest("complete")
    print("[run_all] complete -> %s" % r.manifest_path)


if __name__ == "__main__":
    main()
