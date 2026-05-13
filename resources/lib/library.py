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


def count_strm_files(path):
    if not os.path.exists(path):
        return 0

    count = 0
    for root, dirs, files in os.walk(path):
        count += len([name for name in files if name.lower().endswith(".strm")])
    return count


def delete_strm_files_and_empty_dirs(path):
    path = xbmcvfs.translatePath(path)
    if not path:
        return 0

    root_path = os.path.abspath(path)
    if not os.path.isdir(root_path):
        return 0

    removed_files = 0
    for current_root, dirs, files in os.walk(root_path, topdown=False):
        current_abs = os.path.abspath(current_root)
        if os.path.commonpath([root_path, current_abs]) != root_path:
            continue

        for file_name in files:
            if not file_name.lower().endswith(".strm"):
                continue
            file_path = os.path.abspath(os.path.join(current_abs, file_name))
            if os.path.commonpath([root_path, file_path]) != root_path:
                continue
            os.remove(file_path)
            removed_files += 1

        if current_abs != root_path and not os.listdir(current_abs):
            os.rmdir(current_abs)

    return removed_files


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


def delete_all_streams():
    movie_folder = get_movie_folder()
    series_folder = get_series_folder()
    movie_count = count_strm_files(movie_folder)
    series_count = count_strm_files(series_folder)
    total = movie_count + series_count

    if total == 0:
        xbmcgui.Dialog().ok("Streams löschen", "Keine exportierten Streams gefunden.")
        return

    confirm = xbmcgui.Dialog().yesno(
        "Alle Streams löschen",
        "Möchtest du wirklich alle exportierten Streams löschen?\n\n"
        "Filme: {0}\nSerien: {1}\n\n"
        "Die Addon-Einstellungen und Zugangsdaten bleiben erhalten.".format(movie_count, series_count),
        nolabel="Nein",
        yeslabel="Löschen"
    )

    if not confirm:
        return

    try:
        removed_files = delete_strm_files_and_empty_dirs(movie_folder) + delete_strm_files_and_empty_dirs(series_folder)
        xbmc.executebuiltin("CleanLibrary(video)")
        xbmc.executebuiltin("Container.Refresh")
        xbmcgui.Dialog().notification(
            "Streams gelöscht",
            "{0} Streams entfernt".format(removed_files),
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
        xbmc.log(
            "[IPTV Addon] Alle Streams geloescht: {0} Dateien".format(removed_files),
            xbmc.LOGINFO
        )
    except Exception as e:
        xbmcgui.Dialog().ok("Fehler", str(e))
