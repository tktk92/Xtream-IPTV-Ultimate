# -*- coding: utf-8 -*-

import os
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcvfs

from common import get_movie_strm_path, get_series_strm_path


MOVIE_SOURCE_NAME = "Xtream IPTV Ultimate Filme"
SERIES_SOURCE_NAME = "Xtream IPTV Ultimate Serien"


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

        xbmcgui.Dialog().ok(
            "Kodi Quellen",
            "Quellen wurden eingerichtet.\n\n"
            "Filme: " + movies_status + "\n"
            "Serien: " + series_status + "\n\n"
            "Falls Kodi die Inhalte nicht sofort erkennt, bitte Kodi neu starten.\n\n"
            "Danach unter Videos -> Dateien den Inhalt setzen:\n"
            + MOVIE_SOURCE_NAME + " = Filme\n"
            + SERIES_SOURCE_NAME + " = Serien"
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
