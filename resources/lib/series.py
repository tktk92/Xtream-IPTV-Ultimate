# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcplugin

from common import HANDLE, build_url
from config import get_selected_languages
from language_filter import extract_language_from_category
from strm import write_episode, clean_filename
from kodi_library import ask_clean_and_scan_after_export
import xtream
import cache_index
from movie_lookup import get_tmdb_api_key, search_tmdb_tv_fuzzy, format_tmdb_search_label


def menu():
    items = [
        ("Serien suchen", {"mode": "search_series"}),
        ("Kategorien", {"mode": "series_languages"}),
        ("Neu hinzugefügt", {"mode": "series_latest"}),
    ]

    for label, params in items:
        li = xbmcgui.ListItem(label)
        xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, True)

    xbmcplugin.endOfDirectory(HANDLE)


def get_grouped_categories():
    categories = xtream.api("get_series_categories")
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
    categories = xtream.api("get_series_categories")
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
        xbmcgui.Dialog().ok("Keine Serien-Kategorien", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    for language in sorted(grouped.keys()):
        label = f"{language} ({len(grouped[language])})"
        li = xbmcgui.ListItem(label)
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "series_categories_by_language", "language": language}),
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

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "series_list", "category_id": cat_id, "category_name": name}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_series_list(category_id, category_name):
    xbmcplugin.setContent(HANDLE, "tvshows")
    series_list = xtream.api("get_series", {"category_id": category_id})

    if not series_list:
        xbmcgui.Dialog().ok("Serien", "Keine Serien gefunden")
        return

    for serie in series_list:
        add_series_item(serie)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def add_series_item(serie):
    name = serie.get("name", "Serie")
    series_id = serie.get("series_id")
    li = xbmcgui.ListItem(name)

    li.addContextMenuItems([
        (
            "Komplette Serie exportieren",
            f"RunPlugin({build_url({'mode': 'export_series', 'series_id': series_id, 'series_name': name})})"
        )
    ])

    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({"mode": "series_info", "series_id": series_id, "series_name": name}),
        li,
        True
    )


def search_series_via_tmdb(search_text):
    if not get_tmdb_api_key():
        return False

    tmdb_results = search_tmdb_tv_fuzzy(search_text, limit=8)
    if not tmdb_results:
        return False

    labels = []
    for serie in tmdb_results:
        label = format_tmdb_search_label(serie, "tv")
        original = serie.get("original_name") or ""
        if original and original not in label:
            label += " / " + original
        labels.append(label)

    labels.append("Normale Index-Suche verwenden")
    index = xbmcgui.Dialog().select("TMDb Serie auswählen", labels)

    if index == -1:
        return True

    if index >= len(tmdb_results):
        return False

    selected = tmdb_results[index]
    matches = cache_index.find_series_by_tmdb_id(selected.get("id"))

    if not matches:
        xbmcgui.Dialog().ok(
            "Nicht gefunden",
            "Dieser TMDb-Treffer wurde in deinem Xtream-Index nicht gefunden.\n\n"
            "Du kannst danach noch die normale Index-Suche verwenden."
        )
        return False

    xbmcplugin.setContent(HANDLE, "tvshows")
    for serie in matches:
        add_series_item(serie)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)
    return True


def show_series_info(series_id, series_name):
    info = xtream.api("get_series_info", {"series_id": series_id})
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}

    if not episodes:
        xbmcgui.Dialog().ok("Serie", "Keine Episoden gefunden")
        return

    for season_num in sorted(episodes.keys(), key=lambda x: int(x) if str(x).isdigit() else 999):
        season_label = "Staffel " + str(season_num).zfill(2)
        li = xbmcgui.ListItem(season_label)

        li.addContextMenuItems([
            (
                "Diese Staffel exportieren",
                f"RunPlugin({build_url({'mode': 'export_season', 'series_id': series_id, 'series_name': series_name, 'season': season_num})})"
            )
        ])

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "series_season", "series_id": series_id, "series_name": series_name, "season": season_num}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def get_season_episodes(episodes, season):
    if str(season).isdigit():
        return episodes.get(str(season), []) or episodes.get(int(season), [])
    return episodes.get(str(season), [])


def show_season(series_id, series_name, season):
    xbmcplugin.setContent(HANDLE, "episodes")
    info = xtream.api("get_series_info", {"series_id": series_id})
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}
    season_episodes = get_season_episodes(episodes, season)

    if not season_episodes:
        xbmcgui.Dialog().ok("Staffel", "Keine Episoden gefunden")
        return

    for ep in season_episodes:
        title = ep.get("title") or ep.get("name") or "Episode"
        episode_id = ep.get("id")
        ext = ep.get("container_extension", "mp4")
        episode_num = ep.get("episode_num") or 1
        label = "E" + str(episode_num).zfill(2) + " - " + title
        li = xbmcgui.ListItem(label)

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({
                "mode": "export_episode",
                "series_name": series_name,
                "season": season,
                "episode": episode_num,
                "episode_title": title,
                "episode_id": episode_id,
                "ext": ext
            }),
            li,
            False
        )

    xbmcplugin.endOfDirectory(HANDLE)


def search_series():
    keyboard = xbmc.Keyboard("", "Serie suchen")
    keyboard.doModal()

    if not keyboard.isConfirmed():
        return

    search_text = keyboard.getText().strip().lower()
    if not search_text:
        return

    if search_series_via_tmdb(search_text):
        return

    indexed_results = cache_index.search_series(search_text)
    if indexed_results:
        xbmcplugin.setContent(HANDLE, "tvshows")
        for serie in indexed_results:
            name = serie.get("name", "Serie")
            series_id = serie.get("series_id")
            li = xbmcgui.ListItem(name)
            xbmcplugin.addDirectoryItem(HANDLE, build_url({"mode": "series_info", "series_id": series_id, "series_name": name}), li, True)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    allowed_categories = get_allowed_categories()
    if not allowed_categories:
        xbmcgui.Dialog().ok("Suche", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    results = []
    progress = xbmcgui.DialogProgress()
    progress.create("Seriensuche läuft", "Durchsuche ausgewählte Sprachen...")

    for index, cat in enumerate(allowed_categories):
        if progress.iscanceled():
            break

        category_id = cat.get("category_id")
        category_name = cat.get("category_name", "Unbekannt")
        progress.update(int((index + 1) / len(allowed_categories) * 100), category_name)
        series_list = xtream.api("get_series", {"category_id": category_id})

        for serie in series_list:
            name = serie.get("name", "")
            if search_text in name.lower():
                results.append(serie)

    progress.close()

    if not results:
        xbmcgui.Dialog().ok("Suche", "Keine Serien gefunden")
        return

    xbmcplugin.setContent(HANDLE, "tvshows")
    for serie in results:
        add_series_item(serie)
    xbmcplugin.endOfDirectory(HANDLE)


def show_latest(limit=100):
    allowed = get_allowed_categories()
    if not allowed:
        xbmcgui.Dialog().ok("Serien", "Keine Kategorien für die ausgewählten Sprachen gefunden.")
        return

    results = []
    progress = xbmcgui.DialogProgress()
    progress.create("Neue Serien", "Lade aktuelle Serien...")

    for index, cat in enumerate(allowed):
        if progress.iscanceled():
            break
        category_id = cat.get("category_id")
        category_name = cat.get("category_name", "Unbekannt")
        progress.update(int((index + 1) / len(allowed) * 100), category_name)
        for serie in xtream.api("get_series", {"category_id": category_id}):
            serie["category_name_export"] = category_name
            results.append(serie)

    progress.close()
    results = sorted(results, key=lambda x: str(x.get("last_modified", x.get("added", "0"))), reverse=True)[:int(limit)]

    xbmcplugin.setContent(HANDLE, "tvshows")
    for serie in results:
        add_series_item(serie)
    xbmcplugin.endOfDirectory(HANDLE)


def export_episode(series_name, season, episode, episode_title, episode_id, ext):
    stream_url = xtream.series_url(episode_id, ext)
    ok = write_episode(series_name, int(season), int(episode), episode_title, stream_url)

    if ok:
        xbmcgui.Dialog().notification("Episode erstellt", clean_filename(series_name), xbmcgui.NOTIFICATION_INFO, 5000)
        ask_clean_and_scan_after_export()


def export_season(series_id, series_name, season):
    info = xtream.api("get_series_info", {"series_id": series_id})
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}
    season_episodes = get_season_episodes(episodes, season)

    if not season_episodes:
        xbmcgui.Dialog().ok("Staffel", "Keine Episoden in dieser Staffel gefunden")
        return

    export_episode_list(series_name, [(season, ep) for ep in season_episodes], "Exportiere Staffel")


def export_series(series_id, series_name):
    info = xtream.api("get_series_info", {"series_id": series_id})
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}

    if not episodes:
        xbmcgui.Dialog().ok("Serie", "Keine Episoden gefunden")
        return

    flat = []
    for season_num, eps in episodes.items():
        for ep in eps:
            flat.append((season_num, ep))

    export_episode_list(series_name, flat, "Exportiere Serie")


def export_episode_list(series_name, flat, progress_title):
    progress = xbmcgui.DialogProgress()
    progress.create(progress_title, series_name)

    total = len(flat)
    created = 0
    failed = []

    for index, item in enumerate(flat):
        if progress.iscanceled():
            break

        season_num, ep = item
        title = ep.get("title") or ep.get("name") or "Episode"
        episode_id = ep.get("id")
        ext = ep.get("container_extension", "mp4")
        episode_num = ep.get("episode_num") or 1
        label = f"S{int(season_num):02d}E{int(episode_num):02d} - {title}"

        try:
            if not episode_id:
                failed.append(f"{label} - Keine Episode-ID")
                continue

            stream_url = xtream.series_url(episode_id, ext)
            ok = write_episode(series_name, int(season_num), int(episode_num), title, stream_url, show_dialog=False)

            if ok:
                created += 1
            else:
                failed.append(f"{label} - STRM konnte nicht erstellt werden")

        except Exception as e:
            failed.append(f"{label} - {str(e)}")
            xbmc.log(f"[IPTV Addon] Fehler beim Serien-Export: {label} | {str(e)}", xbmc.LOGERROR)
            continue

        progress.update(int((index + 1) / total * 100), label)

    progress.close()
    show_export_result("Export fertig", created, total, failed)

    if created > 0:
        ask_clean_and_scan_after_export()


def show_export_result(title, created, total, failed):
    if failed:
        text = f"Erstellt: {created} von {total}\nFehlerhaft: {len(failed)}\n\n" + "\n".join(failed)
        xbmcgui.Dialog().textviewer("Fehlerhafte Episoden", text)
    else:
        xbmcgui.Dialog().notification(title, f"Alle {created} Episoden erstellt", xbmcgui.NOTIFICATION_INFO, 5000)
