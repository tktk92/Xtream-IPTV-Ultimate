# -*- coding: utf-8 -*-

import json
import os
import urllib.request
import xbmc
import xbmcgui
import xbmcvfs

from common import ADDON_ID
from strm import get_movie_folder, get_series_folder

BROKEN_FILE = "special://profile/addon_data/" + ADDON_ID + "/broken_streams.json"


def get_broken_file():
    path = xbmcvfs.translatePath(BROKEN_FILE)
    folder = os.path.dirname(path)
    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)
    return path


def collect_strm_files(scope="all"):
    roots = []
    if scope in ("all", "movies"):
        roots.append(("Film", get_movie_folder()))
    if scope in ("all", "series"):
        roots.append(("Serie", get_series_folder()))

    result = []
    for media_type, root in roots:
        if not os.path.exists(root):
            continue
        for current, dirs, files in os.walk(root):
            for file_name in files:
                if file_name.lower().endswith(".strm"):
                    result.append((media_type, os.path.join(current, file_name)))
    return result


def read_stream_url(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def check_url(url, timeout=8):
    if not url:
        return False, "Leere STRM-Datei"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            code = getattr(response, "status", response.getcode())
            if 200 <= int(code) < 400:
                return True, "OK"
            return False, "HTTP " + str(code)
    except Exception as e:
        return False, str(e)


def check_streams(scope="all"):
    files = collect_strm_files(scope)

    if not files:
        xbmcgui.Dialog().ok("Streams überprüfen", "Keine STRM-Dateien gefunden")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Streams überprüfen", "Prüfung läuft...")

    broken = []
    ok_count = 0

    for index, item in enumerate(files):
        if progress.iscanceled():
            break

        media_type, path = item
        label = os.path.basename(path)
        progress.update(int((index + 1) / len(files) * 100), label)

        try:
            url = read_stream_url(path)
            ok, reason = check_url(url)
            if ok:
                ok_count += 1
            else:
                broken.append({"type": media_type, "path": path, "url": url, "reason": reason})
        except Exception as e:
            broken.append({"type": media_type, "path": path, "url": "", "reason": str(e)})
            xbmc.log("[IPTV Addon] Streamprüfung Fehler: " + path + " | " + str(e), xbmc.LOGERROR)

    progress.close()
    save_broken_streams(broken)

    if broken:
        show_broken_streams()
    else:
        xbmcgui.Dialog().notification("Streams überprüft", f"Alle {ok_count} Streams funktionieren", xbmcgui.NOTIFICATION_INFO, 5000)


def save_broken_streams(items):
    path = get_broken_file()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=4)


def load_broken_streams():
    path = get_broken_file()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def show_broken_streams():
    items = load_broken_streams()

    if not items:
        xbmcgui.Dialog().ok("Defekte Streams", "Keine defekten Streams gespeichert")
        return

    lines = []
    for item in items:
        lines.append(item.get("type", "") + ": " + os.path.basename(item.get("path", "")))
        lines.append("Grund: " + item.get("reason", "Unbekannt"))
        lines.append("Pfad: " + item.get("path", ""))
        lines.append("")

    xbmcgui.Dialog().textviewer("Defekte Streams", "\n".join(lines))
