# -*- coding: utf-8 -*-

import os
import sys

import xbmc
import xbmcaddon
import xbmcgui


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_PATH = ADDON.getAddonInfo("path")
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
UPDATE_CHECK_INTERVAL_SECONDS = 300
STARTUP_REPOSITORY_UPDATE_DELAY_SECONDS = 5
STARTUP_SERVICE_READY_DELAY_SECONDS = 5

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from auto_import import run_startup_import
from appearance import apply_arctic_zephyr_reloaded_after_update
from github_update import check_github_updates
from kodi_library import apply_kodi_library_update_after_addon_update
from profiles import apply_profiles_after_update
from strm import ensure_media_folders


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[IPTV Addon Service] " + str(message), level)


class XtreamStrmService(xbmc.Monitor):
    def run_startup_repository_update(self):
        try:
            log("GitHub-/Repository-Update wird geprueft")
            github_updates = check_github_updates()
            xbmc.executebuiltin("UpdateAddonRepos", True)
            xbmc.executebuiltin("UpdateLocalAddons", True)
            log("GitHub-/Repository-Updatepruefung abgeschlossen: {0}".format(len(github_updates)))
        except Exception as exc:
            log("Repository-/Addon-Updatepruefung fehlgeschlagen: " + str(exc), xbmc.LOGERROR)

    def run_update_tasks(self):
        progress = None
        needs_visible_update = False
        try:
            try:
                from profiles import kodi_profiles_are_configured
                needs_visible_update = not kodi_profiles_are_configured()
            except Exception:
                needs_visible_update = False

            if needs_visible_update:
                progress = xbmcgui.DialogProgress()
                progress.create("Xtream IPTV Ultimate", "Update wird vorbereitet...")
                progress.update(10, "Pruefe Kodi-Profile und LoginScreen...\n\nBitte Kodi nicht schliessen.")

            ensure_media_folders()
            profiles_updated = apply_profiles_after_update(progress=progress)

            if profiles_updated and progress:
                progress.update(85, "Profil-Update ist vorbereitet.\n\nKodi wird jetzt beendet und danach automatisch neu gestartet.")

            skin_updated = apply_arctic_zephyr_reloaded_after_update()
            library_updated = apply_kodi_library_update_after_addon_update()
            log("Update-Aufgaben geprueft: Profile={0}, Skin={1}, Bibliothek={2}".format(
                profiles_updated,
                skin_updated,
                library_updated,
            ))

            if profiles_updated:
                if progress:
                    progress.update(100, "Profil-Update startet jetzt...\n\nKodi wird kurz geschlossen.")
                    xbmc.sleep(1000)
                    progress.close()
                    progress = None
                xbmcgui.Dialog().ok(
                    "Xtream IPTV Ultimate",
                    "Die Kodi-Profile werden jetzt sicher eingerichtet.\n\n"
                    "Kodi wird geschlossen, die Profile werden eingetragen und Kodi startet danach automatisch neu."
                )
                xbmc.executebuiltin("Quit")
        except Exception as exc:
            log("Update-Aufgaben fehlgeschlagen: " + str(exc), xbmc.LOGERROR)
            if needs_visible_update:
                xbmcgui.Dialog().notification(
                    "Xtream IPTV Ultimate",
                    "Update-Aufgaben fehlgeschlagen",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000,
                )
        finally:
            if progress:
                progress.close()

    def run_periodic_tasks(self):
        try:
            run_startup_import()
        except Exception as exc:
            log("Startup-Import fehlgeschlagen: " + str(exc), xbmc.LOGERROR)

    def run(self):
        log("Service gestartet")
        if self.waitForAbort(STARTUP_SERVICE_READY_DELAY_SECONDS):
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
