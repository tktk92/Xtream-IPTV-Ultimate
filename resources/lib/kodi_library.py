# -*- coding: utf-8 -*-

import os
import sqlite3
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

from common import get_movie_strm_path, get_series_strm_path


MOVIE_SOURCE_NAME = "Xtream IPTV Ultimate Filme"
SERIES_SOURCE_NAME = "Xtream IPTV Ultimate Serien"
MOVIE_SCRAPER_ID = "metadata.themoviedb.org.python"
TV_SCRAPER_ID = "metadata.tvshows.themoviedb.org.python"
SCRAPER_LABELS = {
    MOVIE_SCRAPER_ID: "The Movie Database Python",
    TV_SCRAPER_ID: "TMDb TV Shows",
}


def is_addon_installed(addon_id):
    try:
        xbmcaddon.Addon(addon_id)
        return True
    except Exception:
        return False


def install_addon(addon_id):
    xbmc.executebuiltin("InstallAddon({0})".format(addon_id), True)
    return is_addon_installed(addon_id)


def install_metadata_scrapers(show_dialog=True):
    results = []
    for addon_id in (MOVIE_SCRAPER_ID, TV_SCRAPER_ID):
        label = SCRAPER_LABELS.get(addon_id, addon_id)
        if is_addon_installed(addon_id):
            results.append("{0}: bereits installiert".format(label))
            continue

        if install_addon(addon_id):
            results.append("{0}: installiert".format(label))
        else:
            results.append("{0}: nicht installiert".format(label))

    if show_dialog:
        xbmcgui.Dialog().ok("Kodi Scraper", "\n".join(results))

    return results


def remove_empty_dirs(path):
    path = xbmcvfs.translatePath(path)
    if not path or not os.path.exists(path):
        return 0

    removed = 0
    for root, dirs, files in os.walk(path, topdown=False):
        if root == path:
            continue
        try:
            if not os.listdir(root):
                os.rmdir(root)
                removed += 1
        except Exception:
            continue

    return removed


def remove_empty_strm_dirs():
    return remove_empty_dirs(get_movie_strm_path()) + remove_empty_dirs(get_series_strm_path())


def normalize_kodi_path(path):
    if not path:
        return ""
    if not path.endswith("/") and not path.endswith("\\"):
        return path + "/"
    return path


def get_video_database_path():
    database_dir = xbmcvfs.translatePath("special://profile/Database")
    if not os.path.exists(database_dir):
        return ""

    candidates = []
    for name in os.listdir(database_dir):
        if name.startswith("MyVideos") and name.endswith(".db"):
            try:
                number = int(name.replace("MyVideos", "").replace(".db", ""))
            except Exception:
                number = 0
            candidates.append((number, os.path.join(database_dir, name)))

    if not candidates:
        return ""

    return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]


def ensure_path_row(cursor, path_value):
    path_value = normalize_kodi_path(path_value)
    cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (path_value,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO path (strPath, strContent, strScraper, scanRecursive, useFolderNames, noUpdate, exclude) "
        "VALUES (?, '', '', 0, 0, 0, 0)",
        (path_value,)
    )
    return cursor.lastrowid


def set_path_content(cursor, path_value, content, scraper, recursive, use_folder_names):
    path_id = ensure_path_row(cursor, path_value)
    cursor.execute(
        "UPDATE path SET strContent = ?, strScraper = ?, scanRecursive = ?, useFolderNames = ?, noUpdate = 0, exclude = 0 "
        "WHERE idPath = ?",
        (content, scraper, recursive, use_folder_names, path_id)
    )


def setup_video_library_content(show_dialog=False):
    db_path = get_video_database_path()
    if not db_path:
        if show_dialog:
            xbmcgui.Dialog().ok("Kodi Bibliothek", "Kodi Video-Datenbank wurde nicht gefunden.")
        return False

    movie_path = normalize_kodi_path(get_movie_strm_path())
    series_path = normalize_kodi_path(get_series_strm_path())

    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            set_path_content(cursor, movie_path, "movies", MOVIE_SCRAPER_ID, 2147483647, 1)
            set_path_content(cursor, series_path, "tvshows", TV_SCRAPER_ID, 2147483647, 0)
            conn.commit()
        finally:
            conn.close()

        if show_dialog:
            xbmcgui.Dialog().ok(
                "Kodi Bibliothek",
                "Inhalte wurden gesetzt:\n\n"
                + MOVIE_SOURCE_NAME + " = Filme\n"
                + SERIES_SOURCE_NAME + " = Serien"
            )
        return True
    except Exception as e:
        if show_dialog:
            xbmcgui.Dialog().ok("Kodi Bibliothek", "Inhalte konnten nicht gesetzt werden:\n\n" + str(e))
        return False


def setup_kodi_sources():
    sources_path = xbmcvfs.translatePath("special://profile/sources.xml")
    movie_path = get_movie_strm_path()
    series_path = get_series_strm_path()

    try:
        if os.path.exists(sources_path):
            tree = ET.parse(sources_path)
            root = tree.getroot()
        else:
            root = ET.Element("sources")
            tree = ET.ElementTree(root)

        video = root.find("video")
        if video is None:
            video = ET.SubElement(root, "video")
            ET.SubElement(video, "default", attrib={"pathversion": "1"})

        existing_sources_by_path = {}
        for source in video.findall("source"):
            path = source.find("path")
            if path is not None and path.text:
                existing_sources_by_path[path.text] = source

        def add_or_update_source(name, path_value):
            existing = existing_sources_by_path.get(path_value)
            if existing is not None:
                source_name = existing.find("name")
                if source_name is not None and source_name.text != name:
                    source_name.text = name
                    return "aktualisiert"
                return "bereits vorhanden"

            source = ET.SubElement(video, "source")
            ET.SubElement(source, "name").text = name
            ET.SubElement(source, "path", attrib={"pathversion": "1"}).text = path_value
            ET.SubElement(source, "allowsharing").text = "true"
            existing_sources_by_path[path_value] = source
            return "hinzugefuegt"

        movies_status = add_or_update_source(MOVIE_SOURCE_NAME, movie_path)
        series_status = add_or_update_source(SERIES_SOURCE_NAME, series_path)

        folder = os.path.dirname(sources_path)
        if not os.path.exists(folder):
            os.makedirs(folder)

        tree.write(sources_path, encoding="utf-8", xml_declaration=True)
        content_status = "gesetzt" if setup_video_library_content(show_dialog=False) else "nicht gesetzt"

        xbmcgui.Dialog().ok(
            "Kodi Quellen",
            "Quellen wurden eingerichtet.\n\n"
            "Filme: " + movies_status + "\n"
            "Serien: " + series_status + "\n\n"
            "Bibliotheksinhalt: " + content_status + "\n\n"
            "Falls Kodi die Inhalte nicht sofort erkennt, bitte Kodi neu starten und erneut scannen."
        )
    except Exception as e:
        xbmcgui.Dialog().ok("Fehler", "Quellen konnten nicht eingerichtet werden:\n\n" + str(e))


def scan_kodi_library():
    xbmc.executebuiltin("UpdateLibrary(video)")
    xbmcgui.Dialog().notification("Kodi Bibliothek", "Videoscan gestartet", xbmcgui.NOTIFICATION_INFO, 5000)


def clean_kodi_library():
    xbmc.executebuiltin("CleanLibrary(video)")
    xbmcgui.Dialog().notification("Kodi Bibliothek", "Bereinigung gestartet", xbmcgui.NOTIFICATION_INFO, 5000)


def clean_and_scan_kodi_library():
    try:
        removed = remove_empty_strm_dirs()
        xbmc.executebuiltin("CleanLibrary(video)", True)
        xbmc.executebuiltin("UpdateLibrary(video)", True)
        xbmcgui.Dialog().notification(
            "Kodi Bibliothek",
            "Bereinigung abgeschlossen, Scan gestartet" + (f" ({removed} leere Ordner entfernt)" if removed else ""),
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
    except Exception as e:
        xbmcgui.Dialog().ok(
            "Kodi Bibliothek",
            "Bereinigung/Scan konnte nicht gestartet werden:\n\n" + str(e)
        )


def ask_clean_and_scan_after_export():
    confirm = xbmcgui.Dialog().yesno(
        "Kodi Bibliothek aktualisieren",
        "Der Export wurde abgeschlossen.\n\n"
        "Soll die Kodi Bibliothek jetzt bereinigt und neu gescannt werden?",
        nolabel="Nein",
        yeslabel="Ja"
    )

    if not confirm:
        return

    clean_and_scan_kodi_library()
