$ErrorActionPreference = "Stop"

$addonRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pluginId = "plugin.video.xtream.strm"
$repoId = "repository.xtream.iptv.ultimate"
$repoRoot = Join-Path $addonRoot "repo"
$repoAddonDir = Join-Path $repoRoot $repoId
$zipsDir = Join-Path $repoRoot "zips"
$pluginVersion = ([xml](Get-Content -Raw -LiteralPath (Join-Path $addonRoot "addon.xml"))).addon.version
$repoVersion = ([xml](Get-Content -Raw -LiteralPath (Join-Path $repoAddonDir "addon.xml"))).addon.version
$pluginZip = Join-Path $addonRoot "dist\$pluginId-$pluginVersion.zip"
$repoZipDir = Join-Path $zipsDir $repoId
$pluginZipDir = Join-Path $zipsDir $pluginId
$repoZip = Join-Path $repoZipDir "$repoId-$repoVersion.zip"

if (-not (Test-Path -LiteralPath $pluginZip)) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "package_addon.ps1")
}

New-Item -ItemType Directory -Force -Path $repoZipDir | Out-Null
New-Item -ItemType Directory -Force -Path $pluginZipDir | Out-Null

Copy-Item -LiteralPath $pluginZip -Destination (Join-Path $pluginZipDir (Split-Path $pluginZip -Leaf)) -Force

$stageDir = Join-Path $repoRoot "_stage_$repoId"
if (Test-Path -LiteralPath $stageDir) {
    Remove-Item -LiteralPath $stageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $stageDir $repoId) | Out-Null
Copy-Item -LiteralPath (Join-Path $repoAddonDir "addon.xml") -Destination (Join-Path $stageDir "$repoId\addon.xml") -Force

if (Test-Path -LiteralPath $repoZip) {
    Remove-Item -LiteralPath $repoZip -Force
}
Compress-Archive -LiteralPath (Join-Path $stageDir $repoId) -DestinationPath $repoZip -Force
Remove-Item -LiteralPath $stageDir -Recurse -Force

$pluginAddonXml = Get-Content -Raw -LiteralPath (Join-Path $addonRoot "addon.xml")
$repositoryAddonXml = Get-Content -Raw -LiteralPath (Join-Path $repoAddonDir "addon.xml")
$addonsXml = "<?xml version=`"1.0`" encoding=`"UTF-8`" standalone=`"yes`"?>`n<addons>`n" +
    $repositoryAddonXml.Replace("<?xml version=`"1.0`" encoding=`"UTF-8`" standalone=`"yes`"?>", "").Trim() + "`n" +
    $pluginAddonXml.Replace("<?xml version=`"1.0`" encoding=`"UTF-8`" standalone=`"yes`"?>", "").Trim() + "`n" +
    "</addons>`n"

$addonsPath = Join-Path $repoRoot "addons.xml"
$encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($addonsPath, $addonsXml, $encoding)

$md5 = [System.BitConverter]::ToString(
    [System.Security.Cryptography.MD5]::Create().ComputeHash([System.IO.File]::ReadAllBytes($addonsPath))
).Replace("-", "").ToLowerInvariant()
[System.IO.File]::WriteAllText((Join-Path $repoRoot "addons.xml.md5"), $md5, $encoding)

Write-Host "Repository created:"
Write-Host "  repo/addons.xml"
Write-Host "  repo/addons.xml.md5"
Write-Host "  repo/zips/$repoId/$repoId-$repoVersion.zip"
Write-Host "  repo/zips/$pluginId/$pluginId-$pluginVersion.zip"
