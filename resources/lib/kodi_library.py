# -*- coding: utf-8 -*-

import json
import os
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

from common import ADDON_PROFILE, get_movie_strm_path, get_series_strm_path
from strm import ensure_media_folders


MOVIE_SOURCE_NAME = "Xtream IPTV Ultimate Filme"
SERIES_SOURCE_NAME = "Xtream IPTV Ultimate Serien"
MOVIE_SCRAPER_ID = "metadata.themoviedb.org.python"
TV_SCRAPER_ID = "metadata.tvshows.themoviedb.org.python"
LIBRARY_SETUP_STATE_FILE = "library_setup_state.json"
GERMAN_MOVIE_SCRAPER_SETTINGS = {
    "keeporiginaltitle": "false",
    "language": "de-DE",
    "searchlanguage": "de-DE",
    "tmdbcertcountry": "de",
    "certprefix": "FSK ",
    "fanarttv_language": "de",
}
GERMAN_TV_SCRAPER_SETTINGS = {
    "languageDetails": "de-DE",
    "usedifferentlangforimages": "false",
    "languageImages": "de-DE",
    "tmdbcertcountry": "de",
    "certprefix": "FSK ",
    "keeporiginaltitle": "false",
}
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


def translate(path):
    return xbmcvfs.translatePath(path)


def ensure_parent(path):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    ensure_parent(path)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def load_json_object(path):
    if not os.path.exists(path):
        return {}
    try:
        data = json.loads(read_text(path))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_json_object(path, data):
    write_text(path, json.dumps(data, indent=4, sort_keys=True))


def library_setup_state_path():
    return translate(os.path.join(ADDON_PROFILE, LIBRARY_SETUP_STATE_FILE))


def addon_settings_path(addon_id):
    return translate("special://profile/addon_data/{0}/settings.xml".format(addon_id))


def set_settings_xml_values(path, values):
    if os.path.exists(path):
        root = ET.parse(path).getroot()
    else:
        root = ET.Element("settings", {"version": "2"})

    for setting_id, value in values.items():
        node = root.find("./setting[@id='{0}']".format(setting_id))
        if node is None:
            node = ET.SubElement(root, "setting", {"id": setting_id})
        node.text = value
        if "default" in node.attrib:
            del node.attrib["default"]

    ensure_parent(path)
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def configure_metadata_scrapers_german():
    install_metadata_scrapers(show_dialog=False)
    set_settings_xml_values(addon_settings_path(MOVIE_SCRAPER_ID), GERMAN_MOVIE_SCRAPER_SETTINGS)
    set_settings_xml_values(addon_settings_path(TV_SCRAPER_ID), GERMAN_TV_SCRAPER_SETTINGS)
    xbmc.log("[IPTV Addon] Kodi Scraper auf Deutsch konfiguriert", xbmc.LOGINFO)


def install_and_configure_metadata_scrapers(show_dialog=True):
    results = install_metadata_scrapers(show_dialog=False)
    configure_metadata_scrapers_german()

    if show_dialog:
        xbmcgui.Dialog().ok(
            "Kodi Scraper",
            "\n".join(results) + "\n\nSprache: Deutsch",
        )

    return results


def remove_empty_dirs(path):
    path = translate(path)
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
    database_dir = translate("special://profile/Database")
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
    try:
        import sqlite3
    except Exception:
        if show_dialog:
            xbmcgui.Dialog().ok(
                "Kodi Bibliothek",
                "Automatisches Setzen des Bibliotheksinhalts ist auf diesem Kodi-System nicht verfuegbar.\n\n"
                "Bitte einmalig unter Videos -> Dateien den Inhalt manuell setzen."
            )
        return False

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
            set_path_content(cursor, movie_path, "movies", MOVIE_SCRAPER_ID, 2147483647, 0)
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
    sources_path = translate("special://profile/sources.xml")
    ensure_media_folders()
    movie_path = normalize_kodi_path(get_movie_strm_path())
    series_path = normalize_kodi_path(get_series_strm_path())

    try:
        configure_metadata_scrapers_german()

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
                existing_sources_by_path[normalize_kodi_path(path.text)] = source

        def add_or_update_source(name, path_value):
            existing = existing_sources_by_path.get(path_value)
            if existing is not None:
                source_name = existing.find("name")
                if source_name is not None and source_name.text != name:
                    source_name.text = name
                    return "aktualisiert"
                source_path = existing.find("path")
                if source_path is not None and source_path.text != path_value:
                    source_path.text = path_value
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


def json_rpc(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
    }
    if params is not None:
        payload["params"] = params

    response = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(response)
    except Exception:
        return {}


def remove_movie_from_library(movie_id):
    data = json_rpc("VideoLibrary.RemoveMovie", {"movieid": int(movie_id)})
    return data.get("result") == "OK"


def remove_tvshow_from_library(tvshow_id):
    data = json_rpc("VideoLibrary.RemoveTVShow", {"tvshowid": int(tvshow_id), "deleteepisodes": True})
    return data.get("result") == "OK"


def get_xtream_library_ids():
    try:
        import sqlite3
    except Exception:
        return [], []

    db_path = get_video_database_path()
    if not db_path:
        return [], []

    movie_path = normalize_kodi_path(get_movie_strm_path()).replace("\\", "/")
    series_path = normalize_kodi_path(get_series_strm_path()).replace("\\", "/")
    movie_ids = []
    tvshow_ids = []

    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT m.idMovie
                FROM movie m
                LEFT JOIN files f ON f.idFile = m.idFile
                LEFT JOIN path p ON p.idPath = f.idPath
                WHERE replace(COALESCE(m.c22, ''), '\\', '/') LIKE ?
                   OR replace(COALESCE(p.strPath, ''), '\\', '/') LIKE ?
                """,
                (movie_path + "%", movie_path + "%"),
            )
            movie_ids = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT DISTINCT t.idShow
                FROM tvshow t
                LEFT JOIN tvshowlinkpath tp ON tp.idShow = t.idShow
                LEFT JOIN path p ON p.idPath = tp.idPath
                WHERE replace(COALESCE(p.strPath, ''), '\\', '/') LIKE ?
                """,
                (series_path + "%",),
            )
            tvshow_ids = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        xbmc.log("[IPTV Addon] Xtream Bibliotheks-IDs konnten nicht gelesen werden: %s" % exc, xbmc.LOGERROR)

    return movie_ids, tvshow_ids


def remove_xtream_library_items():
    movie_ids, tvshow_ids = get_xtream_library_ids()
    removed_movies = 0
    removed_tvshows = 0

    for movie_id in movie_ids:
        if remove_movie_from_library(movie_id):
            removed_movies += 1

    for tvshow_id in tvshow_ids:
        if remove_tvshow_from_library(tvshow_id):
            removed_tvshows += 1

    xbmc.log(
        "[IPTV Addon] Alte Xtream Bibliotheksdaten entfernt: Filme={0}, Serien={1}".format(
            removed_movies,
            removed_tvshows,
        ),
        xbmc.LOGINFO,
    )
    return removed_movies, removed_tvshows


def apply_kodi_library_update_after_addon_update():
    version = xbmcaddon.Addon().getAddonInfo("version")
    state_path = library_setup_state_path()
    state = load_json_object(state_path)
    if state.get("addon_version") == version:
        return False

    try:
        ensure_media_folders()
        configure_metadata_scrapers_german()
        setup_video_library_content(show_dialog=False)
        removed_movies, removed_tvshows = remove_xtream_library_items()
        xbmc.executebuiltin("CleanLibrary(video)", True)
        xbmc.executebuiltin("UpdateLibrary(video)")
        save_json_object(
            state_path,
            {
                "addon_version": version,
                "applied_at": int(time.time()),
                "removed_movies": removed_movies,
                "removed_tvshows": removed_tvshows,
            },
        )
        xbmc.log("[IPTV Addon] Kodi Bibliothek nach Addon-Update aktualisiert: " + version, xbmc.LOGINFO)
        return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] Kodi Bibliothek Auto-Update fehlgeschlagen: %s" % exc, xbmc.LOGERROR)
        return False
