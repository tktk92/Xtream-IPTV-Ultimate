# -*- coding: utf-8 -*-

import json
import os
import socket
import time
import uuid
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from common import ADDON_PROFILE


ARCTIC_ZEPHYR_RELOADED_ID = "skin.xtream.ultimate"
ARCTIC_ZEPHYR_RELOADED_NAME = "Ultimate IPTV"
YOUTUBE_ADDON_ID = "plugin.video.youtube"
YOUTUBE_ADDON_NAME = "YouTube"
SKINSHORTCUTS_ID = "script.skinshortcuts"
SKIN_SETUP_STATE_FILE = "skin_setup_state.json"
YOUTUBE_HTTP_PORT_RANGE = range(52152, 52252)

MAINMENU_ITEMS = (
    {
        "label": "Suchen",
        "default_id": "search",
        "icon": "special://skin/extras/icons/search.png",
        "action": "ActivateWindow(Videos,plugin://plugin.video.xtream.strm/?mode=search_all,return)",
    },
    {
        "label": "20342",
        "default_id": "movies",
        "icon": "special://skin/extras/icons/film.png",
        "action": "ActivateWindow(Videos,MovieTitles,return)",
    },
    {
        "label": "20343",
        "default_id": "tvshows",
        "icon": "special://skin/extras/icons/tv.png",
        "action": "ActivateWindow(Videos,TVShowTitles,return)",
    },
    {
        "label": "TV",
        "default_id": "livetv",
        "icon": "special://skin/extras/icons/livetv.png",
        "action": "ActivateWindow(Tvchannels)",
    },
)

MOVIE_WIDGETS = (
    {
        "label_id": "20342",
        "suffix": "",
        "name": "Filme fortsetzen",
        "widget": "InProgressMovies",
        "path": "special://skin/extras/playlists/InProgressMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".2",
        "name": "Tamil Filme",
        "widget": "TamilMovies",
        "path": "special://skin/extras/playlists/TamilMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".3",
        "name": "Action",
        "widget": "ActionMovies",
        "path": "special://skin/extras/playlists/ActionMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".4",
        "name": "Komoedie",
        "widget": "ComedyMovies",
        "path": "special://skin/extras/playlists/ComedyMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".5",
        "name": "Thriller",
        "widget": "ThrillerMovies",
        "path": "special://skin/extras/playlists/ThrillerMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".6",
        "name": "Drama",
        "widget": "DramaMovies",
        "path": "special://skin/extras/playlists/DramaMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".7",
        "name": "Horror",
        "widget": "HorrorMovies",
        "path": "special://skin/extras/playlists/HorrorMovies.xsp",
        "target": "video",
        "aspect": "Poster",
    },
    {
        "label_id": "20342",
        "suffix": ".8",
        "name": "Sci-Fi",
        "widget": "SciFiMovies",
        "path": "special://skin/extras/playlists/SciFiMovies.xsp",
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
    "NetflixTrailerDelay": "2",
}

NETFLIX_STYLE_BOOL_SETTINGS = {
    "homemenu.netflix": True,
    "home.vertical": True,
    "home.vertical.widgets": True,
    "furniture.coloredicons": False,
    "osd.coloredicons": False,
    "tmdbhelper.enablecolors": False,
    "items.focus.glow": False,
    "items.focus.glow.low": False,
    "items.focus.glow.full": False,
    "items.focus.zoom": True,
    "global.showvideo": False,
    "background.video.fix.audio.errors": False,
    "home.netflix.autoplay.trailer": True,
    "home.netflix.autoplay.trailer.custom.window": False,
    "home.netflix.autoplay.trailer.custom.window.force": False,
    "trailer.dont.stop.on.unfocus": False,
    "playtrailerwindowed": False,
    "extended.nowplaying.videowindow": False,
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


def _install_and_enable_addon(addon_id, timeout=90):
    if not _is_addon_installed(addon_id):
        xbmc.executebuiltin("InstallAddon(%s)" % addon_id, True)

    if not _wait_for_addon(addon_id, timeout=timeout):
        return False

    try:
        xbmcaddon.Addon(addon_id)
    except Exception:
        xbmc.executebuiltin("EnableAddon(%s)" % addon_id, True)

    return _wait_for_addon(addon_id, timeout=10)


def _port_is_free(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _find_youtube_http_port(current_port=""):
    try:
        current = int(str(current_port or "").strip())
        if current > 0 and _port_is_free("127.0.0.1", current):
            return current
    except Exception:
        pass

    for port in YOUTUBE_HTTP_PORT_RANGE:
        if _port_is_free("127.0.0.1", port):
            return port

    return 52152


def _write_json_if_missing(path, data):
    if os.path.exists(path):
        return False

    _ensure_parent(path)
    with open(path, "w") as handle:
        json.dump(data, handle, indent=4, sort_keys=True)
    return True


def _ensure_youtube_json_store():
    profile_path = xbmcvfs.translatePath("special://profile/addon_data/{0}".format(YOUTUBE_ADDON_ID))
    if not profile_path:
        return 0

    user_id = uuid.uuid4().hex
    created = 0
    access_manager_path = os.path.join(profile_path, "access_manager.json")
    api_keys_path = os.path.join(profile_path, "api_keys.json")

    access_manager_data = {
        "access_manager": {
            "current_user": 0,
            "developers": {},
            "last_origin": YOUTUBE_ADDON_ID,
            "users": {
                "0": {
                    "access_token": "",
                    "id": user_id,
                    "last_key_hash": "",
                    "name": "Default",
                    "refresh_token": "",
                    "token_expires": -1,
                    "watch_history": "HL",
                    "watch_later": "WL",
                }
            },
        }
    }
    api_keys_data = {
        "keys": {
            "developer": {},
            "user": {
                "api_key": "",
                "client_id": "",
                "client_secret": "",
            },
        }
    }

    if _write_json_if_missing(access_manager_path, access_manager_data):
        created += 1
    if _write_json_if_missing(api_keys_path, api_keys_data):
        created += 1

    return created


def configure_youtube_http_server(show_dialog=False):
    if not _is_addon_installed(YOUTUBE_ADDON_ID):
        return False

    try:
        addon = xbmcaddon.Addon(YOUTUBE_ADDON_ID)
        current_port = addon.getSetting("kodion.http.port")
        port = _find_youtube_http_port(current_port)
        created_json_files = _ensure_youtube_json_store()
        addon.setSetting("kodion.http.listen", "127.0.0.1")
        addon.setSetting("kodion.http.port", str(port))
        addon.setSetting("kodion.setup_wizard", "false")
        addon.setSetting("youtube.api.config.page", "false")
        addon.setSetting("youtube.allow.dev.keys", "true")
        addon.setSetting("youtube.folder.my_subscriptions.sources", "subscriptions,saved_playlists,bookmark_channels,bookmark_playlists")
        addon.setSetting("kodion.support.alternative_player", "false")
        xbmc.log(
            "[IPTV Addon] YouTube fuer Trailer konfiguriert: 127.0.0.1:{0}, JSON-Dateien angelegt={1}".format(
                port,
                created_json_files,
            ),
            xbmc.LOGINFO,
        )
        if show_dialog:
            xbmcgui.Dialog().notification(
                YOUTUBE_ADDON_NAME,
                "Trailer-Wiedergabe vorbereitet",
                xbmcgui.NOTIFICATION_INFO,
                4000,
            )
        return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] YouTube HTTP-Server Konfiguration fehlgeschlagen: %s" % exc, xbmc.LOGWARNING)
        return False


def _open_skin_settings():
    xbmc.executebuiltin("ActivateWindow(interfacesettings)")
    xbmc.sleep(500)
    xbmc.executebuiltin("SetFocus(30)")


def _yesno(title, message="", nolabel="Abbrechen", yeslabel="Ja"):
    return xbmcgui.Dialog().yesno(title, message, nolabel=nolabel, yeslabel=yeslabel)


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


def _kodi_database_folder():
    return _translate("special://profile/Database")


def _kodi_thumbnails_folder():
    return _translate("special://profile/Thumbnails")


def _skin_setup_state_path():
    return _translate("%s/%s" % (ADDON_PROFILE, SKIN_SETUP_STATE_FILE))


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


def _load_json_object(path):
    if not os.path.exists(path):
        return {}
    try:
        data = json.loads(_read_text(path))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json_object(path, data):
    _write_text(path, json.dumps(data, indent=4, sort_keys=True))


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
    root = ET.Element("shortcuts")
    for menu_item in MAINMENU_ITEMS:
        shortcut = ET.SubElement(root, "shortcut")
        ET.SubElement(shortcut, "label").text = menu_item["label"]
        ET.SubElement(shortcut, "label2").text = "Ultimate IPTV Shortcut"
        ET.SubElement(shortcut, "defaultID").text = menu_item["default_id"]
        ET.SubElement(shortcut, "icon").text = menu_item["icon"]
        ET.SubElement(shortcut, "action").text = menu_item["action"]

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

    for widget in MOVIE_WIDGETS + TV_WIDGETS:
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
    for setting_id, value in NETFLIX_STYLE_SETTINGS.items():
        xbmc.executebuiltin("Skin.SetString(%s,%s)" % (setting_id, value))

    for setting_id, value in NETFLIX_STYLE_BOOL_SETTINGS.items():
        if value:
            xbmc.executebuiltin("Skin.SetBool(%s)" % setting_id)
        else:
            xbmc.executebuiltin("Skin.Reset(%s)" % setting_id)

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


def _remove_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] Skin Cache Datei konnte nicht geloescht werden: %s | %s" % (path, exc), xbmc.LOGWARNING)
    return False


def _clear_directory_files(path):
    removed = 0
    if not os.path.isdir(path):
        return removed

    for root, _dirs, files in os.walk(path):
        for filename in files:
            if _remove_file(os.path.join(root, filename)):
                removed += 1

    return removed


def _clear_texture_cache():
    removed = 0
    database_folder = _kodi_database_folder()
    if os.path.isdir(database_folder):
        for filename in os.listdir(database_folder):
            if filename.startswith("Textures") and filename.endswith(".db"):
                if _remove_file(os.path.join(database_folder, filename)):
                    removed += 1

    removed += _clear_directory_files(_kodi_thumbnails_folder())
    xbmc.log("[IPTV Addon] Skin Texture Cache bereinigt: " + str(removed), xbmc.LOGINFO)
    return removed


def _reload_skinshortcuts_and_skin():
    xbmcgui.Window(10000).setProperty("skinshortcuts-reloadmainmenu", "True")
    xbmc.executebuiltin(
        "RunScript(script.skinshortcuts,type=buildxml&mainmenuID=300&group=mainmenu|x1111|x1112|x1113|x1114|x1115|x1116|x1117|x1118|x1119|powermenu&levels=6)",
        True,
    )
    xbmc.executebuiltin("ReloadSkin()")


def _mark_skin_setup_applied():
    version = xbmcaddon.Addon().getAddonInfo("version")
    _save_json_object(_skin_setup_state_path(), {"addon_version": version, "applied_at": int(time.time())})


def _apply_arctic_zephyr_reloaded_settings(clear_cache=True):
    _configure_mainmenu_visibility()
    _configure_widgets()
    _configure_netflix_colors()
    if clear_cache:
        _clear_texture_cache()
    _reload_skinshortcuts_and_skin()
    _mark_skin_setup_applied()


def install_youtube_addon(show_dialog=True):
    if _install_and_enable_addon(YOUTUBE_ADDON_ID):
        configure_youtube_http_server(show_dialog=False)
        if show_dialog:
            xbmcgui.Dialog().notification(
                YOUTUBE_ADDON_NAME,
                "Addon ist installiert",
                xbmcgui.NOTIFICATION_INFO,
                4000,
            )
        return True

    if show_dialog:
        xbmcgui.Dialog().ok(
            YOUTUBE_ADDON_NAME,
            "Das YouTube-Addon konnte nicht installiert werden.",
            "Bitte pruefe, ob das offizielle Kodi-Repository aktiviert ist.",
        )
    return False


def setup_arctic_zephyr_reloaded(show_dialog=False):
    if not _install_and_enable_addon(ARCTIC_ZEPHYR_RELOADED_ID):
        if show_dialog:
            xbmcgui.Dialog().ok(
                ARCTIC_ZEPHYR_RELOADED_NAME,
                "Der Skin konnte nicht installiert werden.",
                "Bitte pruefe, ob das offizielle Kodi-Repository aktiviert ist.",
            )
        return False

    if _get_active_skin() != ARCTIC_ZEPHYR_RELOADED_ID:
        _set_active_skin(ARCTIC_ZEPHYR_RELOADED_ID)
        xbmc.sleep(1500)

    if _get_active_skin() != ARCTIC_ZEPHYR_RELOADED_ID:
        if show_dialog:
            _open_skin_settings()
            xbmcgui.Dialog().ok(
                ARCTIC_ZEPHYR_RELOADED_NAME,
                "Kodi hat den Skin-Wechsel nicht automatisch uebernommen.",
                "Die Skin-Einstellungen wurden geoeffnet. Bitte Ultimate IPTV dort auswaehlen.",
            )
        return False

    _apply_arctic_zephyr_reloaded_settings(clear_cache=True)
    if show_dialog:
        xbmcgui.Dialog().notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Skin, Widgets und Auto-Trailer eingerichtet",
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
    return True


def apply_arctic_zephyr_reloaded_after_update():
    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        return False

    if _get_active_skin() != ARCTIC_ZEPHYR_RELOADED_ID:
        return False

    version = xbmcaddon.Addon().getAddonInfo("version")
    state = _load_json_object(_skin_setup_state_path())
    if state.get("addon_version") == version:
        return False

    try:
        _apply_arctic_zephyr_reloaded_settings(clear_cache=True)
        xbmc.log("[IPTV Addon] Ultimate IPTV Skin nach Addon-Update aktualisiert: " + version, xbmc.LOGINFO)
        return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] Ultimate IPTV Skin Auto-Update fehlgeschlagen: %s" % exc, xbmc.LOGERROR)
        return False


def configure_arctic_zephyr_reloaded():
    dialog = xbmcgui.Dialog()

    if not _is_addon_installed(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Bitte installiere den Skin zuerst ueber den Ultimate-IPTV-Menuepunkt.",
        )
        return

    confirm = _yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Im Hauptmenue bleiben nur Suchen, Filme, Serien und TV sichtbar.\n\n"
        "Einstellungen und Power werden als Icon-Buttons unten links gesetzt.\n\n"
        "Widgets, dunkle Netflix-Farben, rote Akzente und der Icon-Cache werden gesetzt.\n\n"
        "Soll die Skin-Konfiguration jetzt geschrieben werden?",
        nolabel="Abbrechen",
        yeslabel="Fortfahren",
    )
    if not confirm:
        return

    try:
        _apply_arctic_zephyr_reloaded_settings(clear_cache=True)
        dialog.notification(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Hauptmenue, Quick-Icons, Widgets, Farben, Hintergrundvideo und Icon-Cache gesetzt",
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
            "Der Skin wird aus dem offiziellen Kodi-Repository installiert.\n\n"
            "Installation jetzt starten?",
            nolabel="Abbrechen",
            yeslabel="Installieren",
        )
        if not install:
            return

        xbmc.executebuiltin("InstallAddon(%s)" % ARCTIC_ZEPHYR_RELOADED_ID, True)

    if not _wait_for_addon(ARCTIC_ZEPHYR_RELOADED_ID):
        dialog.ok(
            ARCTIC_ZEPHYR_RELOADED_NAME,
            "Der Skin konnte nicht installiert werden.",
            "Bitte pruefe, ob das Xtream IPTV Ultimate Repository aktiviert ist.",
        )
        return

    try:
        xbmcaddon.Addon(ARCTIC_ZEPHYR_RELOADED_ID)
    except Exception:
        xbmc.executebuiltin("EnableAddon(%s)" % ARCTIC_ZEPHYR_RELOADED_ID, True)

    switch = _yesno(
        ARCTIC_ZEPHYR_RELOADED_NAME,
        "Der Skin ist installiert.\n\nJetzt als Kodi-Skin aktivieren?",
        nolabel="Abbrechen",
        yeslabel="Aktivieren",
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
            "Die Skin-Einstellungen wurden geoeffnet. Bitte Ultimate IPTV dort auswaehlen.",
        )
