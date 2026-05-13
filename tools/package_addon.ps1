$ErrorActionPreference = "Stop"

$addonRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$addonId = "plugin.video.xtream.strm"
$version = ([xml](Get-Content -Raw -LiteralPath (Join-Path $addonRoot "addon.xml"))).addon.version
$distDir = Join-Path $addonRoot "dist"
$stageDir = Join-Path $distDir $addonId
$zipPath = Join-Path $distDir "$addonId-$version.zip"

if (Test-Path -LiteralPath $stageDir) {
    Remove-Item -LiteralPath $stageDir -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $stageDir | Out-Null

$excludeDirs = @(".git", "dist", "__pycache__", ".venv", "venv", "env")
$excludeFiles = @("*.pyc", "*.pyo", "*.tmp", "*.bak", ".env", ".env.*")

Get-ChildItem -LiteralPath $addonRoot -Force | ForEach-Object {
    if ($excludeDirs -contains $_.Name) {
        return
    }

    $target = Join-Path $stageDir $_.Name
    if ($_.PSIsContainer) {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    } else {
        $skip = $false
        foreach ($pattern in $excludeFiles) {
            if ($_.Name -like $pattern) {
                $skip = $true
                break
            }
        }
        if (-not $skip) {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

Get-ChildItem -LiteralPath $stageDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $stageDir -Recurse -File | Where-Object {
    $_.Name -like "*.pyc" -or
    $_.Name -like "*.pyo" -or
    $_.Name -like "*.tmp" -or
    $_.Name -like "*.bak"
} | Remove-Item -Force

Compress-Archive -LiteralPath $stageDir -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
