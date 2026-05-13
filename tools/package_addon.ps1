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

$addonRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$addonId = "plugin.video.xtream.strm"
$version = ([xml](Get-Content -Raw -LiteralPath (Join-Path $addonRoot "addon.xml"))).addon.version
$distDir = Join-Path $addonRoot "dist"
$zipPath = Join-Path $distDir "$addonId-$version.zip"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$archive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($fileName in @("addon.xml", "default.py", "service.py", "README.md")) {
        $source = Join-Path $addonRoot $fileName
        if (Test-Path -LiteralPath $source) {
            Add-ZipEntry -Archive $archive -SourcePath $source -EntryName "$addonId/$fileName"
        }
    }

    $resourcesRoot = Join-Path $addonRoot "resources"
    Get-ChildItem -LiteralPath $resourcesRoot -Recurse -File | ForEach-Object {
        if ($_.Name -like "*.pyc" -or $_.Name -like "*.pyo" -or $_.Name -like "*.tmp" -or $_.Name -like "*.bak") {
            return
        }
        $relative = $_.FullName.Substring($addonRoot.Path.Length + 1)
        Add-ZipEntry -Archive $archive -SourcePath $_.FullName -EntryName "$addonId/$relative"
    }
}
finally {
    $archive.Dispose()
}

Write-Host "Created $zipPath"
