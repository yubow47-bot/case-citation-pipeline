# -*- coding: utf-8 -*-
"""把 data/run_* 压成 zip 放到归档盘，校验通过后才删原目录。

沿用 2026-10-03 的归档做法（见 data/README.md、E:\\cases_archive\\runs\\archive_log.jsonl）：
  1. zipfile + DEFLATED 压缩整个目录（相对路径以目录名为根）；
  2. 校验：zip 内文件数 == 原目录文件数，且解压后总字节数（zip 内记录）== 原目录总字节数，
     且 testzip() 无损坏；
  3. 只有校验全部通过才 rmtree 原目录；失败则保留原目录并以非零码退出；
  4. 追加一行到 archive_log.jsonl。

用法：
  python tools/archive_run.py data/run_20261003_v16b data/run_20261003_v16c
  python tools/archive_run.py --dest E:\\cases_archive\\runs --keep-original data/run_X   # 只压不删
不会处理正在运行的 run（manifest status=running 的目录一律拒绝）。
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile


def dir_stats(path):
    n = b = 0
    for root, _, files in os.walk(path):
        for f in files:
            n += 1
            b += os.path.getsize(os.path.join(root, f))
    return n, b


def is_running(path):
    m = os.path.join(path, "run_manifest.json")
    if os.path.exists(m):
        try:
            return json.load(open(m, encoding="utf-8")).get("status") == "running"
        except Exception:
            return False
    return False


def archive(path, dest, keep):
    path = os.path.abspath(path)
    name = os.path.basename(path.rstrip("\\/"))
    if is_running(path):
        print("拒绝：%s 的 manifest 状态是 running" % name)
        return False
    os.makedirs(dest, exist_ok=True)
    zp = os.path.join(dest, name + ".zip")
    if os.path.exists(zp):
        print("拒绝：%s 已存在（不覆盖）" % zp)
        return False
    files0, bytes0 = dir_stats(path)
    t0 = time.time()
    tmp = zp + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for root, _, files in os.walk(path):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.join(name, os.path.relpath(full, path)))
    with zipfile.ZipFile(tmp) as z:
        bad = z.testzip()
        infos = [i for i in z.infolist() if not i.is_dir()]
        files1, bytes1 = len(infos), sum(i.file_size for i in infos)
    ok = bad is None and files1 == files0 and bytes1 == bytes0
    rec = {"source": path, "archive": zp, "files": files0, "bytes": bytes0,
           "zip_bytes": os.path.getsize(tmp), "verified": ok, "seconds": int(time.time() - t0)}
    if not ok:
        os.remove(tmp)
        print("校验失败，保留原目录：%s (bad=%r files %d/%d bytes %d/%d)" %
              (name, bad, files1, files0, bytes1, bytes0))
        return False
    os.rename(tmp, zp)
    with open(os.path.join(dest, "archive_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if not keep:
        shutil.rmtree(path)
    print("OK %s: %d 文件 %.2f GB -> %.2f GB（%ds）%s" % (
        name, files0, bytes0 / 1e9, rec["zip_bytes"] / 1e9, rec["seconds"],
        "，原目录保留" if keep else "，原目录已删"))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--dest", default=r"E:\cases_archive\runs")
    ap.add_argument("--keep-original", action="store_true")
    a = ap.parse_args()
    ok = all([archive(r, a.dest, a.keep_original) for r in a.runs])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
