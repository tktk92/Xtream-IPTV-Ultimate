# -*- coding: utf-8 -*-

import os
import sys

import xbmc
import xbmcaddon


ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from auto_import import run_startup_import


class XtreamStrmService(xbmc.Monitor):
    def run(self):
        if self.waitForAbort(60):
            return
        run_startup_import()


if __name__ == "__main__":
    XtreamStrmService().run()
