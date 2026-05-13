# -*- coding: utf-8 -*-

import xbmcgui
import xbmcplugin

from common import HANDLE, build_url
from config import get_selected_languages


def add_directory_items(items):
    for label, params, is_folder in items:
        li = xbmcgui.ListItem(label)
        xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, is_folder)
    xbmcplugin.endOfDirectory(HANDLE)


def main_menu():
    items = [
        ("Suchen & Hinzufügen", {"mode": "add_menu"}, True),
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
    ]
    add_directory_items(items)


def index_menu():
    items = [
        ("Index-Info anzeigen", {"mode": "show_index_info"}, False),
        ("Basis-Index neu erstellen", {"mode": "rebuild_basic_index"}, False),
        ("TMDb-Infos pro Gruppe aktualisieren", {"mode": "metadata_groups"}, False),
        ("Vollindex mit allen TMDb-Infos erstellen", {"mode": "rebuild_index"}, False),
    ]
    add_directory_items(items)
