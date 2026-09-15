<#
cleanup_execute.ps1 — 2026-09-15 瘦身（按 implementation/run_registry.csv 执行）

  .\cleanup_execute.ps1            # 只列出将要做的事，不动任何文件
  .\cleanup_execute.ps1 -Execute   # 真正执行

按登记表 disposition 列：
  delete        整个 run 目录删除（可重建的用 implementation/rebuild_run.py 重建）
  keep_answers  只删 extract_out + classify_out，其余（答案层、manifest、日志）保留
  keep_extras   删五层产物，保留事后追加的 sensitivity_* / audit/ / manifest / 日志
  keep_whole    不动
另外：删 data/audit/before_capfix（无引用）、空目录 tmp_r3_scratch、各处 __pycache__；
data 根的 35 个散落文件**移动**到 data/audit/scratch_2026-09/（不删）。

保护：每个目标必须在 data/ 或本项目内、不含任何 git 跟踪文件；keep_whole 的 run 必须
完整存在；可重建 run 的 manifest 指纹必须等于登记值（确认删的就是登记的那个）。
任一检查失败 → 什么都不删。
#>
[CmdletBinding()]
param([switch]$Execute)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Data = Join-Path $Root "data"
$Reg = Import-Csv -LiteralPath (Join-Path $Root "implementation\run_registry.csv") -Encoding UTF8

function Size-Of($p) {
    if (-not (Test-Path -LiteralPath $p)) { return 0 }
    $s = (Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue |
          Measure-Object Length -Sum).Sum
    if ($s) { $s } else { 0 }
}

# ---- 计划 -------------------------------------------------------------------
$remove = New-Object System.Collections.Generic.List[string]
$problems = New-Object System.Collections.Generic.List[string]

foreach ($r in $Reg) {
    $dir = Join-Path $Data $r.run
    switch ($r.disposition) {
        "keep_whole" {
            if (-not (Test-Path -LiteralPath (Join-Path $dir "run_manifest.json"))) {
                $problems.Add("keep_whole 缺失: $($r.run)")
            }
        }
        "delete" {
            if (-not (Test-Path -LiteralPath $dir)) { continue }
            if ($r.rebuildable -eq "yes") {
                $m = Get-Content -LiteralPath (Join-Path $dir "run_manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($m.input_identity.fingerprint -ne $r.fingerprint) {
                    $problems.Add("指纹与登记不符: $($r.run)")
                }
            }
            $remove.Add($dir)
        }
        "keep_answers" {
            foreach ($s in "extract_out", "classify_out") {
                $p = Join-Path $dir $s
                if (Test-Path -LiteralPath $p) { $remove.Add($p) }
            }
        }
        "keep_extras" {
            foreach ($s in "extract_out", "classify_out", "merge_out", "decide_out", "select_out", "edges") {
                $p = Join-Path $dir $s
                if (Test-Path -LiteralPath $p) { $remove.Add($p) }
            }
        }
        default { $problems.Add("未知 disposition: $($r.run) = $($r.disposition)") }
    }
}

# 登记表之外的 run 目录不允许存在（防止漏登记的被误留或误删）
Get-ChildItem -LiteralPath $Data -Directory | Where-Object {
    $_.Name -like "run_*" -or $_.Name -like "*smoke"
} | ForEach-Object {
    if (-not ($Reg | Where-Object run -eq $_.Name)) { $problems.Add("登记表外的 run 目录: $($_.Name)") }
}

$capfix = Join-Path $Data "audit\before_capfix"
if (Test-Path -LiteralPath $capfix) { $remove.Add($capfix) }
$tmpScratch = Join-Path $Root "tmp_r3_scratch"
if ((Test-Path -LiteralPath $tmpScratch) -and -not (Get-ChildItem -LiteralPath $tmpScratch -Force)) {
    $remove.Add($tmpScratch)
}
Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -Filter "__pycache__" |
    Where-Object { $_.FullName -notlike "*\.git\*" } | ForEach-Object { $remove.Add($_.FullName) }

# 这 5 个被 download_corpus.sh / audit 脚本按 data\ 根路径读写，留在原处
$stayInRoot = @("README.md", "corpus_manifest.json", ".corpus_records.tsv", ".tree_targets.tsv",
                "neutral_triage.json", "table_coverage.json")
$scratchFiles = @(Get-ChildItem -LiteralPath $Data -File -Force | Where-Object { $stayInRoot -notcontains $_.Name })
$scratchDest = Join-Path $Data "audit\scratch_2026-09"

# ---- 保护检查 ---------------------------------------------------------------
$tracked = @(git -C $Root ls-files)
foreach ($p in $remove) {
    $full = [System.IO.Path]::GetFullPath($p)
    if (-not $full.StartsWith($Root + "\")) { $problems.Add("不在项目内: $full") }
    $rel = $full.Substring($Root.Length + 1).Replace("\", "/")
    if ($tracked | Where-Object { $_ -eq $rel -or $_.StartsWith($rel + "/") }) {
        $problems.Add("含 git 跟踪文件: $rel")
    }
}

# ---- 报告 -------------------------------------------------------------------
$total = 0
Write-Host ""
Write-Host "=== 将删除（$($remove.Count) 项）===" -ForegroundColor Cyan
foreach ($p in $remove) {
    $s = Size-Of $p; $total += $s
    Write-Host ("  {0,9:N0} MB  {1}" -f ($s / 1MB), $p.Substring($Root.Length + 1))
}
Write-Host ("合计释放约 {0:N1} GB" -f ($total / 1GB)) -ForegroundColor Yellow
Write-Host ""
Write-Host "=== 将移动到 data\audit\scratch_2026-09\（不删）：$($scratchFiles.Count) 个散落文件 ===" -ForegroundColor Cyan
Write-Host ""

if ($problems.Count) {
    Write-Host "检查未通过，什么都没做：" -ForegroundColor Red
    $problems | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}
Write-Host "保护检查全部通过。" -ForegroundColor Green

if (-not $Execute) {
    Write-Host "这只是预览。确认无误后运行： .\cleanup_execute.ps1 -Execute" -ForegroundColor Green
    exit 0
}

# ---- 执行 -------------------------------------------------------------------
$free0 = (Get-PSDrive D).Free
New-Item -ItemType Directory -Path $scratchDest -Force | Out-Null
foreach ($f in $scratchFiles) { Move-Item -LiteralPath $f.FullName -Destination $scratchDest }
$failed = 0
foreach ($p in $remove) {
    try { Remove-Item -LiteralPath $p -Recurse -Force; Write-Host "  已删 $($p.Substring($Root.Length + 1))" }
    catch { $failed++; Write-Host "  失败 $p : $($_.Exception.Message)" -ForegroundColor Red }
}
$free1 = (Get-PSDrive D).Free
Write-Host ""
Write-Host ("完成：失败 {0} 项；D: 可用空间 {1:N1} GB -> {2:N1} GB" -f $failed, ($free0 / 1GB), ($free1 / 1GB)) -ForegroundColor Yellow
if ($failed) { exit 1 }
