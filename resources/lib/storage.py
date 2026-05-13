# -*- coding: utf-8 -*-

import os
import shutil
import xbmcgui
import xbmcvfs

from common import CONFIG_PATH, get_movie_strm_path, get_series_strm_path
from strm import get_movie_folder, get_series_folder


def show_movie_path():
    xbmcgui.Dialog().ok("Filmeordner", get_movie_folder())


def show_series_path():
    xbmcgui.Dialog().ok("Serienordner", get_series_folder())


def show_internal_paths():
    text = (
        "Filme:\n" + get_movie_folder() +
        "\n\nSerien:\n" + get_series_folder() +
        "\n\nConfig:\n" + xbmcvfs.translatePath(CONFIG_PATH) +
        "\n\nKodi Quellen:\n" + xbmcvfs.translatePath("special://profile/sources.xml") +
        "\n\nFilm-Pfad Einstellung:\n" + get_movie_strm_path() +
        "\n\nSerien-Pfad Einstellung:\n" + get_series_strm_path()
    )
    xbmcgui.Dialog().textviewer("Interne Speicherorte", text)


def show_free_space():
    paths = [("Filme", get_movie_folder()), ("Serien", get_series_folder())]
    lines = []

    for label, path in paths:
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            lines.append(f"{label}: {free_gb:.2f} GB frei von {total_gb:.2f} GB")
        except Exception as e:
            lines.append(label + ": " + str(e))

    xbmcgui.Dialog().ok("Freier Speicherplatz", "\n".join(lines))
