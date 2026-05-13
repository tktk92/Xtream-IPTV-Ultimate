# -*- coding: utf-8 -*-

import sys
import urllib.parse
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = "plugin.video.xtream.strm"
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and str(sys.argv[1]).lstrip("-").isdigit() else -1
BASE_URL = sys.argv[0]

DEFAULT_MOVIE_STRM_PATH = "special://profile/addon_data/" + ADDON_ID + "/strm/Filme"
DEFAULT_SERIES_STRM_PATH = "special://profile/addon_data/" + ADDON_ID + "/strm/Serien"
CONFIG_PATH = "special://profile/addon_data/" + ADDON_ID + "/config.json"

ADDON_PROFILE = "special://profile/addon_data/" + ADDON_ID

# Abwärtskompatibel für alte Imports
MOVIE_STRM_PATH = DEFAULT_MOVIE_STRM_PATH
SERIES_STRM_PATH = DEFAULT_SERIES_STRM_PATH


def get_setting(key):
    return ADDON.getSetting(key).strip()


def get_movie_strm_path():
    value = get_setting("movie_strm_path")
    return value if value else DEFAULT_MOVIE_STRM_PATH


def get_series_strm_path():
    value = get_setting("series_strm_path")
    return value if value else DEFAULT_SERIES_STRM_PATH


def build_url(params):
    return BASE_URL + "?" + urllib.parse.urlencode(params)
