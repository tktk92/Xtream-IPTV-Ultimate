# -*- coding: utf-8 -*-

import json
import time

import xbmc
import xbmcaddon
import xbmcgui


ARCTIC_ZEPHYR_RELOADED_ID = "skin.arctic.zephyr.mod"
ARCTIC_ZEPHYR_RELOADED_NAME = "Arctic: Zephyr - Reloaded"


def _is_addon_installed(addon_id):
    return xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id)


def _json_rpc(method, params=None):
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


def _get_active_skin():
    data = _json_rpc("Settings.GetSettingValue", {"setting": "lookandfeel.skin"})
    return data.get("result", {}).get("value", "")


def _set_active_skin(skin_id):
    data = _json_rpc(
        "Settings.SetSettingValue",
        {
            "setting": "lookandfeel.skin",
            "value": skin_id,
        },
    )
    return data.get("result") == "OK"


def _wait_for_addon(addon_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_addon_installed(addon_id):
            return True
        xbmc.sleep(1000)
    return _is_addon_installed(addon_id)


def _open_skin_settings():
    xbmc.executebuiltin("ActivateWindow(interfacesettings)")
    xbmc.sleep(500)
    xbmc.executebuiltin("SetFocus(30)")


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

    if not _wait_for_addon(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Der Skin konnte nicht installiert werden.",
            "Bitte pruefe, ob das offizielle Kodi-Repository aktiviert ist.",
        )
        return

    try:
        xbmcaddon.Addon(ARCTIC_ZEPHYR_RELOADED_ID)
    except Exception:
        xbmc.executebuiltin("EnableAddon(%s)" % ARCTIC_ZEPHYR_RELOADED_ID, True)

    switch = dialog.yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Der Skin ist installiert.",
        "Jetzt als Kodi-Skin aktivieren?",
    )
    if not switch:
        return

    active_skin = _get_active_skin()
    if active_skin == ARCTIC_ZEPHYR_RELOADED_ID:
        dialog.notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Skin ist bereits aktiv",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
        return

    changed = _set_active_skin(ARCTIC_ZEPHYR_RELOADED_ID)
    xbmc.sleep(1500)

    if changed and _get_active_skin() == ARCTIC_ZEPHYR_RELOADED_ID:
        dialog.notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Skin aktiviert",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
    else:
        _open_skin_settings()
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Kodi hat den Skin-Wechsel nicht automatisch uebernommen.",
            "Die Skin-Einstellungen wurden geoeffnet. Bitte Arctic: Zephyr - Reloaded dort auswaehlen.",
        )
