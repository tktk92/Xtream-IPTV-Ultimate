# -*- coding: utf-8 -*-

import json
import os
import shutil
import time

import xbmc
import xbmcvfs

import cache_index
import xtream
from kodi_library import scan_kodi_library_after_export
from common import ADDON, ADDON_PROFILE
from config import get_selected_languages
from language_filter import extract_language_from_category
from movie_lookup import discover_recent_movies, get_tmdb_movie_by_id
from strm import clean_filename, get_movie_folder, write_movie


TMDB_LANGUAGE_CODES = {
    "Deutsch": "",
    "Englisch": "en",
    "Tamil": "ta",
    "Arabisch": "ar",
    "Tuerkisch": "tr",
    "TÃ¼rkisch": "tr",
    "Türkisch": "tr",
    "Hindi": "hi",
    "Franzoesisch": "fr",
    "FranzÃ¶sisch": "fr",
    "Französisch": "fr",
    "Spanisch": "es",
    "Italienisch": "it",
    "Russisch": "ru",
}

TMDB_RECENT_FOLDER = "Neue Filme letztes Jahr"
STATE_FILE = os.path.join(ADDON_PROFILE, "auto_import_state.json")
RUN_INTERVAL_SECONDS = 24 * 60 * 60
DEFAULT_RECENT_LIMIT_PER_LANGUAGE = 100
DEFAULT_RECENT_MONTHS = 12
DEFAULT_RECENT_MAX_PAGES = 40


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[Xtream IPTV Ultimate AutoImport] " + str(message), level)


def get_setting_bool(key, default=False):
    value = ADDON.getSetting(key).strip().lower()
    if value == "":
        return default
    return value in ("true", "1", "yes", "ja")


def get_setting_int(key, default, minimum=1, maximum=1000):
    try:
        value = int(ADDON.getSetting(key).strip() or default)
    except Exception:
        value = default
    return max(int(minimum), min(int(maximum), value))


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
        "matched": matched,
    })


def get_tmdb_language_code(language):
    return TMDB_LANGUAGE_CODES.get(language)


def get_xtream_movie_candidates(selected_languages):
    data = cache_index.get_current_index_for_search()
    wanted = set(selected_languages or [])
    candidates_by_tmdb_id = {}

    for movie in data.get("movies", []):
        category_name = movie.get("category_name", "")
        language = extract_language_from_category(category_name)

        if wanted and language not in wanted:
            continue

        tmdb_id = str(movie.get("tmdb_id") or "")
        if tmdb_id and tmdb_id != "0" and tmdb_id not in candidates_by_tmdb_id:
            candidates_by_tmdb_id[tmdb_id] = movie

    return candidates_by_tmdb_id


def find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates_by_tmdb_id):
    tmdb_id = str(tmdb_movie.get("id") or "")
    return xtream_candidates_by_tmdb_id.get(tmdb_id)


def item_added_timestamp(item):
    try:
        return int(float(item.get("added") or 0))
    except Exception:
        return 0


def movie_is_recently_added(item, months):
    added = item_added_timestamp(item)
    if not added:
        return False
    return added >= int(time.time()) - int(months) * 31 * 24 * 60 * 60


def enrich_movie_with_tmdb_details(movie):
    tmdb_id = str(movie.get("tmdb_id") or "").strip()
    if not tmdb_id or tmdb_id == "0":
        return movie

    details = get_tmdb_movie_by_id(tmdb_id, "de-DE") or get_tmdb_movie_by_id(tmdb_id, "en-US")
    if not details:
        return movie

    release_date = details.get("release_date") or movie.get("release_date") or ""
    item = dict(movie)
    item.update({
        "tmdb_id": details.get("id") or tmdb_id,
        "tmdb_title": details.get("title") or movie.get("tmdb_title") or movie.get("name", "Film"),
        "tmdb_original_title": details.get("original_title") or movie.get("tmdb_original_title", ""),
        "overview": details.get("overview") or movie.get("overview", ""),
        "poster_path": details.get("poster_path") or movie.get("poster_path", ""),
        "backdrop_path": details.get("backdrop_path") or movie.get("backdrop_path", ""),
        "rating": details.get("vote_average") or movie.get("rating", ""),
        "runtime": details.get("runtime") or movie.get("runtime", ""),
        "genres": details.get("genres") or movie.get("genres", []),
        "release_date": release_date,
        "release_year": release_date[:4] if len(release_date) >= 4 else movie.get("release_year", ""),
    })
    return item


def add_match(matches, seen_stream_ids, movie, limit):
    stream_id = movie.get("stream_id")
    if not stream_id or stream_id in seen_stream_ids:
        return False

    matches.append(movie)
    seen_stream_ids.add(stream_id)
    return len(matches) >= int(limit)


def collect_added_matches_for_language(language, limit, months):
    data = cache_index.get_current_index_for_search()
    candidates = []

    for movie in data.get("movies", []):
        category_name = movie.get("category_name", "")
        if extract_language_from_category(category_name) != language:
            continue
        if not movie_is_recently_added(movie, months):
            continue
        if not movie.get("tmdb_id") or str(movie.get("tmdb_id")) == "0":
            continue
        candidates.append(movie)

    candidates.sort(key=item_added_timestamp, reverse=True)
    matches = []
    seen_stream_ids = set()

    for movie in candidates:
        enriched = enrich_movie_with_tmdb_details(movie)
        if add_match(matches, seen_stream_ids, enriched, limit):
            break

    return matches, seen_stream_ids


def tmdb_movie_to_export_item(tmdb_movie, match):
    release_date = tmdb_movie.get("release_date", "")
    item = dict(match)
    item.update({
        "tmdb_id": tmdb_movie.get("id"),
        "tmdb_title": tmdb_movie.get("title") or tmdb_movie.get("original_title") or match.get("name", "Film"),
        "tmdb_original_title": tmdb_movie.get("original_title", ""),
        "overview": tmdb_movie.get("overview", ""),
        "poster_path": tmdb_movie.get("poster_path", ""),
        "backdrop_path": tmdb_movie.get("backdrop_path", ""),
        "rating": tmdb_movie.get("vote_average", ""),
        "release_date": release_date,
        "release_year": release_date[:4] if len(release_date) >= 4 else "",
    })
    return item


def fill_matches_from_tmdb(language, matches, seen_stream_ids, limit, months, max_pages):
    language_code = get_tmdb_language_code(language)
    if language_code is None:
        return 0

    tmdb_movies = discover_recent_movies([language_code], months=months, max_pages=max_pages)
    if not tmdb_movies:
        return 0

    xtream_candidates = get_xtream_movie_candidates([language])
    added = 0

    for tmdb_movie in tmdb_movies:
        match = find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates)
        if not match:
            continue

        item = tmdb_movie_to_export_item(tmdb_movie, match)
        added += 1
        if add_match(matches, seen_stream_ids, item, limit):
            break

    return added


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
        raise Exception("Ungueltiger Exportordner: " + export_folder)

    if os.path.exists(export_folder):
        shutil.rmtree(export_folder)

    os.makedirs(export_folder, exist_ok=True)
    return export_folder


def run_popular_recent_import(months=None, max_pages=None, limit_per_language=None):
    selected_languages = get_selected_languages()
    if not selected_languages:
        log("Kein Sprachfilter gewaehlt, Auto-Import uebersprungen.")
        return 0, 0

    months = int(months or get_setting_int("auto_tmdb_recent_months", DEFAULT_RECENT_MONTHS, 1, 36))
    max_pages = int(max_pages or get_setting_int("auto_tmdb_recent_max_pages", DEFAULT_RECENT_MAX_PAGES, 1, 100))
    limit_per_language = int(limit_per_language or get_setting_int(
        "auto_tmdb_recent_limit_per_language",
        DEFAULT_RECENT_LIMIT_PER_LANGUAGE,
        1,
        1000,
    ))

    supported_languages = [language for language in selected_languages if get_tmdb_language_code(language) is not None]
    if not supported_languages:
        log("Keine TMDb-Sprachzuordnung fuer: " + ", ".join(selected_languages), xbmc.LOGWARNING)
        return 0, 0

    cache_index.ensure_index(show_progress=False, notify=False)

    matches = []
    language_counts = {}

    for language in supported_languages:
        language_matches, seen_stream_ids = collect_added_matches_for_language(language, limit_per_language, months)
        if len(language_matches) < limit_per_language:
            fill_matches_from_tmdb(
                language,
                language_matches,
                seen_stream_ids,
                limit_per_language,
                months,
                max_pages,
            )

        language_counts[language] = len(language_matches)
        matches.extend(language_matches)
        log("{0}: {1} neue Filme ausgewaehlt".format(language, len(language_matches)))

    if not matches:
        log("Keine passenden Filme im Index gefunden.")
        return 0, 0

    reset_export_folder()
    created = 0

    for movie in matches:
        stream_id = movie.get("stream_id")
        if not stream_id:
            continue

        name = format_tmdb_export_title(movie, movie.get("name", "Film"))
        stream_url = xtream.movie_url(stream_id, movie.get("container_extension", "mp4"))

        if write_movie(name, stream_url, TMDB_RECENT_FOLDER, metadata=movie, show_dialog=False):
            created += 1

    log("Auto-Import fertig. Treffer: {0}, erstellt: {1} | {2}".format(len(matches), created, language_counts))
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
        created, matched = run_popular_recent_import()
        mark_run(created, matched)

        if created > 0:
            scan_kodi_library_after_export(os.path.join(get_movie_folder(), clean_filename(TMDB_RECENT_FOLDER)))
    except Exception as e:
        log("Auto-Import fehlgeschlagen: " + str(e), xbmc.LOGERROR)
