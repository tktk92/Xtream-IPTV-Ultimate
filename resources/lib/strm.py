# -*- coding: utf-8 -*-

import os
import re
import xbmc
import xbmcgui
import xbmcvfs
from common import get_movie_strm_path, get_series_strm_path


def clean_filename(name):
    if not name:
        return "Unbekannt"

    clean = str(name).strip()
    clean = clean.replace("â”ƒ", " ").replace("┃", " ").replace("|", " ").replace("│", " ")
    clean = clean.replace("–", "-").replace("—", "-").replace("'", "").replace('"', "")

    language_words = (
        "DE|GER|GERMAN|DEUTSCH|"
        "AR|ARA|ARABIC|"
        "EN|ENG|ENGLISH|UK|US|"
        "FRENCH|FR|"
        "SPANISH|ES|"
        "ITALIAN|IT|"
        "TURKISH|TR|"
        "TAMIL|TAM|TA|"
        "HI|HINDI|IN|"
        "MULTI|MULTI AUDIO|MULTI-AUDIO|MULTIAUDIO|"
        "DUAL AUDIO|DUAL-AUDIO"
    )

    start_patterns = [
        r'^\s*[\[\(\{][^\]\)\}]{1,30}[\]\)\}]\s*',
        r'^\s*[^A-Za-z0-9]{0,10}(' + language_words + r')(?=$|[^A-Za-z0-9])[^A-Za-z0-9]{0,10}\s*',
        r'^\s*(' + language_words + r')\s*[-_|:]\s*',
        r'^\s*(' + language_words + r')\s+',
    ]

    end_patterns = [
        r'\s+(' + language_words + r')\s*$',
        r'\s*[-_|:]\s*(' + language_words + r')\s*$',
    ]

    changed = True
    while changed:
        old = clean
        for pattern in start_patterns:
            clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
        for pattern in end_patterns:
            clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
        changed = old != clean

    remove_patterns = [
        r'\bMULTI\b', r'\bMULTI AUDIO\b', r'\bMULTI-AUDIO\b', r'\bMULTIAUDIO\b',
        r'\bDUAL AUDIO\b', r'\bDUAL-AUDIO\b', r'\b1080P\b', r'\b720P\b', r'\b2160P\b',
        r'\b4K\b', r'\bUHD\b', r'\bWEB-DL\b', r'\bWEBRIP\b', r'\bBLURAY\b',
        r'\bHDRIP\b', r'\bX264\b', r'\bH264\b', r'\bHEVC\b', r'\bAAC\b', r'\bHDR\b'
    ]

    for pattern in remove_patterns:
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)

    clean = re.sub(r'\s+', ' ', clean).strip(" -_|.")

    for char in '<>:"/\\|?*':
        clean = clean.replace(char, "_")

    return clean.strip() or "Unbekannt"


def ensure_folder(folder):
    folder = xbmcvfs.translatePath(folder)
    if xbmcvfs.exists(folder) or os.path.isdir(folder):
        return folder

    try:
        xbmcvfs.mkdirs(folder)
    except Exception as e:
        xbmc.log("STRM FOLDER XBM_ERROR: " + folder + " | " + str(e), xbmc.LOGWARNING)

    if not xbmcvfs.exists(folder) and not os.path.isdir(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            xbmc.log("STRM FOLDER OS_ERROR: " + folder + " | " + str(e), xbmc.LOGWARNING)

    if not xbmcvfs.exists(folder) and not os.path.isdir(folder):
        raise Exception("Ordner konnte nicht erstellt werden: " + folder)

    return folder


def write_text_file(path, text):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as e:
        xbmc.log("STRM WRITE OS_ERROR: " + path + " | " + str(e), xbmc.LOGWARNING)

    file_handle = None
    try:
        file_handle = xbmcvfs.File(path, "w")
        file_handle.write(text)
        return True
    finally:
        if file_handle:
            file_handle.close()


def get_movie_folder():
    return ensure_folder(xbmcvfs.translatePath(get_movie_strm_path()))


def get_series_folder():
    return ensure_folder(xbmcvfs.translatePath(get_series_strm_path()))


def ensure_media_folders():
    movie_folder = get_movie_folder()
    series_folder = get_series_folder()
    xbmc.log("STRM MEDIA FOLDERS OK: Filme=" + movie_folder + " | Serien=" + series_folder, xbmc.LOGINFO)
    return movie_folder, series_folder


def write_strm_file(file_path, stream_url, show_dialog=True):
    try:
        folder = os.path.dirname(file_path)
        ensure_folder(folder)
        write_text_file(file_path, stream_url)
        xbmc.log("STRM ERSTELLT: " + file_path, xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log("STRM ERROR: " + file_path + " | " + str(e), xbmc.LOGERROR)
        if show_dialog:
            xbmcgui.Dialog().ok("STRM Fehler", file_path + "\n\n" + str(e))
        return False


def write_movie(filename, stream_url, subfolder=None, show_dialog=True):
    base_folder = get_movie_folder()
    folder = os.path.join(base_folder, clean_filename(subfolder)) if subfolder else base_folder
    safe_name = clean_filename(filename)
    file_path = os.path.join(folder, safe_name + ".strm")
    return write_strm_file(file_path, stream_url, show_dialog)


def write_episode(series_name, season_number, episode_number, episode_title, stream_url, show_dialog=True):
    base_folder = get_series_folder()
    safe_series = clean_filename(series_name)
    season_folder = "Staffel " + str(season_number).zfill(2)
    folder = os.path.join(base_folder, safe_series, season_folder)

    ep = str(episode_number).zfill(2)
    season = str(season_number).zfill(2)
    title = clean_filename(episode_title) if episode_title else "Episode " + ep
    filename = f"{safe_series} S{season}E{ep} - {title}.strm"
    file_path = os.path.join(folder, filename)
    return write_strm_file(file_path, stream_url, show_dialog)
