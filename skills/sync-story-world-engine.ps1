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

$targets = @(
    (Join-Path $repoRoot ".workbuddy/skills/story-world-engine"),
    (Join-Path $repoRoot ".opencode/skills/story-world-engine"),
    (Join-Path $repoRoot ".claude/skills/story-world-engine"),
    (Join-Path $repoRoot ".codex/skills/story-world-engine"),
    (Join-Path $repoRoot ".agents/skills/story-world-engine")
)

foreach ($dst in $targets) {
    $parent = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse -Path $source -Destination $dst
    Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    Write-Host "synced: $dst"
}

Write-Host "done: $($targets.Count) mirrors from $source"
