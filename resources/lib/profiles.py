# -*- coding: utf-8 -*-

import json
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from common import ADDON_ID, ADDON_PROFILE


PROFILE_DEFINITIONS = (
    {
        "name": "Erwachsene",
        "directory": "profiles/Erwachsene/",
        "content_profile": "adult",
    },
    {
        "name": "Kinder",
        "directory": "profiles/Kinder/",
        "content_profile": "kids",
    },
    {
        "name": "Gast",
        "directory": "profiles/Gast/",
        "content_profile": "guest",
    },
)

PROFILE_SETUP_STATE_FILE = "profile_setup_state.json"


def _translate(path):
    return xbmcvfs.translatePath(path)


def _master_profile_path(*parts):
    return os.path.join(_translate("special://masterprofile/"), *parts)


def _profile_path(profile_def, *parts):
    directory = profile_def["directory"].replace("/", os.sep).strip(os.sep)
    return _master_profile_path(directory, *parts)


def _ensure_dir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4, sort_keys=True)


def _profile_setup_state_path():
    return _translate("%s/%s" % (ADDON_PROFILE, PROFILE_SETUP_STATE_FILE))


def _current_addon_version():
    try:
        return xbmcaddon.Addon().getAddonInfo("version")
    except Exception:
        return ""


def _load_profile_setup_state():
    return _read_json(_profile_setup_state_path())


def _save_profile_setup_state(data):
    _write_json(_profile_setup_state_path(), data)


def _write_xml(path, root):
    _ensure_dir(os.path.dirname(path))
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(path, encoding="UTF-8", xml_declaration=False)


def _safe_setting_value(value):
    return "" if value is None else str(value)


def _setting_node(root, setting_id):
    node = root.find("./setting[@id='%s']" % setting_id)
    if node is None:
        node = ET.SubElement(root, "setting", {"id": setting_id})
    return node


def _write_addon_settings(profile_def):
    addon = xbmcaddon.Addon()
    settings_path = _profile_path(profile_def, "addon_data", ADDON_ID, "settings.xml")
    _ensure_dir(os.path.dirname(settings_path))

    root = ET.Element("settings", {"version": "2"})
    for setting_id in (
        "server_url",
        "username",
        "password",
        "tmdb_api_key",
        "auto_tmdb_recent_import",
        "auto_tmdb_recent_limit_per_language",
        "auto_tmdb_recent_months",
        "auto_tmdb_recent_max_pages",
        "live_tv_check_streams",
    ):
        _setting_node(root, setting_id).text = _safe_setting_value(addon.getSetting(setting_id))

    _write_xml(settings_path, root)


def _write_profile_config(profile_def):
    master_config = _master_profile_path("addon_data", ADDON_ID, "config.json")
    profile_config = _profile_path(profile_def, "addon_data", ADDON_ID, "config.json")
    data = _read_json(master_config)
    data["content_profile"] = profile_def["content_profile"]
    data.setdefault("selected_languages", [])
    _write_json(profile_config, data)


def _copy_if_exists(source, target):
    if not os.path.exists(source) or os.path.exists(target):
        return False
    _ensure_dir(os.path.dirname(target))
    shutil.copy2(source, target)
    return True


def _prepare_profile_folder(profile_def):
    base = _profile_path(profile_def)
    _ensure_dir(base)
    _ensure_dir(os.path.join(base, "addon_data", ADDON_ID))
    _ensure_dir(os.path.join(base, "Database"))
    _ensure_dir(os.path.join(base, "Thumbnails"))

    _copy_if_exists(_master_profile_path("guisettings.xml"), os.path.join(base, "guisettings.xml"))
    _copy_if_exists(_master_profile_path("sources.xml"), os.path.join(base, "sources.xml"))
    _write_addon_settings(profile_def)
    _write_profile_config(profile_def)


def _profile_names(root):
    names = set()
    for node in root.findall("profile"):
        name = node.findtext("name")
        if name:
            names.add(name.strip().lower())
    return names


def _next_profile_id(root):
    ids = []
    for node in root.findall("profile"):
        text = node.findtext("id")
        if text and re.match(r"^\d+$", text):
            ids.append(int(text))
    next_id = max(ids + [-1]) + 1
    next_id_node = root.find("nextIdProfile")
    if next_id_node is not None and next_id_node.text and re.match(r"^\d+$", next_id_node.text):
        next_id = max(next_id, int(next_id_node.text))
    return next_id


def _ensure_text_node(root, tag, value):
    node = root.find(tag)
    if node is None:
        node = ET.SubElement(root, tag)
    node.text = str(value)
    return node


def _append_profile(root, profile_id, profile_def):
    node = ET.SubElement(root, "profile")
    ET.SubElement(node, "id").text = str(profile_id)
    ET.SubElement(node, "name").text = profile_def["name"]
    ET.SubElement(node, "directory", {"pathversion": "1"}).text = profile_def["directory"]
    ET.SubElement(node, "thumbnail", {"pathversion": "1"}).text = ""
    ET.SubElement(node, "hasdatabases").text = "true"
    ET.SubElement(node, "canwritedatabases").text = "true"
    ET.SubElement(node, "hassources").text = "true"
    ET.SubElement(node, "canwritesources").text = "true"
    ET.SubElement(node, "lockaddonmanager").text = "false"
    ET.SubElement(node, "locksettings").text = "0"
    ET.SubElement(node, "lockfiles").text = "false"
    ET.SubElement(node, "lockmusic").text = "false"
    ET.SubElement(node, "lockvideo").text = "false"
    ET.SubElement(node, "lockpictures").text = "false"
    ET.SubElement(node, "lockprograms").text = "false"
    ET.SubElement(node, "lockgames").text = "false"
    ET.SubElement(node, "lockmode").text = "0"
    ET.SubElement(node, "lockcode").text = ""
    ET.SubElement(node, "lastdate").text = ""


def setup_kodi_profiles(show_dialog=True):
    profiles_path = _master_profile_path("profiles.xml")
    if not os.path.exists(profiles_path):
        if show_dialog:
            xbmcgui.Dialog().ok("Profile", "Kodi profiles.xml wurde nicht gefunden.")
        return False

    backup_path = profiles_path + ".ultimate-backup-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(profiles_path, backup_path)

    root = ET.parse(profiles_path).getroot()
    names = _profile_names(root)
    next_id = _next_profile_id(root)
    added = []

    for profile_def in PROFILE_DEFINITIONS:
        _prepare_profile_folder(profile_def)
        if profile_def["name"].strip().lower() in names:
            continue
        _append_profile(root, next_id, profile_def)
        added.append(profile_def["name"])
        names.add(profile_def["name"].strip().lower())
        next_id += 1

    _ensure_text_node(root, "useloginscreen", "true")
    _ensure_text_node(root, "autologin", "-1")
    _ensure_text_node(root, "nextIdProfile", str(next_id))
    _write_xml(profiles_path, root)

    xbmc.log(
        "[IPTV Addon] Kodi Profile eingerichtet. Neu: {0}. Backup: {1}".format(
            ", ".join(added) if added else "keine",
            backup_path,
        ),
        xbmc.LOGINFO,
    )

    if show_dialog:
        message = (
            "LoginScreen wurde aktiviert.\n\n"
            "Profile: Erwachsene, Kinder, Gast\n\n"
            "Kodi sollte einmal neu gestartet werden, damit die Profilauswahl sicher vor dem Homescreen erscheint."
        )
        if added:
            message += "\n\nNeu angelegt: " + ", ".join(added)
        else:
            message += "\n\nDie Profile waren bereits vorhanden."
        xbmcgui.Dialog().ok("Profile eingerichtet", message)

    return True


def apply_profiles_after_update():
    version = _current_addon_version()
    state = _load_profile_setup_state()
    if state.get("addon_version") == version and state.get("completed"):
        return False

    try:
        if setup_kodi_profiles(show_dialog=False):
            _save_profile_setup_state({
                "addon_version": version,
                "completed": True,
                "applied_at": int(time.time()),
            })
            xbmc.log("[IPTV Addon] Kodi Profile automatisch eingerichtet: " + version, xbmc.LOGINFO)
            return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] Kodi Profil-Autoeinrichtung fehlgeschlagen: %s" % exc, xbmc.LOGERROR)

    return False
