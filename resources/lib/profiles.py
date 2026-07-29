# -*- coding: utf-8 -*-

import json
import os
import re
import shutil
import subprocess
import sys
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
PROFILE_BOOTSTRAP_FILE = "profile_bootstrap.ps1"
MOVIE_PROFILE_GENRES = (
    "Action",
    "Abenteuer",
    "Animation",
    "Biografie",
    "Comedy",
    "Crime",
    "Drama",
    "Familie",
    "Fantasy",
    "History",
    "Horror",
    "Krieg",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Sport",
    "Thriller",
    "Western",
    "Deutsch",
    "Tamil",
    "Hindi",
    "Tuerkisch",
    "Koreanisch",
    "Japanisch",
    "Spanisch",
    "Franzoesisch",
)
SERIES_PROFILE_GENRES = (
    "Action",
    "Animation",
    "Comedy",
    "Crime",
    "Drama",
    "Doku",
    "Familie",
    "Fantasy",
    "Kids",
    "Mystery",
    "Reality",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "Deutsch",
    "Tamil",
    "Hindi",
    "Tuerkisch",
    "Koreanisch",
    "Japanisch",
    "Spanisch",
    "Franzoesisch",
)


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


def _profile_bootstrap_path():
    return _translate("%s/%s" % (ADDON_PROFILE, PROFILE_BOOTSTRAP_FILE))


def _current_profile_name():
    try:
        value = xbmc.getInfoLabel("System.ProfileName")
        if value:
            return value.strip()
    except Exception:
        pass
    return "Erwachsene"


def _select_categories(title, categories, selected_categories=None):
    if not categories:
        return []

    selected_categories = set(selected_categories or [])
    preselect = [index for index, name in enumerate(categories) if name in selected_categories]
    try:
        result = xbmcgui.Dialog().multiselect(title, categories, preselect=preselect)
    except TypeError:
        result = xbmcgui.Dialog().multiselect(title, categories)

    if result is None:
        return None
    return [categories[index] for index in result if 0 <= index < len(categories)]


def _get_profile_preference_categories():
    return list(MOVIE_PROFILE_GENRES), list(SERIES_PROFILE_GENRES)


def configure_current_profile_preferences(force=False):
    version = _current_addon_version()
    state = _load_profile_setup_state()
    if not force and (
        state.get("preferences_completed_at")
        or state.get("preferences_postponed_at")
        or state.get("preferences_addon_version") == version
    ):
        return False

    config_path = _master_profile_path("addon_data", ADDON_ID, "config.json")
    if not os.path.exists(config_path):
        config_path = _translate("special://profile/addon_data/%s/config.json" % ADDON_ID)

    config = _read_json(config_path)
    current_name = config.get("profile_display_name") or _current_profile_name()

    if not xbmcgui.Dialog().yesno(
        "Profil einrichten",
        "Moechtest du dieses Kodi-Profil jetzt personalisieren?\n\n"
        "Es werden Name sowie bevorzugte Film- und Seriengenres gespeichert.",
        nolabel="Spaeter",
        yeslabel="Einrichten",
    ):
        state["preferences_addon_version"] = version
        state["preferences_postponed_at"] = int(time.time())
        _save_profile_setup_state(state)
        return False

    profile_name = xbmcgui.Dialog().input("Profilname", defaultt=current_name, type=xbmcgui.INPUT_ALPHANUM)
    if not profile_name:
        profile_name = current_name

    movie_categories, series_categories = _get_profile_preference_categories()
    selected_movies = _select_categories(
        "Bevorzugte Filmgenres",
        movie_categories,
        config.get("preferred_movie_genres") or config.get("preferred_movie_categories", []),
    )
    if selected_movies is None:
        selected_movies = config.get("preferred_movie_genres") or config.get("preferred_movie_categories", [])

    selected_series = _select_categories(
        "Bevorzugte Seriengenres",
        series_categories,
        config.get("preferred_series_genres") or config.get("preferred_series_categories", []),
    )
    if selected_series is None:
        selected_series = config.get("preferred_series_genres") or config.get("preferred_series_categories", [])

    config["profile_display_name"] = profile_name.strip() or current_name
    config["preferred_movie_genres"] = selected_movies
    config["preferred_series_genres"] = selected_series
    config.pop("preferred_movie_categories", None)
    config.pop("preferred_series_categories", None)
    config["profile_preferences_updated_at"] = int(time.time())
    _write_json(config_path, config)

    state["preferences_addon_version"] = version
    state["preferences_completed_at"] = int(time.time())
    _save_profile_setup_state(state)
    xbmcgui.Dialog().notification(
        "Profil gespeichert",
        config["profile_display_name"],
        xbmcgui.NOTIFICATION_INFO,
        4000,
    )
    xbmc.log("[IPTV Addon] Profil-Einstellungen gespeichert: " + config["profile_display_name"], xbmc.LOGINFO)
    return True


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


def _prepare_profile_folders():
    for profile_def in PROFILE_DEFINITIONS:
        _prepare_profile_folder(profile_def)


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


def _profiles_xml_is_configured():
    profiles_path = _master_profile_path("profiles.xml")
    if not os.path.exists(profiles_path):
        return False

    try:
        root = ET.parse(profiles_path).getroot()
    except Exception:
        return False

    if (root.findtext("useloginscreen") or "").strip().lower() != "true":
        return False

    names = _profile_names(root)
    for profile_def in PROFILE_DEFINITIONS:
        if profile_def["name"].strip().lower() not in names:
            return False

    return True


def kodi_profiles_are_configured():
    if not _profiles_xml_is_configured():
        return False

    for profile_def in PROFILE_DEFINITIONS:
        if not os.path.exists(_profile_path(profile_def, "addon_data", ADDON_ID, "config.json")):
            return False

    return True


def _powershell_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def _build_profile_bootstrap_script(profiles_path, kodi_executable):
    profile_entries = []
    for profile_def in PROFILE_DEFINITIONS:
        profile_entries.append(
            "@{Name=%s; Directory=%s; ContentProfile=%s}"
            % (
                _powershell_string(profile_def["name"]),
                _powershell_string(profile_def["directory"]),
                _powershell_string(profile_def["content_profile"]),
            )
        )

    restart_block = ""
    if kodi_executable and os.path.exists(kodi_executable):
        restart_block = """
Start-Sleep -Seconds 1
Start-Process -FilePath {0}
""".format(_powershell_string(kodi_executable))

    return r"""$ErrorActionPreference = 'Stop'
$profilesPath = {profiles_path}
$profiles = @(
    {profile_entries}
)

while (Get-Process -Name kodi -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 500
}}

if (-not (Test-Path -LiteralPath $profilesPath)) {{
    exit 2
}}

$backupPath = $profilesPath + '.ultimate-bootstrap-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item -LiteralPath $profilesPath -Destination $backupPath -Force

[xml]$xml = Get-Content -LiteralPath $profilesPath -Raw
$root = $xml.profiles

function Ensure-TextNode($parent, $name, $value) {{
    $node = $parent.SelectSingleNode($name)
    if ($null -eq $node) {{
        $node = $xml.CreateElement($name)
        [void]$parent.AppendChild($node)
    }}
    $node.InnerText = $value
}}

function Ensure-Profile($root, $profile, [int]$id) {{
    foreach ($existing in @($root.profile)) {{
        if ($existing.name -and $existing.name.Trim().ToLowerInvariant() -eq $profile.Name.Trim().ToLowerInvariant()) {{
            return $false
        }}
    }}

    $node = $xml.CreateElement('profile')
    $fields = @(
        @('id', [string]$id),
        @('name', $profile.Name),
        @('directory', $profile.Directory),
        @('thumbnail', ''),
        @('hasdatabases', 'true'),
        @('canwritedatabases', 'true'),
        @('hassources', 'true'),
        @('canwritesources', 'true'),
        @('lockaddonmanager', 'false'),
        @('locksettings', '0'),
        @('lockfiles', 'false'),
        @('lockmusic', 'false'),
        @('lockvideo', 'false'),
        @('lockpictures', 'false'),
        @('lockprograms', 'false'),
        @('lockgames', 'false'),
        @('lockmode', '0'),
        @('lockcode', ''),
        @('lastdate', '')
    )

    foreach ($field in $fields) {{
        $child = $xml.CreateElement($field[0])
        if ($field[0] -eq 'directory' -or $field[0] -eq 'thumbnail') {{
            $attr = $xml.CreateAttribute('pathversion')
            $attr.Value = '1'
            [void]$child.Attributes.Append($attr)
        }}
        $child.InnerText = $field[1]
        [void]$node.AppendChild($child)
    }}

    [void]$root.AppendChild($node)
    return $true
}}

$maxId = -1
foreach ($existing in @($root.profile)) {{
    $parsed = 0
    if ([int]::TryParse([string]$existing.id, [ref]$parsed)) {{
        if ($parsed -gt $maxId) {{
            $maxId = $parsed
        }}
    }}
}}

$nextId = $maxId + 1
foreach ($profile in $profiles) {{
    if (Ensure-Profile $root $profile $nextId) {{
        $nextId++
    }}
}}

Ensure-TextNode $root 'useloginscreen' 'true'
Ensure-TextNode $root 'autologin' '-1'
Ensure-TextNode $root 'nextIdProfile' ([string]$nextId)

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [System.Xml.XmlWriter]::Create($profilesPath, $settings)
$xml.Save($writer)
$writer.Close()
{restart_block}
""".format(
        profiles_path=_powershell_string(profiles_path),
        profile_entries=",\n    ".join(profile_entries),
        restart_block=restart_block,
    )


def _start_windows_profile_bootstrap(show_dialog=True):
    if os.name != "nt":
        if show_dialog:
            xbmcgui.Dialog().ok(
                "Profile",
                "Automatische Profileinrichtung ist aktuell nur fuer Windows vorbereitet.\n\n"
                "Oeffne bitte Kodi Profileinstellungen und aktiviere den LoginScreen manuell.",
            )
        return False

    profiles_path = _master_profile_path("profiles.xml")
    bootstrap_path = _profile_bootstrap_path()
    kodi_executable = sys.executable if sys.executable else ""

    _ensure_dir(os.path.dirname(bootstrap_path))
    with open(bootstrap_path, "w", encoding="utf-8") as handle:
        handle.write(_build_profile_bootstrap_script(profiles_path, kodi_executable))

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        bootstrap_path,
    ]
    subprocess.Popen(command, close_fds=True)
    xbmc.log("[IPTV Addon] Kodi Profil-Bootstrap vorbereitet: " + bootstrap_path, xbmc.LOGINFO)
    return True


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


def apply_profiles_after_update(progress=None):
    version = _current_addon_version()
    state = _load_profile_setup_state()

    if kodi_profiles_are_configured():
        if not state.get("completed") or state.get("addon_version") != version:
            state.update({
                "addon_version": version,
                "completed": True,
                "verified_at": int(time.time()),
            })
            _save_profile_setup_state(state)
        return False

    if (
        state.get("addon_version") == version
        and state.get("bootstrap_started")
        and int(time.time()) - int(state.get("bootstrap_started_at", 0) or 0) < 60
    ):
        return False

    try:
        if progress:
            progress.update(25, "Kodi-Profile werden vorbereitet...\n\nProfile: Erwachsene, Kinder, Gast")
        _prepare_profile_folders()

        if progress:
            progress.update(45, "LoginScreen wird fuer den naechsten Kodi-Start vorbereitet...\n\nKodi wird danach einmal neu gestartet.")

        if _start_windows_profile_bootstrap(show_dialog=False):
            state.update({
                "addon_version": version,
                "completed": False,
                "bootstrap_started": True,
                "bootstrap_started_at": int(time.time()),
            })
            _save_profile_setup_state(state)
            xbmc.log("[IPTV Addon] Kodi Profil-Bootstrap automatisch gestartet: " + version, xbmc.LOGINFO)
            return True
    except Exception as exc:
        xbmc.log("[IPTV Addon] Kodi Profil-Autoeinrichtung fehlgeschlagen: %s" % exc, xbmc.LOGERROR)

    return False
