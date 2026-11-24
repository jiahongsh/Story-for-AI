# 同步 story-world-engine 正本到各运行时镜像
# 正本：skills/story-world-engine/
# 用法：pwsh -File skills/sync-story-world-engine.ps1
$ErrorActionPreference = "Stop"

$skillsDir = $PSScriptRoot
$repoRoot  = Split-Path -Parent $skillsDir
$source    = Join-Path $skillsDir "story-world-engine"

if (-not (Test-Path $source)) {
    throw "canonical skill not found: $source"
}

# 默认始终同步当前主力宿主 Antigravity (.agents)；其余宿主仅在项目已部署对应隐藏目录时按需同步，避免凭空生成多套重复目录
$targets = @(
    (Join-Path $repoRoot ".agents/skills/story-world-engine")
)
foreach ($optionalHost in @(".claude", ".codex", ".opencode", ".workbuddy")) {
    $hostRoot = Join-Path $repoRoot $optionalHost
    if (Test-Path $hostRoot) {
        $targets += (Join-Path $hostRoot "skills/story-world-engine")
    }
}

foreach ($dst in $targets) {
    $parent = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse -Path $source -Destination $dst
    Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    Write-Host "synced: $dst"
}

Write-Host "done: $($targets.Count) mirror(s) from $source"
