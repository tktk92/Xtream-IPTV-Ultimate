# -*- coding: utf-8 -*-

import os
import shutil

import xbmc
import xbmcgui
import xbmcplugin
from common import HANDLE, build_url
from config import get_selected_languages
from language_filter import extract_language_from_category
from strm import write_movie, write_strm_file, clean_filename, get_movie_folder
from movie_lookup import (
    choose_movie_title,
    get_tmdb_api_key,
    title_from_tmdb_id,
    discover_recent_movies,
    search_tmdb_movie_fuzzy,
    format_tmdb_search_label
)
from kodi_library import ask_clean_and_scan_after_export
import xtream
import cache_index


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


def menu():
    items = [
        ("Filme suchen", {"mode": "search_movies"}),
        ("Kategorien", {"mode": "movie_languages"}),
        ("Neu hinzugefügt", {"mode": "movie_latest"}),
        ("TMDb: beliebte Filme der letzten 6 Monate suchen und neu laden", {"mode": "reload_tmdb_recent_selected"}),
    ]

    for label, params in items:
        li = xbmcgui.ListItem(label)
        xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, True)

    xbmcplugin.endOfDirectory(HANDLE)


def get_grouped_categories():
    categories = xtream.api("get_vod_categories")
    selected_languages = get_selected_languages()
    grouped = {}

    for cat in categories:
        name = cat.get("category_name", "Unbekannt")
        language = extract_language_from_category(name)

        if selected_languages and language not in selected_languages:
            continue

        grouped.setdefault(language, []).append(cat)

    return grouped


def get_allowed_categories():
    categories = xtream.api("get_vod_categories")
    selected_languages = get_selected_languages()
    allowed = []

    for cat in categories:
        name = cat.get("category_name", "Unbekannt")
        language = extract_language_from_category(name)

        if selected_languages and language not in selected_languages:
            continue

        allowed.append(cat)

    return allowed


def show_languages():
    grouped = get_grouped_categories()

    if not grouped:
        xbmcgui.Dialog().ok("Keine Kategorien", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    for language in sorted(grouped.keys()):
        label = f"{language} ({len(grouped[language])})"
        li = xbmcgui.ListItem(label)
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "movie_categories_by_language", "language": language}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_categories_by_language(selected_language):
    grouped = get_grouped_categories()
    categories = grouped.get(selected_language, [])

    for cat in categories:
        name = cat.get("category_name", "Unbekannt")
        cat_id = cat.get("category_id")
        li = xbmcgui.ListItem(name)

        li.addContextMenuItems([
            (
                "Kategorie komplett exportieren",
                f"RunPlugin({build_url({'mode': 'export_movie_category', 'category_id': cat_id, 'category_name': name})})"
            )
        ])

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "movie_streams", "category_id": cat_id, "category_name": name}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_streams(category_id, category_name):
    xbmcplugin.setContent(HANDLE, "movies")
    movies = xtream.api("get_vod_streams", {"category_id": category_id})

    if not movies:
        xbmcgui.Dialog().ok("Filme", "Keine Filme gefunden")
        return

    for movie in movies:
        add_movie_item(movie, category_name)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def show_latest(limit=100):
    allowed = get_allowed_categories()
    if not allowed:
        xbmcgui.Dialog().ok("Filme", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    results = []
    progress = xbmcgui.DialogProgress()
    progress.create("Neue Filme", "Lade aktuelle Filme...")

    for index, cat in enumerate(allowed):
        if progress.iscanceled():
            break
        category_id = cat.get("category_id")
        category_name = cat.get("category_name", "Unbekannt")
        progress.update(int((index + 1) / len(allowed) * 100), category_name)
        for movie in xtream.api("get_vod_streams", {"category_id": category_id}):
            movie["category_name_export"] = category_name
            results.append(movie)

    progress.close()
    results = sorted(results, key=lambda x: str(x.get("added", "0")), reverse=True)[:int(limit)]

    xbmcplugin.setContent(HANDLE, "movies")
    for movie in results:
        add_movie_item(movie, movie.get("category_name_export", "Neu"))
    xbmcplugin.endOfDirectory(HANDLE)


def format_tmdb_export_title(metadata, fallback_name):
    title = metadata.get("tmdb_title") or fallback_name
    year = metadata.get("release_year") or ""
    if year:
        return clean_filename("{0} ({1})".format(title, year))
    return clean_filename(title)


def get_selected_tmdb_language_codes():
    selected_languages = get_selected_languages()
    codes = []

    for language in selected_languages:
        if language not in TMDB_LANGUAGE_CODES:
            continue

        code = TMDB_LANGUAGE_CODES[language]
        if code not in codes:
            codes.append(code)

    if "" in codes:
        return [""]

    return codes


def get_index_movie_by_stream_id(stream_id):
    if not stream_id:
        return None

    wanted = str(stream_id)
    data = cache_index.get_current_index_for_search()
    for movie in data.get("movies", []):
        if str(movie.get("stream_id") or "") == wanted:
            return movie

    return None


def get_index_movies_by_stream_id():
    data = cache_index.get_current_index_for_search()
    result = {}
    for movie in data.get("movies", []):
        stream_id = movie.get("stream_id")
        if stream_id not in (None, ""):
            result[str(stream_id)] = movie
    return result


def get_movie_export_title(movie):
    name = movie.get("name", "Film")
    tmdb_id = movie.get("tmdb_id")

    if tmdb_id:
        return title_from_tmdb_id(tmdb_id, name)

    return clean_filename(name)


def choose_movie_export_title(stream_id, name):
    index_movie = get_index_movie_by_stream_id(stream_id)
    if index_movie and index_movie.get("tmdb_id"):
        return title_from_tmdb_id(index_movie.get("tmdb_id"), name)

    return choose_movie_title(name)


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
        if tmdb_id and tmdb_id not in candidates_by_tmdb_id:
            candidates_by_tmdb_id[tmdb_id] = movie

    return candidates_by_tmdb_id


def find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates_by_tmdb_id):
    tmdb_id = str(tmdb_movie.get("id") or "")
    return xtream_candidates_by_tmdb_id.get(tmdb_id)


def reset_tmdb_recent_folder():
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


def reload_tmdb_recent_selected(months=6, max_pages=5):
    selected_languages = get_selected_languages()

    if not get_tmdb_api_key():
        xbmcgui.Dialog().ok(
            "TMDb Import",
            "Bitte zuerst in den Addon-Einstellungen den TMDb API Key eintragen."
        )
        return

    if not selected_languages:
        xbmcgui.Dialog().ok(
            "TMDb Import",
            "Bitte zuerst eine Sprache auswählen."
        )
        return

    language_codes = get_selected_tmdb_language_codes()
    if not language_codes:
        xbmcgui.Dialog().ok(
            "TMDb Import",
            "Für die ausgewählte Sprache gibt es noch keine TMDb-Zuordnung."
        )
        return

    confirm = xbmcgui.Dialog().yesno(
        "TMDb Import",
        "Es werden bekannte/beliebte TMDb-Releases der letzten {0} Monate gesucht und mit deinem Index abgeglichen.\n\n"
        "Der Ordner '{1}' wird vorher gelöscht und neu erstellt.".format(months, TMDB_RECENT_FOLDER),
        nolabel="Nein",
        yeslabel="Starten"
    )

    if not confirm:
        return

    progress = xbmcgui.DialogProgress()
    progress.create("TMDb Import", "Lade TMDb Releases...")
    tmdb_movies = discover_recent_movies(language_codes, months=months, max_pages=max_pages)

    if progress.iscanceled():
        progress.close()
        return

    if not tmdb_movies:
        progress.close()
        xbmcgui.Dialog().ok("TMDb Import", "Keine TMDb Releases gefunden.")
        return

    progress.update(15, "Gleiche mit Xtream Index ab...")
    xtream_candidates = get_xtream_movie_candidates(selected_languages)
    matches = []
    seen_stream_ids = set()
    total = len(tmdb_movies)

    for index, tmdb_movie in enumerate(tmdb_movies):
        if progress.iscanceled():
            progress.close()
            return

        progress.update(15 + int((index + 1) / total * 65), tmdb_movie.get("title", "Film"))
        match = find_xtream_match_for_tmdb(tmdb_movie, xtream_candidates)
        if not match:
            continue

        stream_id = match.get("stream_id")
        if stream_id in seen_stream_ids:
            continue

        item = dict(match)
        release_date = tmdb_movie.get("release_date", "")
        item.update({
            "tmdb_id": tmdb_movie.get("id"),
            "tmdb_title": tmdb_movie.get("title") or tmdb_movie.get("original_title") or match.get("name", "Film"),
            "tmdb_original_title": tmdb_movie.get("original_title", ""),
            "release_date": release_date,
            "release_year": release_date[:4] if len(release_date) >= 4 else ""
        })
        matches.append(item)
        seen_stream_ids.add(stream_id)

    if not matches:
        progress.close()
        xbmcgui.Dialog().ok("TMDb Import", "Keine passenden Filme in deinem Index gefunden.")
        return

    try:
        export_folder = reset_tmdb_recent_folder()
    except Exception as e:
        progress.close()
        xbmcgui.Dialog().ok("TMDb Import", str(e))
        return

    created = 0
    failed = []
    total = len(matches)

    for index, movie in enumerate(matches):
        if progress.iscanceled():
            break

        name = format_tmdb_export_title(movie, movie.get("name", "Film"))
        progress.update(80 + int((index + 1) / total * 20), name)

        try:
            stream_id = movie.get("stream_id")
            if not stream_id:
                failed.append(name + " - Keine Stream-ID")
                continue

            stream_url = xtream.movie_url(stream_id, movie.get("container_extension", "mp4"))
            file_path = os.path.join(export_folder, clean_filename(name) + ".strm")
            if write_strm_file(file_path, stream_url, show_dialog=False):
                created += 1
            else:
                failed.append(name + " - STRM konnte nicht erstellt werden")

        except Exception as e:
            failed.append(name + " - " + str(e))
            xbmc.log("[IPTV Addon] Fehler beim TMDb 3-Monate-Import: " + name + " | " + str(e), xbmc.LOGERROR)

    progress.close()

    if failed:
        xbmcgui.Dialog().textviewer(
            "TMDb Import",
            "Gefunden: {0}\nErstellt: {1}\nFehlerhaft: {2}\n\n{3}".format(
                len(matches),
                created,
                len(failed),
                "\n".join(failed)
            )
        )
    else:
        xbmcgui.Dialog().notification(
            "TMDb Import fertig",
            "{0} Filme neu erstellt".format(created),
            xbmcgui.NOTIFICATION_INFO,
            5000
        )

    if created > 0:
        ask_clean_and_scan_after_export()


def add_movie_item(movie, category_name):
    name = movie.get("name", "Film")
    stream_id = movie.get("stream_id")
    extension = movie.get("container_extension", "mp4")
    li = xbmcgui.ListItem(name)

    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({
            "mode": "export_movie",
            "stream_id": stream_id,
            "name": name,
            "ext": extension,
            "category_name": category_name
        }),
        li,
        False
    )


def search_movies_via_tmdb(search_text):
    if not get_tmdb_api_key():
        return False

    tmdb_results = search_tmdb_movie_fuzzy(search_text, limit=8)
    if not tmdb_results:
        return False

    labels = []
    for movie in tmdb_results:
        label = format_tmdb_search_label(movie, "movie")
        original = movie.get("original_title") or ""
        if original and original not in label:
            label += " / " + original
        labels.append(label)

    labels.append("Normale Index-Suche verwenden")
    index = xbmcgui.Dialog().select("TMDb Film auswählen", labels)

    if index == -1:
        return True

    if index >= len(tmdb_results):
        return False

    selected = tmdb_results[index]
    matches = cache_index.find_movies_by_tmdb_id(selected.get("id"))

    if not matches:
        xbmcgui.Dialog().ok(
            "Nicht gefunden",
            "Dieser TMDb-Treffer wurde in deinem Xtream-Index nicht gefunden.\n\n"
            "Du kannst danach noch die normale Index-Suche verwenden."
        )
        return False

    xbmcplugin.setContent(HANDLE, "movies")
    for movie in matches:
        add_movie_item(movie, movie.get("category_name", "TMDb"))

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)
    return True


def search_movies():
    keyboard = xbmc.Keyboard("", "Film suchen")
    keyboard.doModal()

    if not keyboard.isConfirmed():
        return

    search_text = keyboard.getText().strip().lower()
    if not search_text:
        return

    if search_movies_via_tmdb(search_text):
        return

    indexed_results = cache_index.search_movies(search_text)
    if indexed_results:
        xbmcplugin.setContent(HANDLE, "movies")
        for movie in indexed_results:
            add_movie_item(movie, movie.get("category_name", "Index"))
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    allowed_categories = get_allowed_categories()
    if not allowed_categories:
        xbmcgui.Dialog().ok("Suche", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    results = []
    progress = xbmcgui.DialogProgress()
    progress.create("Suche läuft", "Durchsuche ausgewählte Sprachen...")

    for index, cat in enumerate(allowed_categories):
        if progress.iscanceled():
            break

        category_id = cat.get("category_id")
        category_name = cat.get("category_name", "Unbekannt")
        progress.update(int((index + 1) / len(allowed_categories) * 100), category_name)
        movies = xtream.api("get_vod_streams", {"category_id": category_id})

        for movie in movies:
            name = movie.get("name", "")
            if search_text in name.lower():
                movie["category_name_export"] = category_name
                results.append(movie)

    progress.close()

    if not results:
        xbmcgui.Dialog().ok("Suche", "Keine Filme gefunden")
        return

    xbmcplugin.setContent(HANDLE, "movies")
    for movie in results:
        add_movie_item(movie, movie.get("category_name_export", "Suche"))

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def export_movie(stream_id, name, ext, category_name):
    clean_name = choose_movie_export_title(stream_id, name)
    clean_category = clean_filename(category_name) if category_name else None
    stream_url = xtream.movie_url(stream_id, ext)

    ok = write_movie(
        clean_name,
        stream_url,
        clean_category
    )

    if ok:
        xbmcgui.Dialog().notification(
            "STRM erstellt",
            clean_name,
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
        ask_clean_and_scan_after_export()


def export_category(category_id, category_name):
    movies = xtream.api("get_vod_streams", {"category_id": category_id})

    if not movies:
        xbmcgui.Dialog().ok("Export", "Keine Filme gefunden")
        return

    count = len(movies)
    created = 0
    failed = []
    index_movies = get_index_movies_by_stream_id()
    progress = xbmcgui.DialogProgress()
    progress.create("Exportiere Kategorie", category_name)

    for index, movie in enumerate(movies):
        if progress.iscanceled():
            break

        name = movie.get("name", "Film")
        index_movie = index_movies.get(str(movie.get("stream_id") or ""))
        if index_movie:
            movie.update({
                "tmdb_id": index_movie.get("tmdb_id"),
                "metadata_checked_at": index_movie.get("metadata_checked_at")
            })
        clean_name = get_movie_export_title(movie)
        clean_category = clean_filename(category_name) if category_name else None
        stream_id = movie.get("stream_id")
        extension = movie.get("container_extension", "mp4")

        try:
            if not stream_id:
                failed.append(clean_name + " - Keine Stream-ID")
                continue

            stream_url = xtream.movie_url(stream_id, extension)

            if write_movie(clean_name, stream_url, clean_category, show_dialog=False):
                created += 1
            else:
                failed.append(clean_name + " - STRM konnte nicht erstellt werden")

        except Exception as e:
            failed.append(clean_name + " - " + str(e))
            xbmc.log("[IPTV Addon] Fehler beim Film-Export: " + clean_name + " | " + str(e), xbmc.LOGERROR)
            continue

        progress.update(int((index + 1) / count * 100), clean_name)

    progress.close()

    if failed:
        xbmcgui.Dialog().textviewer(
            "Fehlerhafte Filme",
            f"Erstellt: {created} von {count}\nFehlerhaft: {len(failed)}\n\n" + "\n".join(failed)
        )
    else:
        xbmcgui.Dialog().notification("Export fertig", f"{created} STRM Dateien erstellt", xbmcgui.NOTIFICATION_INFO, 5000)

    if created > 0:
        ask_clean_and_scan_after_export()
