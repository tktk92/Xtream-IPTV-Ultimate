# -*- coding: utf-8 -*-

import json
import os

import xbmcgui
import xbmcvfs

import kodi_library
from common import ADDON, ADDON_PROFILE
from config import ALL_LANGUAGES, get_selected_languages, set_selected_languages

SETUP_STATE_FILE = os.path.join(ADDON_PROFILE, "setup_state.json")


def choose_languages():
    selected = get_selected_languages()
    labels = []

    for lang in ALL_LANGUAGES:
        labels.append(("[x] " if lang in selected else "[ ] ") + lang)

    indexes = xbmcgui.Dialog().multiselect("Sprachen auswählen", labels)

    if indexes is None:
        return

    new_selected = [ALL_LANGUAGES[index] for index in indexes]
    set_selected_languages(new_selected)

    if new_selected:
        xbmcgui.Dialog().ok("Gespeichert", "Aktive Sprachen:\n\n" + "\n".join(new_selected))
    else:
        xbmcgui.Dialog().ok("Gespeichert", "Keine Sprache ausgewählt.\nEs wird wieder alles angezeigt.")


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


def run_setup_wizard(force=False):
    if not force and is_setup_completed() and has_credentials():
        return False

    start = xbmcgui.Dialog().yesno(
        "Xtream IPTV Ultimate",
        "Ersteinrichtung starten?\n\n"
        "Das Addon fragt deine IPTV-Zugangsdaten ab und richtet die Kodi-Quellen fuer Filme und Serien ein.",
        nolabel="Spaeter",
        yeslabel="Einrichten"
    )
    if not start:
        return False

    server = input_text("IPTV Server URL", ADDON.getSetting("server_url").strip())
    if not server:
        xbmcgui.Dialog().notification("Einrichtung", "Server URL fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    username = input_text("IPTV Benutzername", ADDON.getSetting("username").strip())
    if not username:
        xbmcgui.Dialog().notification("Einrichtung", "Benutzername fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    password = input_text("IPTV Passwort", ADDON.getSetting("password").strip(), hidden=True)
    if not password:
        xbmcgui.Dialog().notification("Einrichtung", "Passwort fehlt", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    ADDON.setSetting("server_url", server.rstrip("/"))
    ADDON.setSetting("username", username)
    ADDON.setSetting("password", password)

    choose_lang = xbmcgui.Dialog().yesno(
        "Sprache",
        "Moechtest du jetzt auswaehlen, welche Sprache indexiert und angezeigt werden soll?",
        nolabel="Spaeter",
        yeslabel="Auswaehlen"
    )
    if choose_lang:
        choose_languages()

    install_scrapers = xbmcgui.Dialog().yesno(
        "Kodi Scraper",
        "Sollen die offiziellen Kodi-Scraper fuer Filme und Serien installiert werden?\n\n"
        "Filme: The Movie Database Python\n"
        "Serien: TMDb TV Shows",
        nolabel="Nein",
        yeslabel="Installieren"
    )
    if install_scrapers:
        kodi_library.install_metadata_scrapers(show_dialog=True)

    setup_sources = xbmcgui.Dialog().yesno(
        "Kodi Quellen",
        "Sollen die Quellen fuer Filme und Serien jetzt automatisch in Kodi eingerichtet werden?",
        nolabel="Nein",
        yeslabel="Einrichten"
    )
    if setup_sources:
        kodi_library.setup_kodi_sources()

    setup_live_tv = xbmcgui.Dialog().yesno(
        "Live TV",
        "Sollen die Live-TV Sender fuer die ausgewaehlten Sprachen direkt in Kodi Live-TV eingerichtet werden?",
        nolabel="Nein",
        yeslabel="Einrichten"
    )
    if setup_live_tv:
        import live_tv
        live_tv.setup_live_tv(reset_data=True)

    save_setup_state({"completed": True})
    xbmcgui.Dialog().ok(
        "Einrichtung abgeschlossen",
        "Xtream IPTV Ultimate ist eingerichtet.\n\n"
        "Du kannst nun Filme und Serien suchen oder den Index im Hintergrund aktualisieren lassen."
    )
    return True
