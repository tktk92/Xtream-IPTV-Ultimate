# -*- coding: utf-8 -*-

import json
import os

import xbmcgui
import xbmcvfs

import appearance
import kodi_library
import profiles
import xtream
from common import ADDON, ADDON_PROFILE
from config import ALL_LANGUAGES, get_selected_languages, set_selected_languages
from strm import ensure_media_folders

SETUP_STATE_FILE = os.path.join(ADDON_PROFILE, "setup_state.json")


def choose_languages(show_dialog=True):
    selected = get_selected_languages()
    labels = []

    for lang in ALL_LANGUAGES:
        labels.append(("[x] " if lang in selected else "[ ] ") + lang)

    indexes = xbmcgui.Dialog().multiselect("Sprachen auswaehlen", labels)

    if indexes is None:
        return None

    new_selected = [ALL_LANGUAGES[index] for index in indexes]
    set_selected_languages(new_selected)

    if show_dialog:
        if new_selected:
            xbmcgui.Dialog().ok("Gespeichert", "Aktive Sprachen:\n\n" + "\n".join(new_selected))
        else:
            xbmcgui.Dialog().ok("Gespeichert", "Keine Sprache ausgewaehlt.\nEs wird wieder alles angezeigt.")

    return new_selected


def open_settings():
    ADDON.openSettings()


def get_setup_state_path():
    return xbmcvfs.translatePath(SETUP_STATE_FILE)


def load_setup_state():
    path = get_setup_state_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def save_setup_state(state):
    path = get_setup_state_path()
    folder = os.path.dirname(path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def is_setup_completed():
    return bool(load_setup_state().get("completed"))


def has_credentials():
    server = ADDON.getSetting("server_url").strip()
    username = ADDON.getSetting("username").strip()
    password = ADDON.getSetting("password").strip()
    return bool(server and username and password and "example.com" not in server)


def input_text(title, default="", hidden=False):
    option = getattr(xbmcgui, "ALPHANUM_HIDE_INPUT", 0) if hidden else 0
    return xbmcgui.Dialog().input(title, defaultt=default, type=xbmcgui.INPUT_ALPHANUM, option=option).strip()


def update_setup_progress(progress, percent, message, estimate):
    progress.update(percent, message + "\n\nUngefaehre Dauer: " + estimate)


def collect_credentials():
    server = input_text("IPTV Server URL", ADDON.getSetting("server_url").strip())
    if not server:
        xbmcgui.Dialog().notification("Einrichtung", "Server URL fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return None

    username = input_text("IPTV Benutzername", ADDON.getSetting("username").strip())
    if not username:
        xbmcgui.Dialog().notification("Einrichtung", "Benutzername fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return None

    password = input_text("IPTV Passwort", ADDON.getSetting("password").strip(), hidden=True)
    if not password:
        xbmcgui.Dialog().notification("Einrichtung", "Passwort fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return None

    return server.rstrip("/"), username, password


def run_setup_wizard(force=False):
    if not force and is_setup_completed() and has_credentials():
        return False

    credentials = collect_credentials()
    if not credentials:
        return False

    server, username, password = credentials

    progress = xbmcgui.DialogProgress()
    progress.create("Xtream IPTV Ultimate", "Pruefe Zugangsdaten...")
    try:
        update_setup_progress(progress, 10, "Verbindung zum IPTV-Server wird getestet.", "ca. 1 Minute")
        valid, message = xtream.validate_credentials(server, username, password)
    finally:
        progress.close()

    if not valid:
        xbmcgui.Dialog().ok("Einrichtung", message)
        return False

    ADDON.setSetting("server_url", server)
    ADDON.setSetting("username", username)
    ADDON.setSetting("password", password)

    selected_languages = choose_languages(show_dialog=False)
    if selected_languages is None:
        xbmcgui.Dialog().notification("Einrichtung", "Sprachauswahl abgebrochen", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    progress = xbmcgui.DialogProgress()
    progress.create("Xtream IPTV Ultimate", "Einrichtung wird vorbereitet...")

    try:
        update_setup_progress(progress, 15, "Ordner fuer Filme und Serien werden angelegt.", "ca. 3-8 Minuten")
        ensure_media_folders()

        update_setup_progress(progress, 24, "Kodi-Profile und LoginScreen werden fuer den naechsten Start vorbereitet.", "ca. 1 Minute")
        profiles.apply_profiles_after_update(progress=progress)

        update_setup_progress(progress, 35, "Kodi-Scraper werden installiert und auf Deutsch eingerichtet.", "ca. 3-8 Minuten")
        kodi_library.install_and_configure_metadata_scrapers(show_dialog=False)

        update_setup_progress(progress, 48, "YouTube und der Ultimate IPTV Skin werden fuer Trailer vorbereitet.", "ca. 2-5 Minuten")
        appearance.install_youtube_addon(show_dialog=False)
        appearance.setup_arctic_zephyr_reloaded(show_dialog=False)

        update_setup_progress(progress, 60, "Kodi-Quellen fuer Filme und Serien werden erstellt.", "ca. 2-5 Minuten")
        kodi_library.setup_kodi_sources(show_dialog=False)

        update_setup_progress(progress, 72, "Bibliotheksinhalt wird fuer Filme und Serien gesetzt.", "ca. 2-5 Minuten")
        kodi_library.setup_video_library_content(show_dialog=False)

        update_setup_progress(progress, 84, "Live-TV wird fuer deine Sprachauswahl vorbereitet.", "ca. 3-10 Minuten")
        progress.close()

        import live_tv
        live_tv.setup_live_tv(reset_data=True, show_dialog=False)

        progress = xbmcgui.DialogProgress()
        progress.create("Xtream IPTV Ultimate", "Einrichtung wird abgeschlossen...")
        update_setup_progress(progress, 95, "Kodi sucht nach neuen Bibliotheksinhalten.", "ca. 1-2 Minuten")
        kodi_library.scan_kodi_library(show_notification=False)

        update_setup_progress(progress, 100, "Einrichtung abgeschlossen.", "fertig")
        save_setup_state({"completed": True})
    except Exception as e:
        xbmcgui.Dialog().ok("Einrichtung", "Einrichtung konnte nicht abgeschlossen werden:\n\n" + str(e))
        return False
    finally:
        progress.close()

    xbmcgui.Dialog().ok(
        "Einrichtung abgeschlossen",
        "Xtream IPTV Ultimate ist eingerichtet.\n\n"
        "Du kannst nun Filme und Serien suchen oder den Index im Hintergrund aktualisieren lassen."
    )
    return True
