# -*- coding: utf-8 -*-

import os
import shutil
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs


from common import HANDLE, build_url
from strm import get_movie_folder, get_series_folder


def list_dirs(path):
    if not os.path.exists(path):
        return []
    return sorted([x for x in os.listdir(path) if os.path.isdir(os.path.join(path, x))])


def list_strm_files(path):
    if not os.path.exists(path):
        return []
    return sorted([x for x in os.listdir(path) if x.lower().endswith(".strm")])


def show_series_library():
    base = get_series_folder()
    series_items = list_dirs(base)

    if not series_items:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Serien gefunden")
        return

    for serie in series_items:
        full_path = os.path.join(base, serie)
        li = xbmcgui.ListItem(serie)
        li.addContextMenuItems([
            ("Ganze Serie entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': full_path})})")
        ])
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "library_seasons", "path": full_path}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_library_seasons(path):
    path = xbmcvfs.translatePath(path)
    seasons = list_dirs(path)

    if not seasons:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Staffeln gefunden")
        return

    for season in seasons:
        season_path = os.path.join(path, season)
        li = xbmcgui.ListItem(season)
        li.addContextMenuItems([
            ("Staffel entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': season_path})})")
        ])
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "library_episodes", "path": season_path}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_library_episodes(path):
    path = xbmcvfs.translatePath(path)
    files = list_strm_files(path)

    if not files:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Folgen gefunden")
        return

    for file_name in files:
        file_path = os.path.join(path, file_name)
        label = file_name[:-5]
        li = xbmcgui.ListItem(label)
        li.addContextMenuItems([
            ("Folge entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': file_path})})")
        ])
        xbmcplugin.addDirectoryItem(HANDLE, file_path, li, False)

    xbmcplugin.endOfDirectory(HANDLE)


def show_movies_library():
    base = get_movie_folder()

    if not os.path.exists(base):
        xbmcgui.Dialog().ok("Bibliothek", "Keine Filme gefunden")
        return

    entries = []
    for root, dirs, files in os.walk(base):
        for file_name in files:
            if file_name.lower().endswith(".strm"):
                entries.append(os.path.join(root, file_name))

    if not entries:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Filme gefunden")
        return

    for file_path in sorted(entries):
        rel = os.path.relpath(file_path, base)
        label = rel[:-5]
        li = xbmcgui.ListItem(label)
        li.addContextMenuItems([
            ("Film entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': file_path})})")
        ])
        xbmcplugin.addDirectoryItem(HANDLE, file_path, li, False)

    xbmcplugin.endOfDirectory(HANDLE)


def delete_library_item(path):
    path = xbmcvfs.translatePath(path)

    if not path or not os.path.exists(path):
        xbmcgui.Dialog().ok("Löschen", "Datei oder Ordner nicht gefunden")
        return

    confirm = xbmcgui.Dialog().yesno(
        "Aus Bibliothek entfernen",
        "Möchtest du diesen Eintrag wirklich löschen?\n\n" + path
    )

    if not confirm:
        return

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        xbmcgui.Dialog().notification(
            "Gelöscht",
            "Eintrag wurde entfernt",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        xbmc.executebuiltin("Container.Refresh")

    except Exception as e:
        xbmcgui.Dialog().ok("Fehler", str(e))