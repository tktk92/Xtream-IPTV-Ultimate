# -*- coding: utf-8 -*-

import re

LANGUAGE_NAMES = {
    "DE": "Deutsch",
    "GER": "Deutsch",
    "DEU": "Deutsch",
    "AR": "Arabisch",
    "ARA": "Arabisch",
    "EN": "Englisch",
    "ENG": "Englisch",
    "UK": "Englisch",
    "US": "Englisch",
    "FR": "Französisch",
    "ES": "Spanisch",
    "IT": "Italienisch",
    "TR": "Türkisch",
    "IN": "Indisch",
    "HI": "Hindi",
    "TA": "Tamil",
    "TAM": "Tamil",
    "RU": "Russisch",
    "AL": "Albanisch",
    "EXYU": "Ex-Yu",
    "YU": "Ex-Yu",
    "MULTI": "Mehrsprachig"
}


def extract_language_from_category(category_name):
    if not category_name:
        return "Andere"

    name = category_name.upper()

    for keyword in ["TAMIL", "TAM", "KOLLYWOOD"]:
        if keyword in name:
            return "Tamil"

    for keyword in ["MULTI", "MULTI AUDIO", "MULTI-AUDIO", "MULTIAUDIO", "DUAL AUDIO", "DUAL-AUDIO"]:
        if keyword in name:
            return "Mehrsprachig"

    match = re.search(r'[^A-Z0-9]*([A-Z]{2,5})[^A-Z0-9]+', name)

    if match:
        code = match.group(1)
        if code in LANGUAGE_NAMES:
            return LANGUAGE_NAMES[code]

    if "ARABIC" in name or "ARAB" in name:
        return "Arabisch"
    if "GERMAN" in name or "DEUTSCH" in name:
        return "Deutsch"
    if "ENGLISH" in name:
        return "Englisch"
    if "TURKISH" in name or "TURK" in name:
        return "Türkisch"
    if "HINDI" in name or "BOLLYWOOD" in name:
        return "Hindi"
    if "FRENCH" in name:
        return "Französisch"
    if "SPANISH" in name:
        return "Spanisch"
    if "ITALIAN" in name:
        return "Italienisch"

    for code, lang_name in LANGUAGE_NAMES.items():
        if (
            name.startswith(code + " ")
            or name.startswith(code + "-")
            or name.startswith(code + "|")
            or name.startswith(code + "_")
        ):
            return lang_name

    return "Andere"
