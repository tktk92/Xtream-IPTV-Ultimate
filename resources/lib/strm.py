# -*- coding: utf-8 -*-

import os
import re
from xml.sax.saxutils import escape

import xbmc
import xbmcgui
import xbmcvfs
from common import get_movie_strm_path, get_series_strm_path

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"


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


def text_file_matches(path, text):
    try:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            return f.read() == text
    except Exception:
        return False


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


def movie_year_from_title(title):
    match = re.search(r"\((19|20)\d{2}\)", str(title or ""))
    if not match:
        return ""
    return match.group(0).strip("()")


def build_movie_nfo(title, metadata=None):
    metadata = metadata or {}
    clean_title = str(metadata.get("tmdb_title") or metadata.get("title") or title or "Film").strip()
    original_title = str(metadata.get("tmdb_original_title") or metadata.get("original_title") or "").strip()
    year = str(metadata.get("release_year") or movie_year_from_title(title) or "").strip()
    release_date = str(metadata.get("release_date") or metadata.get("premiered") or "").strip()
    tmdb_id = str(metadata.get("tmdb_id") or "").strip()
    plot = str(metadata.get("plot") or metadata.get("overview") or "").strip()
    runtime = str(metadata.get("runtime") or "").strip()
    rating = str(metadata.get("rating") or metadata.get("vote_average") or "").strip()
    poster_path = str(metadata.get("poster_path") or "").strip()
    backdrop_path = str(metadata.get("backdrop_path") or "").strip()
    poster_url = str(metadata.get("poster") or metadata.get("thumb") or "").strip()
    fanart_url = str(metadata.get("fanart") or "").strip()

    if poster_path and poster_path.startswith("/"):
        poster_url = TMDB_IMAGE_BASE + poster_path
    if backdrop_path and backdrop_path.startswith("/"):
        fanart_url = TMDB_IMAGE_BASE + backdrop_path

    lines = ["<movie>"]
    lines.append("  <title>{0}</title>".format(escape(clean_title)))
    if original_title:
        lines.append("  <originaltitle>{0}</originaltitle>".format(escape(original_title)))
    if plot:
        lines.append("  <plot>{0}</plot>".format(escape(plot)))
        lines.append("  <outline>{0}</outline>".format(escape(plot)))
    if year:
        lines.append("  <year>{0}</year>".format(escape(year)))
    if release_date:
        lines.append("  <premiered>{0}</premiered>".format(escape(release_date)))
        lines.append("  <releasedate>{0}</releasedate>".format(escape(release_date)))
    if runtime and runtime.isdigit():
        lines.append("  <runtime>{0}</runtime>".format(escape(runtime)))
    if rating:
        lines.append("  <rating>{0}</rating>".format(escape(rating)))
    if tmdb_id and tmdb_id != "0":
        lines.append('  <uniqueid type="tmdb" default="true">{0}</uniqueid>'.format(escape(tmdb_id)))
        lines.append("  <tmdbid>{0}</tmdbid>".format(escape(tmdb_id)))
        lines.append("  <id>{0}</id>".format(escape(tmdb_id)))
        lines.append("  <url cache=\"tmdb-{0}.json\">https://www.themoviedb.org/movie/{0}</url>".format(escape(tmdb_id)))
    for genre in metadata.get("genres", []) or []:
        if isinstance(genre, dict):
            genre_name = genre.get("name")
        else:
            genre_name = genre
        if genre_name:
            lines.append("  <genre>{0}</genre>".format(escape(str(genre_name))))
    if poster_url:
        lines.append("  <thumb aspect=\"poster\">{0}</thumb>".format(escape(poster_url)))
    if fanart_url:
        lines.append("  <fanart>")
        lines.append("    <thumb>{0}</thumb>".format(escape(fanart_url)))
        lines.append("  </fanart>")
    lines.append("</movie>")
    return "\n".join(lines) + "\n"


def write_movie_nfo(folder, safe_name, metadata=None, show_dialog=True):
    file_path = os.path.join(folder, safe_name + ".nfo")
    content = build_movie_nfo(safe_name, metadata)
    if text_file_matches(file_path, content):
        return False

    try:
        write_text_file(file_path, content)
        xbmc.log("NFO ERSTELLT: " + file_path, xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log("NFO ERROR: " + file_path + " | " + str(e), xbmc.LOGERROR)
        if show_dialog:
            xbmcgui.Dialog().ok("NFO Fehler", file_path + "\n\n" + str(e))
        return False


def write_movie(filename, stream_url, subfolder=None, metadata=None, show_dialog=True):
    base_folder = get_movie_folder()
    safe_name = clean_filename(filename)
    category_folder = os.path.join(base_folder, clean_filename(subfolder)) if subfolder else base_folder
    folder = os.path.join(category_folder, safe_name)
    file_path = os.path.join(folder, safe_name + ".strm")

    changed = not text_file_matches(file_path, stream_url)
    if changed and not write_strm_file(file_path, stream_url, show_dialog):
        return False

    changed = write_movie_nfo(folder, safe_name, metadata, show_dialog=False) or changed
    return {"folder": folder, "changed": changed}


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
