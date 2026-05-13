# -*- coding: utf-8 -*-

import xbmcgui

from common import ADDON
from config import ALL_LANGUAGES, get_selected_languages, set_selected_languages


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
