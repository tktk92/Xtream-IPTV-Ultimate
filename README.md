# Xtream IPTV Ultimate

Kodi addon for Xtream IPTV library management, STRM export, TMDb matching, and fast language-based indexing.

## Features

- Movies and series from Xtream IPTV as Kodi library entries
- STRM export for Kodi movie and TV libraries
- TMDb matching for more tolerant title search
- Language-based index files, for example `xtream_index_Deutsch.json`
- Startup automation for recent popular releases
- Optional standalone index builder scripts in `tools/`

## Install

Download the latest Kodi ZIP from the GitHub Releases page and install it in Kodi via:

`Add-ons -> Install from zip file`

The ZIP must contain the top-level folder `plugin.video.xtream.strm`.

## Build ZIP

From the addon folder:

```powershell
powershell -ExecutionPolicy Bypass -File tools\package_addon.ps1
```

The ZIP will be created in `dist/`, for example:

```text
dist/plugin.video.xtream.strm-1.0.6.zip
```

## Notes

Use this addon only with IPTV access you are allowed to use. Keep personal credentials and locally generated index files out of Git.
