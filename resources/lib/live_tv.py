# -*- coding: utf-8 -*-

import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

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
LIVE_CHECK_WORKERS = 8
LIVE_CHECK_TIMEOUT = 5
PVR_DATABASE_PREFIXES = ("Epg", "TV")

EPG_NAME_MAP = {
    "ARD ALPHA": "ardalpha.de",
    "ARD-ALPHA": "ardalpha.de",
    "DAS ERSTE": "ard.de",
    "ARD": "ard.de",
    "ZDF NEO": "zdfneo.de",
    "ZDF INFO": "zdfinfo.de",
    "ZDF": "zdf.de",
    "RTL PASSION": "rtlpassion.de",
    "RTL CRIME": "rtlcrime.de",
    "RTL LIVING": "rtlliving.de",
    "RTL UP": "rtlplus.de",
    "RTL ZWEI": "rtl2.de",
    "RTLZWEI": "rtl2.de",
    "RTL": "rtl.de",
    "RTL II": "rtl2.de",
    "RTL2": "rtl2.de",
    "SAT.1 EMOTIONS": "sat1emotions.de",
    "SAT1 EMOTIONS": "sat1emotions.de",
    "SAT.1 GOLD": "sat1gold.de",
    "SAT1 GOLD": "sat1gold.de",
    "SAT.1": "sat1.de",
    "SAT1": "sat1.de",
    "PROSIEBEN MAXX": "prosiebenmaxx.de",
    "PRO7 MAXX": "prosiebenmaxx.de",
    "PROSIEBEN FUN": "prosiebenfun.de",
    "PRO7 FUN": "prosiebenfun.de",
    "PROSIEBEN": "pro7.de",
    "PRO7": "pro7.de",
    "VOX": "vox.de",
    "KABEL EINS": "kabel1.de",
    "KABEL 1": "kabel1.de",
    "ARTE": "arte.de",
    "SIXX": "sixx.de",
    "3SAT": "3sat.de",
    "NTV": "ntv.de",
    "WDR": "wdr.de",
    "NDR": "ndr.de",
    "SWR": "swrsr.de",
    "TAGESSCHAU24": "tagesschau24.de",
    "PHOENIX": "phoenix.de",
    "BR FERNSEHEN": "br.de",
    "NITRO": "rtlnitro.de",
    "DMAX": "dmax.de",
    "TELE 5": "tele5.de",
    "ANIXE": "anixe.de",
    "WELT": "welt.de",
    "MDR": "mdr.de",
    "NICKELODEON": "nickelodeon.de",
    "NICK TOONS": "nicktoons.de",
    "NICK JR": "nickjr.de",
    "DISNEY CHANNEL": "disneychannel.de",
    "CARTOON NETWORK": "cartoonnetwork.de",
    "SUPER RTL": "superrtl.de",
    "KIKA": "kika.de",
    "SKY ONE": "sky1.de",
}


def _m3u_path():
    folder = ensure_folder(xbmcvfs.translatePath(ADDON_PROFILE))
    return os.path.join(folder, "live_tv.m3u8")


def _iptv_simple_profile_folder():
    return ensure_folder(xbmcvfs.translatePath(IPTV_SIMPLE_PROFILE))


def _kodi_database_folder():
    return xbmcvfs.translatePath("special://profile/Database")


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


def _setting_bool(key, default=False):
    value = get_setting(key).lower()
    if value == "":
        return default
    return value in ("true", "1", "yes", "ja")


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


def normalize_epg_name(name):
    clean = clean_channel_name(name).upper()
    clean = re.sub(r"\b(4K|UHD|FHD|HD|SD)\b", " ", clean)
    clean = clean.replace("+", " PLUS")
    clean = re.sub(r"[^A-Z0-9. ]+", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def infer_epg_id(name):
    normalized = normalize_epg_name(name)
    if not normalized:
        return ""

    labels = sorted(EPG_NAME_MAP.keys(), key=lambda value: len(normalize_epg_name(value)), reverse=True)
    for label in labels:
        normalized_label = normalize_epg_name(label)
        if normalized == label or normalized.startswith(label + " "):
            return EPG_NAME_MAP[label]
        if normalized == normalized_label or normalized.startswith(normalized_label + " "):
            return EPG_NAME_MAP[label]

    return ""


def get_epg_id(stream, clean_name):
    epg_id = _clean_line(stream.get("epg_channel_id", ""))
    return epg_id or infer_epg_id(clean_name)


def stream_looks_playable(url):
    if not url:
        return False

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "VLC/3.0.18 LibVLC/3.0.18",
                "Range": "bytes=0-4095"
            }
        )
        response = urllib.request.urlopen(req, timeout=LIVE_CHECK_TIMEOUT)
        try:
            response.read(1)
        finally:
            response.close()
        return True
    except Exception:
        return False


def filter_playable_streams(items, progress=None):
    if not _setting_bool("live_tv_check_streams", False):
        return items, 0

    playable = []
    skipped = 0
    total = len(items)
    completed = 0

    with ThreadPoolExecutor(max_workers=LIVE_CHECK_WORKERS) as executor:
        futures = {
            executor.submit(stream_looks_playable, item.get("stream_url")): item
            for item in items
        }

        for future in as_completed(futures):
            item = futures[future]
            completed += 1

            if progress and progress.iscanceled():
                skipped += total - completed + 1
                for pending in futures:
                    pending.cancel()
                break

            try:
                ok = future.result()
            except Exception:
                ok = False

            if ok:
                playable.append(item)
            else:
                skipped += 1

            if progress and total:
                progress.update(int(completed / total * 100), "Pruefe Streams: " + item.get("name", "Sender"))

    return sorted(playable, key=lambda item: item.get("order", 0)), skipped


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
        return "", 0, 0

    items = []

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
                epg_id = _escape_attr(get_epg_id(stream, name))
                group = _escape_attr(clean_group_name(category_name))
                stream_url = _clean_line(stream.get("direct_source")) or xtream.live_url(stream_id, "ts")

                items.append({
                    "order": len(items),
                    "epg_id": epg_id,
                    "name": name,
                    "logo": logo,
                    "group": group,
                    "stream_url": stream_url
                })

        items, skipped = filter_playable_streams(items, progress)
    finally:
        progress.close()

    lines = ["#EXTM3U"]
    for item in items:
        lines.append(
            '#EXTINF:-1 tvg-id="{0}" tvg-name="{1}" tvg-logo="{2}" group-title="{3}",{4}'.format(
                item.get("epg_id", ""),
                _escape_attr(item.get("name", "Unbekannt")),
                item.get("logo", ""),
                item.get("group", ""),
                item.get("name", "Unbekannt")
            )
        )
        lines.append(item.get("stream_url", ""))

    return "\n".join(lines) + "\n", len(items), skipped


def write_live_tv_m3u():
    content, total, skipped = build_m3u()
    if not content or total <= 0:
        xbmcgui.Dialog().ok("Live TV", "Keine Live-TV Sender fuer die ausgewaehlten Sprachen gefunden.")
        return None, 0, 0

    path = _m3u_path()
    write_text_file(path, content)
    xbmc.log("LIVE TV M3U ERSTELLT: " + path + " | Sender=" + str(total) + " | ausgelassen=" + str(skipped), xbmc.LOGINFO)
    return path, total, skipped


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


def _delete_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception as e:
        xbmc.log("LIVE TV RESET DELETE ERROR: " + path + " | " + str(e), xbmc.LOGWARNING)

    return False


def _delete_matching_files(folder, predicate):
    deleted = []

    try:
        filenames = os.listdir(folder)
    except Exception:
        return deleted

    for filename in filenames:
        if not predicate(filename):
            continue

        path = os.path.join(folder, filename)
        if _delete_file(path):
            deleted.append(filename)

    return deleted


def clear_live_tv_data():
    xbmc.executebuiltin("StopPVRManager")

    deleted = []
    deleted.extend(_delete_matching_files(
        _kodi_database_folder(),
        lambda name: name.endswith(".db") and name.startswith(PVR_DATABASE_PREFIXES)
    ))
    deleted.extend(_delete_matching_files(
        _iptv_simple_profile_folder(),
        lambda name: name.startswith("xmltv") and ".cache" in name
    ))

    return deleted


def setup_live_tv(reset_data=False):
    deleted = []
    if reset_data:
        deleted = clear_live_tv_data()

    m3u_path, total, skipped = write_live_tv_m3u()
    if not m3u_path:
        return

    _write_iptv_simple_instance(m3u_path)
    _configure_legacy_settings(m3u_path)
    _enable_iptv_simple()
    _reload_pvr()

    xbmcgui.Dialog().ok(
        "Live TV",
        "Live TV wurde eingerichtet.\n\nSender: {0}\nAusgelassen: {1}\nPVR/EPG Daten geloescht: {2}\n\nFalls Kodi die Sender nicht sofort zeigt, Kodi einmal neu starten.".format(total, skipped, len(deleted))
    )
