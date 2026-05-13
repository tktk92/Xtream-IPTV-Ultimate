# -*- coding: utf-8 -*-

import json
import os
import shutil
import time

import xbmc
import xbmcvfs

import cache_index
import xtream
from common import ADDON, ADDON_PROFILE
from config import get_selected_languages
from language_filter import extract_language_from_category
from movie_lookup import discover_recent_movies, prepare_movie_search_title
from strm import clean_filename, get_movie_folder, write_strm_file


TMDB_LANGUAGE_CODES = {
    "Deutsch": "",
    "Englisch": "en",
    "Tamil": "ta",
    "Arabisch": "ar",
    "Türkisch": "tr",
    "Hindi": "hi",
    "Französisch": "fr",
    "Spanisch": "es",
    "Italienisch": "it",
    "Russisch": "ru"
}

TMDB_RECENT_FOLDER = "TMDb Beliebte Releases letzte 6 Monate"
STATE_FILE = os.path.join(ADDON_PROFILE, "auto_import_state.json")
RUN_INTERVAL_SECONDS = 24 * 60 * 60


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[Xtream IPTV Ultimate AutoImport] " + str(message), level)


def get_setting_bool(key, default=False):
    value = ADDON.getSetting(key).strip().lower()
    if value == "":
        return default
    return value in ("true", "1", "yes", "ja")


def get_state_path():
    return xbmcvfs.translatePath(STATE_FILE)


def load_state():
    path = get_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    path = get_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_run():
    state = load_state()
    last_run = float(state.get("last_run", 0) or 0)
    return (time.time() - last_run) >= RUN_INTERVAL_SECONDS


def mark_run(created, matched):
    save_state({
        "last_run": time.time(),
        "created": created,
        "matched": matched
    })


def get_selected_tmdb_language_codes():
    codes = []
    for language in get_selected_languages():
        if language not in TMDB_LANGUAGE_CODES:
            continue
        code = TMDB_LANGUAGE_CODES[language]
        if code not in codes:
            codes.append(code)
    if "" in codes:
        return [""]
    return codes


def normalize_movie_match_title(title):
    prepared = prepare_movie_search_title(title)
    return clean_filename(prepared or title).lower()


def get_xtream_movie_candidates(selected_languages):
    data = cache_index.get_current_index_for_search()
    wanted = set(selected_languages or [])
    candidates = []

    for movie in data.get("movies", []):
        category_name = movie.get("category_name", "")
        language = extract_language_from_category(category_name)

        if wanted and language not in wanted:
            continue

        item = dict(movie)
        item["match_title"] = normalize_movie_match_title(item.get("name", ""))
        if item["match_title"]:
            candidates.append(item)

    return candidates


def find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates):
    tmdb_id = str(tmdb_movie.get("id") or "")
    if tmdb_id:
        for candidate in xtream_candidates:
            if str(candidate.get("tmdb_id") or "") == tmdb_id:
                return candidate

    titles = [
        tmdb_movie.get("title", ""),
        tmdb_movie.get("original_title", "")
    ]
    normalized_titles = []

    for title in titles:
        normalized = normalize_movie_match_title(title)
        if normalized and normalized not in normalized_titles:
            normalized_titles.append(normalized)

    for normalized in normalized_titles:
        for candidate in xtream_candidates:
            if candidate.get("match_title") == normalized:
                return candidate

    for normalized in normalized_titles:
        if len(normalized) < 5:
            continue
        for candidate in xtream_candidates:
            candidate_title = candidate.get("match_title", "")
            if len(candidate_title) < 5:
                continue
            if normalized in candidate_title or candidate_title in normalized:
                return candidate

    return None


def format_tmdb_export_title(movie, fallback_name):
    title = movie.get("tmdb_title") or fallback_name
    release_date = movie.get("release_date") or ""
    year = release_date[:4] if len(release_date) >= 4 else ""
    if year:
        return clean_filename("{0} ({1})".format(title, year))
    return clean_filename(title)


def reset_export_folder():
    base_folder = get_movie_folder()
    export_folder = os.path.join(base_folder, clean_filename(TMDB_RECENT_FOLDER))
    base_abs = os.path.abspath(base_folder)
    export_abs = os.path.abspath(export_folder)

    if os.path.commonpath([base_abs, export_abs]) != base_abs:
        raise Exception("Ungültiger Exportordner: " + export_folder)

    if os.path.exists(export_folder):
        shutil.rmtree(export_folder)

    os.makedirs(export_folder, exist_ok=True)
    return export_folder


def run_popular_recent_import(months=6, max_pages=5):
    selected_languages = get_selected_languages()
    if not selected_languages:
        log("Kein Sprachfilter gewählt, Auto-Import übersprungen.")
        return 0, 0

    language_codes = get_selected_tmdb_language_codes()
    if not language_codes:
        log("Keine TMDb-Sprachzuordnung für: " + ", ".join(selected_languages), xbmc.LOGWARNING)
        return 0, 0

    cache_index.ensure_index(show_progress=False, notify=False)

    tmdb_movies = discover_recent_movies(language_codes, months=months, max_pages=max_pages)
    if not tmdb_movies:
        log("Keine TMDb-Releases gefunden.")
        return 0, 0

    xtream_candidates = get_xtream_movie_candidates(selected_languages)
    matches = []
    seen_stream_ids = set()

    for tmdb_movie in tmdb_movies:
        match = find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates)
        if not match:
            continue

        stream_id = match.get("stream_id")
        if stream_id in seen_stream_ids:
            continue

        release_date = tmdb_movie.get("release_date", "")
        item = dict(match)
        item.update({
            "tmdb_id": tmdb_movie.get("id"),
            "tmdb_title": tmdb_movie.get("title") or tmdb_movie.get("original_title") or match.get("name", "Film"),
            "tmdb_original_title": tmdb_movie.get("original_title", ""),
            "release_date": release_date
        })
        matches.append(item)
        seen_stream_ids.add(stream_id)

    if not matches:
        log("Keine passenden Filme im Index gefunden.")
        return 0, 0

    export_folder = reset_export_folder()
    created = 0

    for movie in matches:
        stream_id = movie.get("stream_id")
        if not stream_id:
            continue

        name = format_tmdb_export_title(movie, movie.get("name", "Film"))
        stream_url = xtream.movie_url(stream_id, movie.get("container_extension", "mp4"))
        file_path = os.path.join(export_folder, clean_filename(name) + ".strm")

        if write_strm_file(file_path, stream_url, show_dialog=False):
            created += 1

    log("Auto-Import fertig. Treffer: {0}, erstellt: {1}".format(len(matches), created))
    return created, len(matches)


def run_startup_import():
    if not get_setting_bool("auto_tmdb_recent_import", True):
        log("Auto-Import ist deaktiviert.")
        return

    if not should_run():
        log("Auto-Import heute bereits gelaufen.")
        return

    try:
        cache_index.ensure_index(show_progress=False, notify=False)
        cache_index.update_next_metadata_group(show_progress=False, notify=False)
        created, matched = run_popular_recent_import()
        mark_run(created, matched)

        if created > 0:
            xbmc.executebuiltin("CleanLibrary(video)", True)
            xbmc.executebuiltin("UpdateLibrary(video)", True)
    except Exception as e:
        log("Auto-Import fehlgeschlagen: " + str(e), xbmc.LOGERROR)
