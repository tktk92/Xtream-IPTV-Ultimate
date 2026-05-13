# -*- coding: utf-8 -*-

import os
import json
import xbmcvfs
from common import CONFIG_PATH

ALL_LANGUAGES = [
    "Deutsch",
    "Englisch",
    "Tamil",
    "Mehrsprachig",
    "Arabisch",
    "Türkisch",
    "Hindi",
    "Französisch",
    "Spanisch",
    "Italienisch",
    "Russisch",
    "Albanisch",
    "Ex-Yu",
    "Andere"
]


def get_config_file():
    path = xbmcvfs.translatePath(CONFIG_PATH)
    folder = os.path.dirname(path)

    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)

    return path


def load_config():
    path = get_config_file()

    if not os.path.exists(path):
        return {"selected_languages": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"selected_languages": []}


def save_config(config):
    path = get_config_file()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def get_selected_languages():
    config = load_config()
    return config.get("selected_languages", [])


def set_selected_languages(languages):
    config = load_config()
    config["selected_languages"] = languages
    save_config(config)
