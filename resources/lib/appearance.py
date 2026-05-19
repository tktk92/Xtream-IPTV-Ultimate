# -*- coding: utf-8 -*-

import json

import xbmc
import xbmcgui


ARCTIC_ZEPHYR_RELOADED_ID = "skin.arctic.zephyr.mod"
ARCTIC_ZEPHYR_RELOADED_NAME = "Arctic: Zephyr - Reloaded"


def _is_addon_installed(addon_id):
    return xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id)


def _set_active_skin(skin_id):
    payload = {
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "id": 1,
        "params": {
            "setting": "lookandfeel.skin",
            "value": skin_id,
        },
    }
    response = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        data = json.loads(response)
    except Exception:
        data = {}
    return data.get("result") == "OK"


def install_arctic_zephyr_reloaded():
    dialog = xbmcgui.Dialog()

    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        install = dialog.yesno(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Der Skin wird aus dem offiziellen Kodi-Repository installiert.",
            "Fortfahren?",
        )
        if not install:
            return

        xbmc.executebuiltin("InstallAddon(%s)" % ARCTIC_ZEPHYR_RELOADED_ID, True)

    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Der Skin konnte nicht installiert werden.",
            "Bitte pruefe, ob das offizielle Kodi-Repository aktiviert ist.",
        )
        return

    switch = dialog.yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Der Skin ist installiert.",
        "Jetzt als Kodi-Skin aktivieren?",
    )
    if not switch:
        return

    if _set_active_skin(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Skin-Wechsel gestartet",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
    else:
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Kodi konnte den Skin nicht automatisch aktivieren.",
            "Bitte waehle ihn unter Einstellungen > Benutzeroberflaeche > Skin aus.",
        )
