# -*- coding: utf-8 -*-
"""rebuild_run.py — 按登记的 git 提交原样重建一个已删除的 run

2026-09-15 瘦身：可重建的旧 run 从 data/ 删除，只在 implementation/run_registry.csv
登记「run → 提交 → 参数 → 输入指纹」。要用哪个旧 run，一条命令重建（约 14 分钟）。

用法
    python implementation/rebuild_run.py --list
    python implementation/rebuild_run.py run_20260913_r2i          # → data/run_20260913_r2i
    python implementation/rebuild_run.py run_20260914_r4b --out D:/tmp/r4b \\
        --verify-against data/run_20260914_r4b                        # 逐文件比对

做法
  1. git worktree 把登记的提交检出到临时目录（不动当前工作区）；
  2. 语料复制进去（corpus/ 不入库）；按 run_registry_inputs.json 把每个输入文件还原成
     当年的 LF/CRLF（core.autocrlf 检出会改换行，内容相同但哈希不同）；
  3. 用**该提交自己的** pipeline/run_all.py 跑，参数取登记值；
  4. 新 run_manifest.json 的 input_identity.fingerprint 必须等于登记值——
     不等 = 重建出的不是同一个 run，exit 1；
  5. 删临时工作树。

只重建 run_all.py 的五层产物；run 目录里事后由其他脚本追加的东西（如 r2d_b 的
敏感性产物）不在指纹覆盖范围内，登记表 note 列写明。
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(HERE, "run_registry.csv")
# 每个 run 的逐文件输入哈希（run_manifest.json 的 input_identity），run 目录删了也还在
with open(os.path.join(HERE, "run_registry_inputs.json"), encoding="utf-8") as _f:
    INPUTS = json.load(_f)


def load_registry():
    with open(REGISTRY, encoding="utf-8", newline="") as f:
        return {r["run"]: r for r in csv.DictReader(f)}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(d):
    out = {}
    for base, _, files in os.walk(d):
        for n in files:
            p = os.path.join(base, n)
            out[os.path.relpath(p, d).replace("\\", "/")] = sha256_file(p)
    return out


def verify_against(new, old):
    a, b = tree_hashes(new), tree_hashes(old)
    same = sorted(k for k in a if k in b and a[k] == b[k])
    diff = sorted(k for k in a if k in b and a[k] != b[k])
    only_new = sorted(set(a) - set(b))
    only_old = sorted(set(b) - set(a))
    print("逐文件比对：相同 %d / 不同 %d / 仅新 %d / 仅旧 %d"
          % (len(same), len(diff), len(only_new), len(only_old)))
    for tag, ks in (("不同", diff), ("仅新", only_new), ("仅旧", only_old)):
        for k in ks:
            print("  %s: %s" % (tag, k))
    return diff, only_new, only_old


def restore_eol(wt, files):
    """检出受 core.autocrlf 影响，换行方式可能与当年工作区不同（内容相同、哈希不同）。
    按 run_registry_inputs.json 记录的逐文件哈希，把每个输入文件还原成当年的 LF/CRLF；
    两种都对不上 = 内容真的不同，中止。"""
    for rel, want in files.items():
        p = os.path.join(wt, rel)
        with open(p, "rb") as f:
            b = f.read()
        if hashlib.sha256(b).hexdigest() == want:
            continue
        lf = b.replace(b"\r\n", b"\n")
        for cand in (lf, lf.replace(b"\n", b"\r\n")):
            if hashlib.sha256(cand).hexdigest() == want:
                with open(p, "wb") as f:
                    f.write(cand)
                break
        else:
            raise SystemExit("输入文件与登记哈希不符（非换行差异）：%s" % rel)


def git(*args, **kw):
    return subprocess.run(["git", "-C", ROOT] + list(args), check=True, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", help="输出目录（默认 data/<run>；必须不存在或为空）")
    ap.add_argument("--verify-against", help="与既有 run 目录逐文件比对")
    a = ap.parse_args()

    reg = load_registry()
    if a.list or not a.run:
        for r in reg.values():
            print("%-22s %-14s %s  %s" % (r["run"], r["disposition"],
                                          (r["commit"] or "-")[:7], r["note"]))
        return
    r = reg.get(a.run)
    if r is None:
        raise SystemExit("登记表里没有 %s" % a.run)
    if r["rebuildable"] != "yes":
        raise SystemExit("%s 不可重建：%s" % (a.run, r["note"]))

    out = os.path.abspath(a.out or os.path.join(ROOT, "data", a.run))
    if os.path.exists(out) and os.listdir(out):
        raise SystemExit("输出目录已存在且非空：%s" % out)

    wt = tempfile.mkdtemp(prefix="rebuild_%s_" % a.run)
    os.rmdir(wt)  # git worktree add 要求目标不存在
    print("[rebuild] %s @ %s -> %s" % (a.run, r["commit"][:7], out))
    git("worktree", "add", "--detach", wt, r["commit"])
    try:
        os.makedirs(os.path.join(wt, "corpus"))
        for c in ("SCC", "ONCA"):
            shutil.copy2(os.path.join(ROOT, "corpus", c + ".parquet"),
                         os.path.join(wt, "corpus", c + ".parquet"))
        restore_eol(wt, INPUTS[a.run]["files"])
        cmd = [sys.executable, os.path.join(wt, "pipeline", "run_all.py"),
               "--out", out, "--batch-size", r["batch_size"]]
        if r["year_from"]:
            cmd += ["--year-from", r["year_from"]]
        if r["limit_batches"]:
            cmd += ["--limit-batches", r["limit_batches"]]
        p = subprocess.run(cmd, cwd=wt)
        if p.returncode != 0 and r["status"] != "failed":
            raise SystemExit("run_all 失败（exit %d）" % p.returncode)
    finally:
        # 工作树里只有检出文件和复制来的语料，没有联接点，--force 删除是安全的
        git("worktree", "remove", "--force", wt)

    m = json.load(open(os.path.join(out, "run_manifest.json"), encoding="utf-8"))
    fp = m["input_identity"]["fingerprint"]
    if fp != r["fingerprint"]:
        raise SystemExit("输入指纹不一致：登记 %s / 重建 %s" % (r["fingerprint"], fp))
    print("[rebuild] 输入指纹一致 %s…；status=%s" % (fp[:12], m["status"]))

    if a.verify_against:
        verify_against(out, os.path.join(ROOT, a.verify_against)
                       if not os.path.isabs(a.verify_against) else a.verify_against)


if __name__ == "__main__":
    main()
