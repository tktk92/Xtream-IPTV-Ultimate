# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcplugin

import cache_index
import movies
import series
from common import HANDLE
from movie_lookup import (
    format_tmdb_search_label,
    get_tmdb_api_key,
    search_tmdb_movie_fuzzy,
    search_tmdb_tv_fuzzy,
)


def _search_via_tmdb(search_text):
    if not get_tmdb_api_key():
        return False

    results = []
    for movie in search_tmdb_movie_fuzzy(search_text, limit=6):
        results.append(("movie", movie, "[Film] " + format_tmdb_search_label(movie, "movie")))

    for tvshow in search_tmdb_tv_fuzzy(search_text, limit=6):
        results.append(("tv", tvshow, "[Serie] " + format_tmdb_search_label(tvshow, "tv")))

    if not results:
        return False

    labels = [item[2] for item in results]
    labels.append("Normale Index-Suche verwenden")
    index = xbmcgui.Dialog().select("Suchen", labels)

    if index == -1:
        return True

    if index >= len(results):
        return False

    media_type, item, _label = results[index]
    tmdb_id = item.get("id")
    if media_type == "movie":
        matches = cache_index.find_movies_by_tmdb_id(tmdb_id)
        if matches:
            xbmcplugin.setContent(HANDLE, "movies")
            for movie in matches:
                movies.add_movie_item(movie, movie.get("category_name", "TMDb"))
            xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.endOfDirectory(HANDLE)
            return True
    else:
        matches = cache_index.find_series_by_tmdb_id(tmdb_id)
        if matches:
            xbmcplugin.setContent(HANDLE, "tvshows")
            for serie in matches:
                series.add_series_item(serie)
            xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.endOfDirectory(HANDLE)
            return True

    xbmcgui.Dialog().ok(
        "Nicht gefunden",
        "Dieser TMDb-Treffer wurde in deinem Xtream-Index nicht gefunden.\n\n"
        "Du kannst danach noch die normale Index-Suche verwenden.",
    )
    return False


def search_all():
    keyboard = xbmc.Keyboard("", "Filme und Serien suchen")
    keyboard.doModal()

    if not keyboard.isConfirmed():
        return

    search_text = keyboard.getText().strip().lower()
    if not search_text:
        return

    if _search_via_tmdb(search_text):
        return

    movie_results = cache_index.search_movies(search_text)
    series_results = cache_index.search_series(search_text)

    if not movie_results and not series_results:
        xbmcgui.Dialog().ok("Suche", "Keine Filme oder Serien gefunden.")
        return

    for movie in movie_results:
        name = movie.get("name", "Film")
        li = xbmcgui.ListItem("[Film] " + name)
        movies.add_movie_item(movie, movie.get("category_name", "Index"))

    for serie in series_results:
        original_name = serie.get("name", "Serie")
        serie = dict(serie)
        serie["name"] = "[Serie] " + original_name
        series.add_series_item(serie)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)
