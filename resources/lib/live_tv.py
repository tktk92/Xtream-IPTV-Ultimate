# -*- coding: utf-8 -*-

import os
import re
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from common import ADDON_PROFILE
from common import get_setting
from config import get_selected_languages
from language_filter import extract_language_from_category
from strm import ensure_folder, write_text_file
import xtream


IPTV_SIMPLE_ID = "pvr.iptvsimple"
IPTV_SIMPLE_PROFILE = "special://profile/addon_data/" + IPTV_SIMPLE_ID
IPTV_SIMPLE_INSTANCE_NAME = "Xtream IPTV Ultimate"


def _m3u_path():
    folder = ensure_folder(xbmcvfs.translatePath(ADDON_PROFILE))
    return os.path.join(folder, "live_tv.m3u8")


def _iptv_simple_profile_folder():
    return ensure_folder(xbmcvfs.translatePath(IPTV_SIMPLE_PROFILE))


def _instance_settings_path():
    folder = _iptv_simple_profile_folder()
    used_ids = []

    try:
        files = os.listdir(folder)
    except Exception:
        files = []

    for filename in files:
        if not filename.startswith("instance-settings-") or not filename.endswith(".xml"):
            continue

        instance_id = filename.replace("instance-settings-", "").replace(".xml", "")
        if instance_id.isdigit():
            used_ids.append(int(instance_id))

        path = os.path.join(folder, filename)
        try:
            root = ET.parse(path).getroot()
            name_node = root.find("./setting[@id='kodi_addon_instance_name']")
            if name_node is not None and _xml_text(name_node.text) == IPTV_SIMPLE_INSTANCE_NAME:
                return path
        except Exception:
            continue

    next_id = max(used_ids or [0]) + 1
    return os.path.join(folder, "instance-settings-" + str(next_id) + ".xml")


def _xml_text(value):
    return "" if value is None else str(value)


def _set_setting(root, setting_id, value):
    node = root.find("./setting[@id='" + setting_id + "']")
    if node is None:
        node = ET.SubElement(root, "setting", {"id": setting_id})

    node.attrib.pop("default", None)
    node.text = _xml_text(value)
    return node


def _escape_attr(value):
    return _xml_text(value).replace('"', "'").replace("\r", " ").replace("\n", " ").strip()


def _clean_line(value):
    return _xml_text(value).replace("\r", " ").replace("\n", " ").strip()


def _epg_url():
    server = get_setting("server_url").rstrip("/")
    username = get_setting("username")
    password = get_setting("password")

    if not server or not username or not password:
        return ""

    return "{0}/xmltv.php?username={1}&password={2}".format(server, username, password)


def clean_channel_name(name):
    clean = _clean_line(name) or "Unbekannt"
    clean = clean.replace("â”ƒ", " ").replace("┃", " ").replace("|", " ").replace("│", " ")
    clean = clean.replace("âº", " ").replace("►", " ")
    language_prefixes = (
        "DE|CH|GER|DEU|GERMAN|GERMANY|DEUTSCH|SWISS|SCHWEIZ|"
        "AR|ARA|ARABIC|EN|ENG|ENGLISH|UK|US|"
        "FR|FRENCH|ES|SPANISH|IT|ITALIAN|TR|TURKISH|"
        "IN|HI|HINDI|TA|TAM|TAMIL|RU|AL|EXYU|YU|MULTI"
    )

    changed = True
    while changed:
        old = clean
        clean = re.sub(
            r'^\s*[\[\(\{]?\s*(' + language_prefixes + r')\s*[\]\)\}]?\s*(?:[-_|:•]+|\s{2,})\s*',
            "",
            clean,
            flags=re.IGNORECASE
        )
        clean = re.sub(
            r'^\s*[\[\(\{]\s*(' + language_prefixes + r')\s*[\]\)\}]\s*',
            "",
            clean,
            flags=re.IGNORECASE
        )
        clean = re.sub(
            r'^\s*(' + language_prefixes + r')\b\s+',
            "",
            clean,
            flags=re.IGNORECASE
        )
        changed = old != clean

    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" -_|:.") or _clean_line(name) or "Unbekannt"


def clean_group_name(name):
    clean = clean_channel_name(name)
    clean = re.sub(r"\bZUR[ÜU]CKBLICKEN\b", "Replay", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" -_|:.") or clean_channel_name(name)


def get_allowed_categories():
    categories = xtream.api("get_live_categories")
    selected_languages = get_selected_languages()
    allowed = []

    for category in categories:
        name = category.get("category_name", "Unbekannt")
        language = extract_language_from_category(name)

        if selected_languages and language not in selected_languages:
            continue

        category["language_name"] = language
        allowed.append(category)

    return allowed


def build_m3u():
    categories = get_allowed_categories()
    if not categories:
        return "", 0

    lines = ["#EXTM3U"]
    total = 0

    progress = xbmcgui.DialogProgress()
    progress.create("Live TV", "Lade Live-TV Sender...")

    try:
        for index, category in enumerate(categories):
            if progress.iscanceled():
                break

            category_id = category.get("category_id")
            category_name = category.get("category_name", "Unbekannt")
            progress.update(int((index + 1) / len(categories) * 100), category_name)

            streams = xtream.api("get_live_streams", {"category_id": category_id}, show_error=False)
            for stream in streams:
                stream_id = stream.get("stream_id")
                if not stream_id:
                    continue

                name = clean_channel_name(stream.get("name", "Unbekannt"))
                logo = _escape_attr(stream.get("stream_icon", ""))
                epg_id = _escape_attr(stream.get("epg_channel_id", ""))
                group = _escape_attr(clean_group_name(category_name))
                stream_url = _clean_line(stream.get("direct_source")) or xtream.live_url(stream_id, "ts")

                lines.append(
                    '#EXTINF:-1 tvg-id="{0}" tvg-name="{1}" tvg-logo="{2}" group-title="{3}",{4}'.format(
                        epg_id,
                        _escape_attr(name),
                        logo,
                        group,
                        name
                    )
                )
                lines.append(stream_url)
                total += 1
    finally:
        progress.close()

    return "\n".join(lines) + "\n", total


def write_live_tv_m3u():
    content, total = build_m3u()
    if not content or total <= 0:
        xbmcgui.Dialog().ok("Live TV", "Keine Live-TV Sender fuer die ausgewaehlten Sprachen gefunden.")
        return None, 0

    path = _m3u_path()
    write_text_file(path, content)
    xbmc.log("LIVE TV M3U ERSTELLT: " + path + " | Sender=" + str(total), xbmc.LOGINFO)
    return path, total


def _write_iptv_simple_instance(m3u_path):
    instance_path = _instance_settings_path()
    epg_url = _epg_url()

    if os.path.exists(instance_path):
        try:
            tree = ET.parse(instance_path)
            root = tree.getroot()
        except Exception:
            root = ET.Element("settings", {"version": "2"})
            tree = ET.ElementTree(root)
    else:
        root = ET.Element("settings", {"version": "2"})
        tree = ET.ElementTree(root)

    root.set("version", "2")
    _set_setting(root, "kodi_addon_instance_name", IPTV_SIMPLE_INSTANCE_NAME)
    _set_setting(root, "kodi_addon_instance_enabled", "true")
    _set_setting(root, "m3uPathType", "0")
    _set_setting(root, "m3uPath", m3u_path)
    _set_setting(root, "m3uUrl", "")
    _set_setting(root, "m3uCache", "false")
    _set_setting(root, "m3uRefreshMode", "0")
    _set_setting(root, "defaultProviderName", IPTV_SIMPLE_INSTANCE_NAME)
    _set_setting(root, "epgPathType", "1")
    _set_setting(root, "epgPath", "")
    _set_setting(root, "epgUrl", epg_url)
    _set_setting(root, "epgCache", "true")
    _set_setting(root, "epgIgnoreCaseForChannelIds", "true")
    _set_setting(root, "logoPathType", "1")
    _set_setting(root, "logoPath", "")
    _set_setting(root, "logoBaseUrl", "")

    tree.write(instance_path, encoding="utf-8", xml_declaration=True)
    xbmc.log("IPTV SIMPLE INSTANCE UPDATED: " + instance_path, xbmc.LOGINFO)
    return instance_path


def _configure_legacy_settings(m3u_path):
    try:
        addon = xbmcaddon.Addon(IPTV_SIMPLE_ID)
        epg_url = _epg_url()
        addon.setSetting("m3uPathType", "0")
        addon.setSetting("m3uPath", m3u_path)
        addon.setSetting("m3uUrl", "")
        addon.setSetting("m3uCache", "false")
        addon.setSetting("m3uRefreshMode", "0")
        addon.setSetting("epgPathType", "1")
        addon.setSetting("epgPath", "")
        addon.setSetting("epgUrl", epg_url)
        addon.setSetting("epgCache", "true")
        addon.setSetting("epgIgnoreCaseForChannelIds", "true")
    except Exception as e:
        xbmc.log("IPTV SIMPLE LEGACY SETTINGS ERROR: " + str(e), xbmc.LOGWARNING)


def _enable_iptv_simple():
    xbmc.executebuiltin("InstallAddon(" + IPTV_SIMPLE_ID + ")", True)
    xbmc.executebuiltin("EnableAddon(" + IPTV_SIMPLE_ID + ")", True)


def _reload_pvr():
    xbmc.executebuiltin("StartPVRManager")
    xbmc.executebuiltin("StopPVRManager")
    xbmc.executebuiltin("StartPVRManager")


def setup_live_tv():
    m3u_path, total = write_live_tv_m3u()
    if not m3u_path:
        return

    _write_iptv_simple_instance(m3u_path)
    _configure_legacy_settings(m3u_path)
    _enable_iptv_simple()
    _reload_pvr()

    xbmcgui.Dialog().ok(
        "Live TV",
        "Live TV wurde eingerichtet.\n\nSender: {0}\n\nFalls Kodi die Sender nicht sofort zeigt, Kodi einmal neu starten.".format(total)
    )
