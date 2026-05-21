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


def get_content_profile():
    config = load_config()
    return config.get("content_profile", "adult")


def is_kids_profile():
    return get_content_profile() == "kids"


def is_adult_item(item):
    if not isinstance(item, dict):
        return False

    value = item.get("is_adult")
    if str(value).strip().lower() in ("1", "true", "yes"):
        return True

    category = (item.get("category_name") or item.get("category_name_export") or "").lower()
    adult_markers = ("adult", "xxx", "18+", "18 plus", "erotik", "porn")
    return any(marker in category for marker in adult_markers)


def is_content_allowed(item):
    return not (is_kids_profile() and is_adult_item(item))
