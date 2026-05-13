# -*- coding: utf-8 -*-

import sys
import os
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from router import router

if __name__ == "__main__":
    router()
