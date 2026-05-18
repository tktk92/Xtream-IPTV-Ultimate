# -*- coding: utf-8 -*-

import sys
import urllib.parse

import xbmcgui

import menus
import movies
import series
import library
import kodi_library
import live_tv
import storage
import stream_check
import settings_helper
import cache_index
from strm import ensure_media_folders


def router():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    mode = params.get("mode")

    if mode is None:
        ensure_media_folders()
        settings_helper.run_setup_wizard(force=False)
        cache_index.ensure_index(show_progress=True)
        menus.main_menu()

    elif mode == "add_menu":
        menus.add_menu()

    elif mode == "library_menu":
        menus.library_menu()

    elif mode == "setup_live_tv":
        live_tv.setup_live_tv()

    elif mode == "reset_live_tv":
        live_tv.reset_live_tv_data()

    elif mode == "settings_menu":
        menus.settings_menu()

    elif mode == "open_settings":
        settings_helper.open_settings()

    elif mode == "setup_wizard":
        settings_helper.run_setup_wizard(force=True)

    elif mode == "choose_languages":
        settings_helper.choose_languages()

    elif mode == "movies_menu":
        movies.menu()

    elif mode == "movie_languages":
        movies.show_languages()

    elif mode == "movie_categories_by_language":
        movies.show_categories_by_language(params.get("language"))

    elif mode == "movie_streams":
        movies.show_streams(params.get("category_id"), params.get("category_name"))

    elif mode == "movie_latest":
        movies.show_latest()

    elif mode == "reload_tmdb_recent_selected":
        movies.reload_tmdb_recent_selected()

    elif mode == "search_movies":
        movies.search_movies()

    elif mode == "export_movie":
        movies.export_movie(params.get("stream_id"), params.get("name"), params.get("ext"), params.get("category_name"))

    elif mode == "export_movie_category":
        movies.export_category(params.get("category_id"), params.get("category_name"))

    elif mode == "series_menu":
        series.menu()

    elif mode == "series_languages":
        series.show_languages()

    elif mode == "series_categories_by_language":
        series.show_categories_by_language(params.get("language"))

    elif mode == "series_list":
        series.show_series_list(params.get("category_id"), params.get("category_name"))

    elif mode == "series_info":
        series.show_series_info(params.get("series_id"), params.get("series_name"))

    elif mode == "series_season":
        series.show_season(params.get("series_id"), params.get("series_name"), params.get("season"))

    elif mode == "series_latest":
        series.show_latest()

    elif mode == "search_series":
        series.search_series()

    elif mode == "export_episode":
        series.export_episode(params.get("series_id"), params.get("series_name"), params.get("season"), params.get("episode"), params.get("episode_title"), params.get("episode_id"), params.get("ext"))

    elif mode == "export_series":
        series.export_series(params.get("series_id"), params.get("series_name"))

    elif mode == "export_season":
        series.export_season(params.get("series_id"), params.get("series_name"), params.get("season"))

    elif mode == "library_series":
        library.show_series_library()

    elif mode == "library_seasons":
        library.show_library_seasons(params.get("path"))

    elif mode == "library_episodes":
        library.show_library_episodes(params.get("path"))

    elif mode == "library_movies":
        library.show_movies_library()

    elif mode == "delete_library_item":
        library.delete_library_item(params.get("path"))

    elif mode == "delete_all_streams":
        library.delete_all_streams()

    elif mode == "stream_check_menu":
        menus.stream_check_menu()

    elif mode == "check_streams":
        stream_check.check_streams(params.get("scope", "all"))

    elif mode == "show_broken_streams":
        stream_check.show_broken_streams()

    elif mode == "kodi_library_menu":
        menus.kodi_library_menu()

    elif mode == "setup_sources":
        kodi_library.setup_kodi_sources()

    elif mode == "setup_library_content":
        kodi_library.setup_video_library_content(show_dialog=True)

    elif mode == "install_metadata_scrapers":
        kodi_library.install_metadata_scrapers(show_dialog=True)

    elif mode == "scan_library":
        kodi_library.scan_kodi_library()

    elif mode == "clean_library":
        kodi_library.clean_kodi_library()

    elif mode == "clean_and_scan_library":
        kodi_library.clean_and_scan_kodi_library()

    elif mode == "index_menu":
        menus.index_menu()

    elif mode == "rebuild_index":
        cache_index.rebuild_index()

    elif mode == "rebuild_basic_index":
        cache_index.rebuild_basic_index()

    elif mode == "show_index_info":
        cache_index.show_index_info()

    elif mode == "metadata_groups":
        cache_index.show_metadata_groups()

    elif mode == "storage_menu":
        menus.storage_menu()

    elif mode == "show_movie_path":
        storage.show_movie_path()

    elif mode == "show_series_path":
        storage.show_series_path()

    elif mode == "show_internal_paths":
        storage.show_internal_paths()

    elif mode == "show_free_space":
        storage.show_free_space()

    else:
        xbmcgui.Dialog().ok("Fehler", "Unbekannter Modus:\n" + str(mode))


if __name__ == "__main__":
    router()
