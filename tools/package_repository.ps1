$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Add-ZipEntry {
    param(
        [System.IO.Compression.ZipArchive]$Archive,
        [string]$SourcePath,
        [string]$EntryName
    )

    $entryName = $EntryName.Replace("\", "/")
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $Archive,
        $SourcePath,
        $entryName,
        [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}

function New-SingleAddonZip {
    param(
        [string]$SourceDir,
        [string]$AddonId,
        [string]$ZipPath
    )

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    $archive = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        Get-ChildItem -LiteralPath $SourceDir -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($SourceDir.Length + 1)
            Add-ZipEntry -Archive $archive -SourcePath $_.FullName -EntryName "$AddonId/$relative"
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Write-IndexHtml {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Links
    )

    $items = ($Links | ForEach-Object { "    <li><a href=""$_"">$_</a></li>" }) -join "`n"
    $html = @"
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>$Title</title>
</head>
<body>
  <h1>$Title</h1>
  <ul>
$items
  </ul>
</body>
</html>
"@

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $html, $encoding)
}

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

& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "package_addon.ps1")

New-Item -ItemType Directory -Force -Path $repoZipDir | Out-Null
New-Item -ItemType Directory -Force -Path $pluginZipDir | Out-Null

Get-ChildItem -LiteralPath $pluginZipDir -Filter "$pluginId-*.zip" -File -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -LiteralPath $pluginZip -Destination (Join-Path $pluginZipDir (Split-Path $pluginZip -Leaf)) -Force

Get-ChildItem -LiteralPath $repoZipDir -Filter "$repoId-*.zip" -File -ErrorAction SilentlyContinue | Remove-Item -Force
New-SingleAddonZip -SourceDir $repoAddonDir -AddonId $repoId -ZipPath $repoZip

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

Write-IndexHtml -Path (Join-Path $zipsDir "index.html") -Title "Xtream IPTV Ultimate Repository" -Links @("$repoId/", "$pluginId/")
Write-IndexHtml -Path (Join-Path $repoZipDir "index.html") -Title "Xtream IPTV Ultimate Repository ZIP" -Links @("$repoId-$repoVersion.zip")
Write-IndexHtml -Path (Join-Path $pluginZipDir "index.html") -Title "Xtream IPTV Ultimate Addon ZIP" -Links @("$pluginId-$pluginVersion.zip")

Write-Host "Repository created:"
Write-Host "  repo/addons.xml"
Write-Host "  repo/addons.xml.md5"
Write-Host "  repo/zips/$repoId/$repoId-$repoVersion.zip"
Write-Host "  repo/zips/$pluginId/$pluginId-$pluginVersion.zip"
