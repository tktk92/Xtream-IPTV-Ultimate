# -*- coding: utf-8 -*-

import os
import re
import shutil
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import tempfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


CURRENT_ADDON_ID = "plugin.video.xtream.strm"

GITHUB_ADDONS_XML_URLS = (
    "https://raw.githubusercontent.com/tktk92/Xtream-IPTV-Ultimate/main/repo/addons.xml",
    "https://tktk92.github.io/Xtream-IPTV-Ultimate/repo/addons.xml",
)

REPO_ZIP_BASE_URLS = (
    "https://tktk92.github.io/Xtream-IPTV-Ultimate/repo/zips",
    "https://raw.githubusercontent.com/tktk92/Xtream-IPTV-Ultimate/main/repo/zips",
)

MANAGED_ADDONS = (
    "repository.xtream.iptv.ultimate",
    "plugin.video.xtream.strm",
    "skin.xtream.ultimate",
)

IDLE_STABLE_SECONDS = 10
IDLE_MAX_WAIT_SECONDS = 180
IDLE_POLL_SECONDS = 2

BUSY_CONDITIONS = (
    ("Video-Bibliothek wird aktualisiert", "Library.IsScanningVideo"),
    ("Musik-Bibliothek wird aktualisiert", "Library.IsScanningMusic"),
    ("Player ist aktiv", "Player.HasMedia"),
    ("Kodi zeigt einen Fortschrittsdialog", "Window.IsVisible(progressdialog)"),
    ("Kodi zeigt einen Fortschrittsdialog", "Window.IsVisible(extendedprogressdialog)"),
    ("Kodi ist beschaeftigt", "Window.IsVisible(busydialog)"),
    ("Kodi ist beschaeftigt", "Window.IsVisible(busydialognocancel)"),
    ("Kodi zeigt einen Dialog", "System.HasModalDialog"),
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


def _download_file(url, target_path, timeout=60):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Xtream-IPTV-Ultimate-Kodi-Updater",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with open(target_path, "wb") as handle:
            shutil.copyfileobj(response, handle)


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
    xbmc.executebuiltin("InstallAddon({0})".format(addon_id))
    xbmc.sleep(500)
    xbmc.executebuiltin("UpdateLocalAddons")


def _translate_path(path):
    try:
        return xbmcvfs.translatePath(path)
    except Exception:
        return xbmc.translatePath(path)


def _addon_zip_urls(addon_id, version):
    file_name = "{0}-{1}.zip".format(addon_id, version)
    return ["{0}/{1}/{2}".format(base.rstrip("/"), addon_id, file_name) for base in REPO_ZIP_BASE_URLS]


def _copy_tree(source_dir, target_dir):
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    source_entries = set(os.listdir(source_dir))

    for name in source_entries:
        source_path = os.path.join(source_dir, name)
        target_path = os.path.join(target_dir, name)

        if os.path.isdir(source_path):
            _copy_tree(source_path, target_path)
        else:
            parent = os.path.dirname(target_path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            shutil.copy2(source_path, target_path)

    for name in os.listdir(target_dir):
        if name in source_entries:
            continue

        stale_path = os.path.join(target_dir, name)
        try:
            if os.path.isdir(stale_path):
                shutil.rmtree(stale_path)
            else:
                os.remove(stale_path)
        except Exception as exc:
            log("Veraltete Skin-Datei konnte nicht entfernt werden: {0} | {1}".format(stale_path, exc), xbmc.LOGWARNING)


def _manual_install_addon_zip(addon_id, version):
    temp_dir = tempfile.mkdtemp(prefix="xtream_update_")
    try:
        zip_path = os.path.join(temp_dir, "{0}-{1}.zip".format(addon_id, version))
        last_error = None
        downloaded_url = None

        for url in _addon_zip_urls(addon_id, version):
            try:
                _download_file(url, zip_path)
                downloaded_url = url
                break
            except Exception as exc:
                last_error = exc
                log("Addon-Zip konnte nicht geladen werden: {0} | {1}".format(url, exc), xbmc.LOGWARNING)

        if not downloaded_url:
            raise Exception(last_error or "Addon-Zip nicht erreichbar")

        extract_dir = os.path.join(temp_dir, "extract")
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        source_dir = os.path.join(extract_dir, addon_id)
        if not os.path.isdir(source_dir):
            raise Exception("Addon-Zip enthaelt keinen Ordner " + addon_id)

        addons_dir = _translate_path("special://home/addons")
        target_dir = os.path.join(addons_dir, addon_id)
        _copy_tree(source_dir, target_dir)

        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(1000)

        log("Addon-Zip manuell installiert: {0} {1} von {2}".format(addon_id, version, downloaded_url))
        return target_dir
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def _offer_restart_for_skin_update(local_version, remote_version):
    message = (
        "Ultimate IPTV Skin wurde aktualisiert:\n\n"
        "{0} -> {1}\n\n"
        "Kodi muss neu gestartet werden, damit der neue Skin vollstaendig geladen wird."
    ).format(local_version, remote_version)
    restart = xbmcgui.Dialog().yesno(
        "Skin-Update abgeschlossen",
        message,
        nolabel="Spaeter",
        yeslabel="Jetzt neu starten",
    )
    if restart:
        log("Benutzer bestaetigt Neustart nach Skin-Update.")
        xbmc.executebuiltin("RestartApp")
    else:
        xbmcgui.Dialog().notification(
            "Skin-Update",
            "Neustart erforderlich",
            xbmcgui.NOTIFICATION_INFO,
            6000,
        )


def _busy_reasons():
    reasons = []
    for reason, condition in BUSY_CONDITIONS:
        try:
            if xbmc.getCondVisibility(condition) and reason not in reasons:
                reasons.append(reason)
        except Exception:
            continue
    return reasons


def _wait_for_kodi_idle(monitor=None, max_wait=IDLE_MAX_WAIT_SECONDS, stable_seconds=IDLE_STABLE_SECONDS):
    deadline = time.time() + int(max_wait)
    idle_since = None
    last_log = 0

    while time.time() < deadline:
        if monitor and monitor.abortRequested():
            log("Update abgebrochen, Kodi-Service beendet sich.", xbmc.LOGWARNING)
            return False

        reasons = _busy_reasons()
        if not reasons:
            if idle_since is None:
                idle_since = time.time()
                log("Kodi ist idle, warte kurze Stabilitaetsphase vor dem Update.")
            elif time.time() - idle_since >= int(stable_seconds):
                return True
        else:
            idle_since = None
            if time.time() - last_log >= 15:
                log("Update wartet, Kodi ist beschaeftigt: " + ", ".join(reasons), xbmc.LOGINFO)
                last_log = time.time()

        if monitor:
            if monitor.waitForAbort(IDLE_POLL_SECONDS):
                log("Update abgebrochen, Kodi-Service beendet sich.", xbmc.LOGWARNING)
                return False
        else:
            xbmc.sleep(IDLE_POLL_SECONDS * 1000)

    log("Update uebersprungen, Kodi wurde nicht rechtzeitig idle.", xbmc.LOGWARNING)
    return False


def check_github_updates(monitor=None):
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

    if not _wait_for_kodi_idle(monitor=monitor):
        return []

    xbmc.executebuiltin("UpdateAddonRepos")
    xbmc.executebuiltin("UpdateLocalAddons")

    installed = []
    pending = []
    has_current_addon_update = any(addon_id == CURRENT_ADDON_ID for addon_id, _local, _remote in updates)

    if has_current_addon_update:
        for addon_id, local_version, remote_version in updates:
            if addon_id == CURRENT_ADDON_ID:
                pending.append((addon_id, local_version, remote_version))
                log(
                    "Laufendes Addon wird nur vorgemerkt: {0} {1}->{2}".format(
                        addon_id,
                        local_version,
                        remote_version,
                    ),
                    xbmc.LOGWARNING,
                )

        log(
            "Update des laufenden Addons erkannt. Keine synchronen Zusatzinstallationen in diesem Service-Lauf.",
            xbmc.LOGWARNING,
        )
        return installed

    for addon_id, local_version, remote_version in updates:
        try:
            if addon_id == "skin.xtream.ultimate":
                _manual_install_addon_zip(addon_id, remote_version)
            else:
                _install_addon(addon_id)

            new_version = _installed_version(addon_id)
            if new_version == remote_version or _is_newer(new_version, local_version):
                installed.append((addon_id, local_version, new_version))
                log("Addon aktualisiert: {0} {1}->{2}".format(addon_id, local_version, new_version))
                if addon_id == "skin.xtream.ultimate":
                    log(
                        "Skin-Update manuell installiert: {0}->{1}, Neustart erforderlich".format(
                            local_version,
                            new_version,
                        )
                    )
                    _offer_restart_for_skin_update(local_version, new_version)
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

    return installed
