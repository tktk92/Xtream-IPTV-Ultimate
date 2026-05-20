# -*- coding: utf-8 -*-

import json
import os
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ARCTIC_ZEPHYR_RELOADED_ID = "skin.arctic.zephyr.mod"
ARCTIC_ZEPHYR_RELOADED_NAME = "Arctic: Zephyr - Reloaded"
SKINSHORTCUTS_ID = "script.skinshortcuts"

MAINMENU_ALLOWED_DEFAULT_IDS = ("movies", "tvshows", "settings", "power")

MOVIE_WIDGETS = (
    {
        "label_id": "20342",
        "suffix": "",
        "name": "Neue Filme",
        "widget": "NewMovies",
        "path": "special://skin/extras/playlists/NewMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".2",
        "name": "Filme fortsetzen",
        "widget": "InProgressMovies",
        "path": "special://skin/extras/playlists/InProgressMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
)

TV_WIDGETS = (
    {
        "label_id": "tvshows",
        "suffix": "",
        "name": "Serien fortsetzen",
        "widget": "InProgress",
        "path": "special://skin/extras/playlists/InProgressTvShows.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "tvshows",
        "suffix": ".2",
        "name": "Naechste Folgen",
        "widget": "InProgressEpisodes",
        "path": "special://skin/extras/playlists/InProgressEpisodes.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "tvshows",
        "suffix": ".3",
        "name": "Neue Serien",
        "widget": "NewTvShows",
        "path": "special://skin/extras/playlists/NewShows.xsp",
        "target": "video",
        "aspect": "Poster",
    },
)

SETTINGS_WIDGETS = (
    {
        "label_id": "settings",
        "suffix": "",
        "name": "Xtream IPTV Ultimate",
        "widget": "addon",
        "path": "plugin://plugin.video.xtream.strm/",
        "target": "video",
        "aspect": "Square",
        "type": "video",
    },
)

POWER_WIDGETS = (
    {
        "label_id": "33060",
        "suffix": "",
        "name": "",
        "widget": "custom",
        "path": "plugin://plugin.video.xtream.strm/?mode=empty_widget",
        "target": "video",
        "aspect": "Square",
        "type": "video",
    },
)

NETFLIX_STYLE_SETTINGS = {
    "colorpalette": "basic",
    "focuscolor.name": "FFE50914",
    "focuscolorotherbar.name": "FFE50914",
    "focuscolor2.name": "FFE50914",
    "selectbarcolor.name": "FFE50914",
    "selectotherbarcolor.name": "FFB20710",
    "squarecolor.name": "FF1A1A1A",
    "squarecolor2.name": "FFE50914",
    "kodilogocolor.name": "FFE50914",
    "kodilogocolorgradient.name": "FFB20710",
    "backgroundbrightness": "35",
    "backgroundbrightnessblur": "25",
}

NETFLIX_STYLE_BOOL_SETTINGS = {
    "homemenu.netflix": True,
    "furniture.coloredicons": False,
    "osd.coloredicons": False,
    "tmdbhelper.enablecolors": False,
    "items.focus.glow": False,
    "items.focus.glow.low": False,
    "items.focus.glow.full": False,
    "items.focus.zoom": True,
}


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


def _yesno(title, line1="", line2="", line3="", nolabel="Abbrechen", yeslabel="Ja"):
    return xbmcgui.Dialog().yesno(title, line1, line2, line3, nolabel, yeslabel)


def _translate(path):
    return xbmcvfs.translatePath(path)


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write_text(path, text):
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_xml(path, root):
    _ensure_parent(path)
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def _skinshortcuts_profile_path(filename):
    return _translate("special://profile/addon_data/%s/%s" % (SKINSHORTCUTS_ID, filename))


def _skin_profile_settings_path():
    return _translate("special://profile/addon_data/%s/settings.xml" % ARCTIC_ZEPHYR_RELOADED_ID)


def _skin_default_mainmenu_path():
    return _translate("special://home/addons/%s/shortcuts/mainmenu.DATA.xml" % ARCTIC_ZEPHYR_RELOADED_ID)


def _load_json_list(path):
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(_read_text(path))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json_list(path, data):
    _write_text(path, json.dumps(data, indent=4))


def _set_shortcut_property(properties, label_id, name, value, group="mainmenu"):
    properties[:] = [
        item for item in properties
        if not (
            len(item) >= 4
            and item[0] == group
            and item[1] == label_id
            and item[2] == name
        )
    ]
    properties.append([group, label_id, name, value])


def _configure_mainmenu_visibility():
    user_path = _skinshortcuts_profile_path("mainmenu.DATA.xml")
    source_path = user_path if os.path.exists(user_path) else _skin_default_mainmenu_path()
    root = ET.parse(source_path).getroot()

    for shortcut in root.findall("shortcut"):
        default_id = shortcut.findtext("defaultID")
        disabled = shortcut.find("disabled")
        if default_id in MAINMENU_ALLOWED_DEFAULT_IDS:
            if disabled is not None:
                shortcut.remove(disabled)
        elif disabled is None:
            ET.SubElement(shortcut, "disabled").text = "True"

    _write_xml(user_path, root)


def _configure_widgets():
    properties_path = _skinshortcuts_profile_path("%s.properties" % ARCTIC_ZEPHYR_RELOADED_ID)
    properties = _load_json_list(properties_path)
    properties = [
        item for item in properties
        if not (
            len(item) >= 3
            and item[0] == "mainmenu"
            and item[1] == "33060"
            and item[2].startswith("widget")
        )
    ]

    for widget in MOVIE_WIDGETS + TV_WIDGETS + SETTINGS_WIDGETS + POWER_WIDGETS:
        label_id = widget["label_id"]
        suffix = widget["suffix"]
        if suffix:
            _set_shortcut_property(properties, label_id, "widgetEnable%s" % suffix, "yes")

        _set_shortcut_property(properties, label_id, "widget%s" % suffix, widget["widget"])
        _set_shortcut_property(properties, label_id, "widgetName%s" % suffix, widget["name"])
        _set_shortcut_property(properties, label_id, "widgetPath%s" % suffix, widget["path"])
        _set_shortcut_property(properties, label_id, "widgetTarget%s" % suffix, widget["target"])
        _set_shortcut_property(properties, label_id, "widgetaspect%s" % suffix, widget["aspect"])
        widget_type = widget.get("type")
        if widget_type is None:
            widget_type = "movies" if label_id == "20342" else "tvshows"
        _set_shortcut_property(properties, label_id, "widgetType%s" % suffix, widget_type)

    _save_json_list(properties_path, properties)


def _setting_node(root, setting_id, setting_type):
    node = root.find("./setting[@id='%s']" % setting_id)
    if node is None:
        node = ET.SubElement(root, "setting", {"id": setting_id, "type": setting_type})
    else:
        node.set("type", setting_type)
    return node


def _configure_netflix_colors():
    settings_path = _skin_profile_settings_path()
    if os.path.exists(settings_path):
        root = ET.parse(settings_path).getroot()
    else:
        root = ET.Element("settings", {"version": "2"})

    for setting_id, value in NETFLIX_STYLE_SETTINGS.items():
        _setting_node(root, setting_id, "string").text = value

    for setting_id, value in NETFLIX_STYLE_BOOL_SETTINGS.items():
        _setting_node(root, setting_id, "bool").text = "true" if value else "false"

    _write_xml(settings_path, root)


def configure_arctic_zephyr_reloaded():
    dialog = xbmcgui.Dialog()

    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Bitte installiere den Skin zuerst ueber den Arctic-Zephyr-Menuepunkt.",
        )
        return

    confirm = _yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Im Hauptmenue bleiben nur Filme, Serien, Einstellungen und Power sichtbar.",
        "Widgets, dunkle Netflix-Farben und rote Akzente werden gesetzt.",
        "Soll die Skin-Konfiguration jetzt geschrieben werden?",
        "Abbrechen",
        "Fortfahren",
    )
    if not confirm:
        return

    try:
        _configure_mainmenu_visibility()
        _configure_widgets()
        _configure_netflix_colors()
        xbmcgui.Window(10000).setProperty("skinshortcuts-reloadmainmenu", "True")
        xbmc.executebuiltin(
            "RunScript(script.skinshortcuts,type=buildxml&mainmenuID=300&group=mainmenu|x1111|x1112|x1113|x1114|x1115|x1116|x1117|x1118|x1119|powermenu&levels=6)",
            True,
        )
        xbmc.executebuiltin("ReloadSkin()")
        dialog.notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Hauptmenue, Widgets und Farben gesetzt",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
    except Exception as exc:
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Die Skin-Konfiguration konnte nicht geschrieben werden.",
            str(exc),
        )


def install_arctic_zephyr_reloaded():
    dialog = xbmcgui.Dialog()

    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        install = _yesno(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Der Skin wird aus dem offiziellen Kodi-Repository installiert.",
            "Installation jetzt starten?",
            "",
            "Abbrechen",
            "Installieren",
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

    switch = _yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Der Skin ist installiert.",
        "Jetzt als Kodi-Skin aktivieren?",
        "",
        "Abbrechen",
        "Aktivieren",
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
