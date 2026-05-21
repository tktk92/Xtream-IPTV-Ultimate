# -*- coding: utf-8 -*-

import re
import urllib.request
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon


CURRENT_ADDON_ID = "plugin.video.xtream.strm"

GITHUB_ADDONS_XML_URLS = (
    "https://raw.githubusercontent.com/tktk92/Xtream-IPTV-Ultimate/main/repo/addons.xml",
    "https://tktk92.github.io/Xtream-IPTV-Ultimate/repo/addons.xml",
)

MANAGED_ADDONS = (
    "repository.xtream.iptv.ultimate",
    "plugin.video.xtream.strm",
    "skin.xtream.ultimate",
)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[IPTV GitHub Update] " + str(message), level)


def _fetch_text(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Xtream-IPTV-Ultimate-Kodi-Updater",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def _fetch_github_addons_xml():
    last_error = None
    for url in GITHUB_ADDONS_XML_URLS:
        try:
            text = _fetch_text(url)
            log("GitHub addons.xml geladen: " + url)
            return text
        except Exception as exc:
            last_error = exc
            log("GitHub addons.xml konnte nicht geladen werden: {0} | {1}".format(url, exc), xbmc.LOGWARNING)

    raise Exception(last_error or "addons.xml nicht erreichbar")


def _parse_versions(addons_xml_text):
    root = ET.fromstring(addons_xml_text)
    versions = {}
    for addon_node in root.findall("addon"):
        addon_id = addon_node.get("id")
        version = addon_node.get("version")
        if addon_id and version:
            versions[addon_id] = version
    return versions


def _version_parts(version):
    parts = []
    for part in re.split(r"[^0-9A-Za-z]+", str(version)):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.lower()))
    return parts


def _is_newer(remote_version, local_version):
    return _version_parts(remote_version) > _version_parts(local_version)


def _installed_version(addon_id):
    try:
        return xbmcaddon.Addon(addon_id).getAddonInfo("version") or ""
    except Exception:
        return ""


def _install_addon(addon_id):
    xbmc.executebuiltin("InstallAddon({0})".format(addon_id), True)
    xbmc.sleep(500)
    xbmc.executebuiltin("UpdateLocalAddons", True)


def check_github_updates():
    try:
        remote_versions = _parse_versions(_fetch_github_addons_xml())
    except Exception as exc:
        log("Direkte GitHub-Updatepruefung fehlgeschlagen: " + str(exc), xbmc.LOGERROR)
        return []

    updates = []
    for addon_id in MANAGED_ADDONS:
        remote_version = remote_versions.get(addon_id)
        if not remote_version:
            continue

        local_version = _installed_version(addon_id)
        if not local_version or _is_newer(remote_version, local_version):
            updates.append((addon_id, local_version or "nicht installiert", remote_version))

    if not updates:
        log("Keine GitHub-Updates gefunden")
        return []

    log("GitHub-Updates gefunden: " + ", ".join("{0} {1}->{2}".format(*item) for item in updates))

    xbmc.executebuiltin("UpdateAddonRepos", True)
    xbmc.executebuiltin("UpdateLocalAddons", True)

    installed = []
    pending = []
    for addon_id, local_version, remote_version in updates:
        if addon_id == CURRENT_ADDON_ID:
            pending.append((addon_id, local_version, remote_version))
            log(
                "Laufendes Addon wird nicht synchron aus dem eigenen Service installiert: {0} {1}->{2}".format(
                    addon_id,
                    local_version,
                    remote_version,
                ),
                xbmc.LOGWARNING,
            )
            continue

        try:
            _install_addon(addon_id)
            new_version = _installed_version(addon_id)
            if new_version == remote_version or _is_newer(new_version, local_version):
                installed.append((addon_id, local_version, new_version))
                log("Addon aktualisiert: {0} {1}->{2}".format(addon_id, local_version, new_version))
            else:
                log(
                    "Addon-Update nicht uebernommen: {0} lokal={1}, erwartet={2}".format(
                        addon_id,
                        new_version or "unbekannt",
                        remote_version,
                    ),
                    xbmc.LOGWARNING,
                )
        except Exception as exc:
            log("Addon-Update fehlgeschlagen: {0} | {1}".format(addon_id, exc), xbmc.LOGERROR)

    if pending:
        xbmc.executebuiltin("UpdateAddonRepos")
        xbmc.executebuiltin("UpdateLocalAddons")
        log("Plugin-Update vorgemerkt. Kodi sollte das Update ueber das Repository nachladen oder nach Neustart anbieten.", xbmc.LOGWARNING)

    return installed
