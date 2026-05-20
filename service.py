# -*- coding: utf-8 -*-

import os
import sys

import xbmc
import xbmcaddon


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_PATH = ADDON.getAddonInfo("path")
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
UPDATE_CHECK_INTERVAL_SECONDS = 300
STARTUP_REPOSITORY_UPDATE_DELAY_SECONDS = 5

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from auto_import import run_startup_import
from appearance import apply_arctic_zephyr_reloaded_after_update
from kodi_library import apply_kodi_library_update_after_addon_update
from strm import ensure_media_folders


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[IPTV Addon Service] " + str(message), level)


class XtreamStrmService(xbmc.Monitor):
    def run_startup_repository_update(self):
        try:
            log("Repository-Update wird geprueft")
            xbmc.executebuiltin("UpdateAddonRepos", True)
            xbmc.executebuiltin("UpdateLocalAddons", True)
            xbmc.executebuiltin("InstallAddon({0})".format(ADDON_ID), True)
            log("Repository-Update und Addon-Updatepruefung abgeschlossen")
        except Exception as exc:
            log("Repository-/Addon-Updatepruefung fehlgeschlagen: " + str(exc), xbmc.LOGERROR)

    def run_update_tasks(self):
        try:
            ensure_media_folders()
            skin_updated = apply_arctic_zephyr_reloaded_after_update()
            library_updated = apply_kodi_library_update_after_addon_update()
            log("Update-Aufgaben geprueft: Skin={0}, Bibliothek={1}".format(skin_updated, library_updated))
        except Exception as exc:
            log("Update-Aufgaben fehlgeschlagen: " + str(exc), xbmc.LOGERROR)

    def run_periodic_tasks(self):
        try:
            run_startup_import()
        except Exception as exc:
            log("Startup-Import fehlgeschlagen: " + str(exc), xbmc.LOGERROR)

    def run(self):
        log("Service gestartet")
        if self.waitForAbort(20):
            return

        if not self.waitForAbort(STARTUP_REPOSITORY_UPDATE_DELAY_SECONDS):
            self.run_startup_repository_update()

        self.run_update_tasks()
        self.run_periodic_tasks()

        while not self.abortRequested():
            if self.waitForAbort(UPDATE_CHECK_INTERVAL_SECONDS):
                break
            self.run_update_tasks()

        log("Service beendet")


if __name__ == "__main__":
    XtreamStrmService().run()
