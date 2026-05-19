# -*- coding: utf-8 -*-

import os

import xbmcgui
import xbmcplugin

from common import ADDON, HANDLE, build_url
from config import get_selected_languages


MEDIA_PATH = os.path.join(ADDON.getAddonInfo("path"), "resources", "media")

MODE_ICONS = {
    "add_menu": "search.png",
    "setup_live_tv": "live-tv.png",
    "library_menu": "library.png",
    "settings_menu": "settings.png",
    "choose_languages": "language.png",
    "movies_menu": "movies.png",
    "series_menu": "series.png",
    "library_series": "series.png",
    "library_movies": "movies.png",
    "delete_all_streams": "delete.png",
    "stream_check_menu": "check.png",
    "kodi_library_menu": "kodi.png",
    "storage_menu": "storage.png",
    "index_menu": "index.png",
    "clean_and_scan_library": "refresh.png",
    "setup_sources": "folder.png",
    "setup_library_content": "library.png",
    "install_metadata_scrapers": "scraper.png",
    "check_streams": "check.png",
    "show_broken_streams": "warning.png",
    "show_series_path": "folder.png",
    "show_movie_path": "folder.png",
    "show_internal_paths": "storage.png",
    "show_free_space": "storage.png",
    "setup_wizard": "wizard.png",
    "open_settings": "credentials.png",
    "install_arctic_zephyr_reloaded": "skin.png",
    "configure_arctic_zephyr_reloaded": "layout.png",
    "show_index_info": "info.png",
    "rebuild_basic_index": "refresh.png",
}


def _icon_path(params):
    icon_name = MODE_ICONS.get(params.get("mode"), "icon.png")
    return os.path.join(MEDIA_PATH, icon_name)


def add_directory_items(items):
    for label, params, is_folder in items:
        li = xbmcgui.ListItem(label)
        icon = _icon_path(params)
        li.setArt({"icon": icon, "thumb": icon})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, is_folder)
    xbmcplugin.endOfDirectory(HANDLE)


def main_menu():
    items = [
        ("Suchen & Hinzufügen", {"mode": "add_menu"}, True),
        ("Live TV einrichten", {"mode": "setup_live_tv"}, False),
        ("Bibliothek verwalten", {"mode": "library_menu"}, True),
        ("Einstellungen", {"mode": "settings_menu"}, True),
    ]
    add_directory_items(items)


def add_menu():
    selected = get_selected_languages()
    language_text = ", ".join(selected) if selected else "Alle"

    items = [
        ("Sprache: " + language_text, {"mode": "choose_languages"}, False),
        ("Filme", {"mode": "movies_menu"}, True),
        ("Serien", {"mode": "series_menu"}, True),
    ]
    add_directory_items(items)


def library_menu():
    items = [
        ("Serien", {"mode": "library_series"}, True),
        ("Filme", {"mode": "library_movies"}, True),
        ("Alle Streams löschen", {"mode": "delete_all_streams"}, False),
        ("Streams überprüfen", {"mode": "stream_check_menu"}, True),
        ("Kodi Bibliothek", {"mode": "kodi_library_menu"}, True),
        ("Speicherorte", {"mode": "storage_menu"}, True),
        ("Index verwalten", {"mode": "index_menu"}, True),
    ]
    add_directory_items(items)


def kodi_library_menu():
    items = [
        ("Bibliothek bereinigen und scannen", {"mode": "clean_and_scan_library"}, False),
        ("Quellen automatisch einrichten", {"mode": "setup_sources"}, False),
        ("Bibliotheksinhalt automatisch setzen", {"mode": "setup_library_content"}, False),
        ("Kodi Scraper installieren", {"mode": "install_metadata_scrapers"}, False),
    ]
    add_directory_items(items)


def stream_check_menu():
    items = [
        ("Alle Streams prüfen", {"mode": "check_streams", "scope": "all"}, False),
        ("Nur Serien prüfen", {"mode": "check_streams", "scope": "series"}, False),
        ("Nur Filme prüfen", {"mode": "check_streams", "scope": "movies"}, False),
        ("Defekte Streams anzeigen", {"mode": "show_broken_streams"}, False),
    ]
    add_directory_items(items)


def storage_menu():
    items = [
        ("Serienordner anzeigen", {"mode": "show_series_path"}, False),
        ("Filmeordner anzeigen", {"mode": "show_movie_path"}, False),
        ("Interne Speicherorte anzeigen", {"mode": "show_internal_paths"}, False),
        ("Freier Speicherplatz", {"mode": "show_free_space"}, False),
    ]
    add_directory_items(items)


def settings_menu():
    items = [
        ("Ersteinrichtung starten", {"mode": "setup_wizard"}, False),
        ("IPTV Zugangsdaten", {"mode": "open_settings"}, False),
        ("Speicherpfade", {"mode": "open_settings"}, False),
        ("Arctic: Zephyr - Reloaded installieren", {"mode": "install_arctic_zephyr_reloaded"}, False),
        ("Arctic: Zephyr - Reloaded einrichten", {"mode": "configure_arctic_zephyr_reloaded"}, False),
    ]
    add_directory_items(items)


def index_menu():
    items = [
        ("Index-Info anzeigen", {"mode": "show_index_info"}, False),
        ("Kompakten Index lÃ¶schen und neu erstellen", {"mode": "rebuild_basic_index"}, False),
    ]
    add_directory_items(items)
