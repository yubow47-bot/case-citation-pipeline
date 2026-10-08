#!/usr/bin/env bash
# download_corpus.sh — 语料快照下载脚本（technical specification §1.3, snapshot policy）
#
# 运行环境: bash（Git Bash / WSL）。本机已实测可用通道为 WSL Ubuntu + curl(OpenSSL)。
# 为何不是 download_corpus.ps1: Windows 自带 curl 使用 schannel，在受限令牌环境下
# TLS 握手失败（SEC_E_NO_CREDENTIALS），Invoke-WebRequest 同根因失败；
# WSL/Git Bash 的 curl(OpenSSL) 实测正常，故以 bash 版为准。
#
# 数据集: HuggingFace a2aj/canadian-case-law
# 目标  : SCC + BCCA + 数据集内全部安大略法域（顶层目录名以 "ON" 开头的法院目录）；
#         设环境变量 PIPELINE_COURTS=SCC,BCCA,... 可改为只下指定的法院目录
#         具体清单以 HF API 枚举实测为准，list 模式先列出供人工确认。
#
# 用法:
#   bash scripts/download_corpus.sh list       # 只枚举清单，不下载
#   bash scripts/download_corpus.sh download   # 下载全部目标到 corpus\
#   bash scripts/download_corpus.sh verify     # 只校验 corpus\ 已有文件（不改写任何文件）
#
# 只读保证（规格 §1.3）:
#   - corpus\ 内已存在的最终文件绝不改写、绝不覆盖:
#       * 指纹吻合 → 跳过，仅登记；
#       * 指纹不符 → 报错退出，交人工处理。
#   - 下载一律先写 "{court}.parquet.part"，完整校验（字节数 + SHA256 + PAR1 魔数）
#     通过后才原子重命名为最终名。corpus\ 中因此永远不会出现半截语料文件。
#   - 断点续传作用于 .part 文件（curl -C -），中断后重跑本脚本即可续传。
#   - .part 已完整（上次下载完但未改名）时直接校验改名，不再请求网络。
#
# 清单: data\corpus_manifest.json（派生产物，gitignore，可由 corpus + API 重建）

set -euo pipefail

MODE="${1:-help}"
REPO="a2aj/canadian-case-law"
REV="main"
UA="citations-corpus-downloader"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPUS="$ROOT/corpus"
DATA="$ROOT/data"
MANIFEST="$DATA/corpus_manifest.json"

command -v curl      >/dev/null 2>&1 || { echo "需要 curl" >&2; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo "需要 sha256sum" >&2; exit 2; }
# On Windows "python3" is often a Microsoft Store stub that fails when run, so try
# each name and keep the first one that actually executes.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "需要 python3（或 python）" >&2; exit 2; }

# --- 枚举：输出 TSV（court, relpath, url, expected_bytes, expected_sha256, dest_name）---
enumerate() {
  "$PY" - "$REPO" "$REV" <<'PYEOF'
import json, os, sys, urllib.request

repo, rev = sys.argv[1], sys.argv[2]
url = f"https://huggingface.co/api/datasets/{repo}/tree/{rev}?recursive=true&expand=true"
entries = []
while url:
    req = urllib.request.Request(url, headers={"User-Agent": "citations-corpus-downloader"})
    with urllib.request.urlopen(req, timeout=120) as r:
        entries.extend(json.load(r))
        link = r.headers.get("Link", "") or ""
    url = None
    for part in link.split(","):
        if 'rel="next"' in part:
            url = part[part.find("<") + 1:part.find(">")]

dirs = [e["path"] for e in entries if e.get("type") == "directory"]
wanted = [c for c in os.environ.get("PIPELINE_COURTS", "").split(",") if c]
if wanted:
    targets = [d for d in dirs if d in wanted]      # 用户显式指定：只下这些法院目录
else:
    targets = [d for d in dirs if d in ("SCC", "BCCA") or d.startswith("ON")]

for court in targets:
    files = sorted(
        (e for e in entries
         if e.get("type") == "file" and e["path"].startswith(court + "/")
         and e["path"].endswith(".parquet")),
        key=lambda e: e["path"])
    if not files:
        sys.exit(f"目标法院目录存在但没有 parquet 文件: {court}")
    for e in files:
        lfs = e.get("lfs") or {}
        size = int(lfs.get("size") or e.get("size") or 0)
        sha = (lfs.get("oid") or "").lower() or "-"
        if len(files) == 1:
            dest = f"{court}.parquet"
        else:
            import re
            m = re.search(r"(\d+)\.parquet$", e["path"])
            n = int(m.group(1)) if m else files.index(e)
            dest = f"{court}.shard{n:02d}.parquet"
        dl = f"https://huggingface.co/datasets/{repo}/resolve/{rev}/{e['path']}"
        print("\t".join([court, e["path"], dl, str(size), sha, dest]))

print(f"# 共 {len(dirs)} 个顶层目录，其中目标 {len(targets)} 个: {' '.join(targets)}",
      file=sys.stderr)
PYEOF
}

TSV="$DATA/.tree_targets.tsv"
mkdir -p "$DATA" "$CORPUS"
echo "枚举数据集: $REPO @$REV ..."
# Python on Windows ends printed lines with CR LF; drop the CR so it does not become part of
# the last field (file names).
enumerate | tr -d '\r' > "$TSV"

echo
echo "数据集全部顶层目录见上方 stderr 注释；目标清单:"
printf "%-10s %-32s %14s %s\n" "COURT" "SOURCE" "BYTES" "DEST"
while IFS=$'\t' read -r court path dl bytes sha dest; do
    printf "%-10s %-32s %14s %s\n" "$court" "$path" "$bytes" "$dest"
done < "$TSV"
echo

if [ "$MODE" = "list" ]; then
    echo "list 模式：未下载。确认上述清单后用 download 执行。"
    exit 0
fi

# --- 校验辅助 ---
magic_ok() {  # parquet 首尾各 4 字节均为 "PAR1"
    [ "$(head -c 4 "$1")" = "PAR1" ] && [ "$(tail -c 4 "$1")" = "PAR1" ]
}

RECORDS="$DATA/.corpus_records.tsv"
: > "$RECORDS"
now() { date +"%Y-%m-%d %H:%M:%S %z"; }

FAILED=0
while IFS=$'\t' read -r court path dl bytes sha dest; do
    dest_path="$CORPUS/$dest"
    if [ -f "$dest_path" ]; then
        got_bytes=$(stat -c %s "$dest_path")
        got_sha=$(sha256sum "$dest_path" | cut -d" " -f1)
        if [ "$got_bytes" = "$bytes" ] && { [ "$sha" = "-" ] || [ "$got_sha" = "$sha" ]; }; then
            echo "[已就位] $dest（$got_bytes 字节，指纹吻合）"
            printf "already_present\t%s\t%s\t%s\t%s\t%s\t%s\n" \
                "$court" "$dest" "$dl" "$got_bytes" "$got_sha" "$(now)" >> "$RECORDS"
            continue
        fi
        echo "只读政策拒绝覆盖: $dest 已存在但指纹与上游不符（本地 $got_bytes 字节 vs 上游 $bytes 字节）。请人工处理后重跑。" >&2
        exit 3
    fi

    if [ "$MODE" = "verify" ]; then
        echo "[缺失] $dest"
        continue
    fi

    part="$dest_path.part"
    # .part 已完整则跳过网络，直接走校验改名
    if [ -f "$part" ] && [ "$(stat -c %s "$part")" = "$bytes" ]; then
        echo "[续用] .part 已完整: $dest"
    else
        echo "[下载] $dl"
        curl -sS --fail --show-error --location --continue-at - --retry 5 --retry-delay 3 \
            --connect-timeout 30 -H "User-Agent: $UA" -o "$part" "$dl" || {
            echo "下载失败: $dl（.part 保留以供续传）" >&2; exit 4; }
    fi

    got_bytes=$(stat -c %s "$part")
    got_sha=$(sha256sum "$part" | cut -d" " -f1)
    if [ "$got_bytes" != "$bytes" ]; then
        echo "字节数不符: $part 实测 $got_bytes vs 上游 $bytes（.part 保留以供续传）" >&2; exit 5
    fi
    if [ "$sha" != "-" ] && [ "$got_sha" != "$sha" ]; then
        echo "SHA256 不符: $part 实测 $got_sha vs 上游 $sha（.part 保留以供续传）" >&2; exit 6
    fi
    if ! magic_ok "$part"; then
        echo "PAR1 魔数校验失败: $part" >&2; exit 7
    fi
    mv "$part" "$dest_path"   # 原子改名：完整校验通过的文件才进入 corpus\
    echo "[完成] $dest（$got_bytes 字节，SHA256 $got_sha）"
    printf "downloaded\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$court" "$dest" "$dl" "$got_bytes" "$got_sha" "$(now)" >> "$RECORDS"
done < "$TSV"

# --- 清单（python3 生成合法 JSON）---
if [ -s "$RECORDS" ]; then
    "$PY" - "$RECORDS" "$MANIFEST" "$REPO" "$REV" <<'PYEOF'
import csv, json, sys, datetime

records_tsv, manifest_path, repo, rev = sys.argv[1:5]
rows = []
with open(records_tsv, newline="", encoding="utf-8") as f:
    for action, court, file, url, b, sha, at in csv.reader(f, delimiter="\t"):
        rows.append({"action": action, "court": court, "file": file, "source_url": url,
                     "bytes": int(b), "sha256": sha, "recorded_at": at, "verified": True})
manifest = {"repo": repo, "revision": rev,
            "manifest_written_at": datetime.datetime.now(datetime.timezone.utc)
                                   .astimezone().isoformat(timespec="seconds"),
            "files": rows}
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"清单已写入: {manifest_path}")
PYEOF
fi

echo "全部完成。"
