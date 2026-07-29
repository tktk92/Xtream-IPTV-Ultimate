# -*- coding: utf-8 -*-

import os
import shutil
import json
import glob
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs


from common import HANDLE, build_url
from strm import get_movie_folder, get_series_folder


TVSHOW_PROPERTIES = [
    "title",
    "episode",
    "watchedepisodes",
    "lastplayed",
    "thumbnail",
    "fanart",
    "art",
]

EPISODE_PROPERTIES = [
    "title",
    "showtitle",
    "season",
    "episode",
    "playcount",
    "lastplayed",
    "resume",
    "file",
    "thumbnail",
    "fanart",
    "art",
]


def get_video_database_path():
    database_folder = xbmcvfs.translatePath("special://profile/Database")
    matches = sorted(glob.glob(os.path.join(database_folder, "MyVideos*.db")), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else ""


def json_rpc(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
    }
    if params is not None:
        payload["params"] = params

    response = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(response)
    except Exception:
        return {}


def _special_path(path):
    if not path:
        return ""
    if path.startswith("special://"):
        return path
    return xbmcvfs.translatePath(path)


def _get_art_map(conn, media_type, media_id):
    rows = conn.execute(
        """
        SELECT type, url
        FROM art
        WHERE media_type = ?
          AND media_id = ?
        """,
        (media_type, media_id),
    ).fetchall()
    return dict((row["type"], row["url"]) for row in rows if row["type"] and row["url"])


def get_continue_series_from_database(limit=50):
    try:
        import sqlite3
    except Exception:
        return []

    db_path = get_video_database_path()
    if not db_path:
        return []

    results = []
    try:
        conn = sqlite3.connect("file:" + db_path + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            shows = conn.execute(
                """
                SELECT idShow, c00 AS title, totalCount, watchedcount, lastPlayed, strPath
                FROM tvshow_view
                WHERE COALESCE(totalCount, 0) > 0
                  AND (
                    COALESCE(watchedcount, 0) > 0
                    OR lastPlayed IS NOT NULL
                    OR COALESCE(inProgressCount, 0) > 0
                  )
                  AND COALESCE(watchedcount, 0) < COALESCE(totalCount, 0)
                ORDER BY COALESCE(lastPlayed, '') DESC, c00 COLLATE NOCASE ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

            for show in shows:
                show_art = _get_art_map(conn, "tvshow", show["idShow"])
                episode = conn.execute(
                    """
                    SELECT idEpisode, strTitle, c12 AS season, c13 AS episode, c00 AS title,
                           playCount, lastPlayed, resumeTimeInSeconds, totalTimeInSeconds,
                           strPath, strFileName
                    FROM episode_view
                    WHERE idShow = ?
                      AND COALESCE(resumeTimeInSeconds, 0) > 60
                      AND (
                        COALESCE(totalTimeInSeconds, 0) = 0
                        OR COALESCE(totalTimeInSeconds, 0) - COALESCE(resumeTimeInSeconds, 0) > 60
                      )
                    ORDER BY COALESCE(lastPlayed, '') DESC
                    LIMIT 1
                    """,
                    (show["idShow"],),
                ).fetchone()

                if episode is None:
                    episode = conn.execute(
                        """
                        SELECT idEpisode, strTitle, c12 AS season, c13 AS episode, c00 AS title,
                               playCount, lastPlayed, resumeTimeInSeconds, totalTimeInSeconds,
                               strPath, strFileName
                        FROM episode_view
                        WHERE idShow = ?
                          AND COALESCE(playCount, 0) = 0
                        ORDER BY CAST(c12 AS INTEGER), CAST(c13 AS INTEGER), idEpisode
                        LIMIT 1
                        """,
                        (show["idShow"],),
                    ).fetchone()

                if episode is None:
                    continue

                item = {
                    "tvshowid": show["idShow"],
                    "title": show["title"],
                    "episode": show["totalCount"],
                    "watchedepisodes": show["watchedcount"],
                    "art": show_art,
                    "thumbnail": show_art.get("poster") or show_art.get("thumb") or show_art.get("landscape"),
                    "fanart": show_art.get("fanart") or show_art.get("landscape"),
                    "next_episode": {
                        "episodeid": episode["idEpisode"],
                        "showtitle": episode["strTitle"],
                        "season": episode["season"],
                        "episode": episode["episode"],
                        "title": episode["title"],
                        "file": _special_path((episode["strPath"] or "") + (episode["strFileName"] or "")),
                        "resume": {
                            "position": episode["resumeTimeInSeconds"] or 0,
                            "total": episode["totalTimeInSeconds"] or 0,
                        },
                    },
                }
                results.append(item)
        finally:
            conn.close()
    except Exception as e:
        xbmc.log("[IPTV Addon] Serien fortsetzen DB-Fehler: " + str(e), xbmc.LOGWARNING)
        return []

    return results


def _result_list(data, name):
    result = data.get("result", {}) if isinstance(data, dict) else {}
    items = result.get(name, [])
    return items if isinstance(items, list) else []


def get_in_progress_tvshows(limit=50):
    database_results = get_continue_series_from_database(limit)
    if database_results:
        return database_results

    data = json_rpc(
        "VideoLibrary.GetTVShows",
        {
            "properties": TVSHOW_PROPERTIES,
            "filter": {"field": "inprogress", "operator": "true", "value": ""},
            "sort": {"method": "lastplayed", "order": "descending"},
            "limits": {"start": 0, "end": int(limit)},
        },
    )
    tvshows = _result_list(data, "tvshows")
    if tvshows:
        return tvshows

    data = json_rpc(
        "VideoLibrary.GetTVShows",
        {
            "properties": TVSHOW_PROPERTIES,
            "sort": {"method": "lastplayed", "order": "descending"},
            "limits": {"start": 0, "end": 500},
        },
    )
    fallback = []
    for show in _result_list(data, "tvshows"):
        total = int(show.get("episode") or 0)
        watched = int(show.get("watchedepisodes") or 0)
        has_progress = watched > 0 or bool(show.get("lastplayed"))
        if has_progress and watched < total:
            fallback.append(show)
    return fallback[:int(limit)]


def get_tvshow_episodes(tvshow_id):
    data = json_rpc(
        "VideoLibrary.GetEpisodes",
        {
            "tvshowid": int(tvshow_id),
            "properties": EPISODE_PROPERTIES,
        },
    )
    episodes = _result_list(data, "episodes")
    return sorted(
        episodes,
        key=lambda ep: (
            int(ep.get("season") or 0),
            int(ep.get("episode") or 0),
            int(ep.get("episodeid") or 0),
        ),
    )


def _resume_position(episode):
    resume = episode.get("resume", {}) if isinstance(episode, dict) else {}
    try:
        position = float(resume.get("position") or 0)
        total = float(resume.get("total") or 0)
    except Exception:
        return 0

    if position > 60 and (not total or total - position > 60):
        return int(position)
    return 0


def find_next_episode(tvshow_id):
    episodes = get_tvshow_episodes(tvshow_id)
    if not episodes:
        return None, 0

    resumable = [episode for episode in episodes if _resume_position(episode) > 0]
    if resumable:
        episode = sorted(resumable, key=lambda ep: str(ep.get("lastplayed") or ""), reverse=True)[0]
        return episode, _resume_position(episode)

    for episode in episodes:
        if int(episode.get("playcount") or 0) == 0:
            return episode, 0

    return episodes[-1], 0


def _art_value(item, keys):
    art = item.get("art", {}) if isinstance(item, dict) else {}
    for key in keys:
        value = art.get(key) or item.get(key)
        if value:
            return value
    return ""


def _episode_label(episode):
    if not episode:
        return ""
    season = int(episode.get("season") or 0)
    number = int(episode.get("episode") or 0)
    title = episode.get("title") or "Episode"
    return "S{0:02d}E{1:02d} - {2}".format(season, number, title)


def show_continue_series():
    xbmcplugin.setContent(HANDLE, "tvshows")
    tvshows = get_in_progress_tvshows()
    xbmc.log("[IPTV Addon] Serien fortsetzen: {0} Serien gefunden".format(len(tvshows)), xbmc.LOGINFO)

    if not tvshows:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for show in tvshows:
        tvshow_id = show.get("tvshowid")
        if tvshow_id in (None, ""):
            continue

        next_episode = show.get("next_episode")
        if next_episode:
            _offset = _resume_position(next_episode)
        else:
            next_episode, _offset = find_next_episode(tvshow_id)
        if not next_episode:
            continue

        title = show.get("title") or show.get("label") or "Serie"
        next_label = _episode_label(next_episode)
        file_path = next_episode.get("file") or build_url({"mode": "play_next_tvshow", "tvshowid": tvshow_id})
        xbmc.log("[IPTV Addon] Serien fortsetzen: {0} -> {1}".format(title, next_label), xbmc.LOGINFO)
        li = xbmcgui.ListItem(title)
        li.setProperty("IsPlayable", "true")
        if _offset:
            li.setProperty("StartOffset", str(_offset))
        li.setProperty("TotalEpisodes", str(show.get("episode") or ""))
        li.setProperty("WatchedEpisodes", str(show.get("watchedepisodes") or ""))
        li.setProperty("NextEpisode", next_label)
        li.setArt({
            "thumb": _art_value(show, ["poster", "thumb", "thumbnail"]),
            "poster": _art_value(show, ["poster", "thumb", "thumbnail"]),
            "fanart": _art_value(show, ["fanart"]),
        })
        li.setInfo("video", {
            "title": title,
            "mediatype": "tvshow",
            "plot": next_label,
        })
        li.addContextMenuItems([
            (
                "Serie in Bibliothek öffnen",
                "ActivateWindow(Videos,videodb://tvshows/titles/{0}/,return)".format(tvshow_id),
            )
        ])
        xbmcplugin.addDirectoryItem(
            HANDLE,
            file_path,
            li,
            False,
        )

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE)


def play_next_tvshow(tvshow_id):
    episode, offset = find_next_episode(tvshow_id)
    if not episode:
        xbmcgui.Dialog().ok("Serien fortsetzen", "Keine nächste Folge gefunden.")
        return

    file_path = episode.get("file")
    if not file_path:
        xbmcgui.Dialog().ok("Serien fortsetzen", "Diese Folge hat keinen abspielbaren Pfad.")
        return

    label = _episode_label(episode)
    xbmc.log("[IPTV Addon] Serien fortsetzen Play: {0} | {1}".format(label, file_path), xbmc.LOGINFO)
    li = xbmcgui.ListItem(label, path=file_path)
    li.setProperty("IsPlayable", "true")
    if offset:
        li.setProperty("StartOffset", str(offset))
    li.setArt({
        "thumb": _art_value(episode, ["thumb", "thumbnail"]),
        "fanart": _art_value(episode, ["fanart"]),
    })
    li.setInfo("video", {
        "title": episode.get("title") or label,
        "tvshowtitle": episode.get("showtitle") or "",
        "season": int(episode.get("season") or 0),
        "episode": int(episode.get("episode") or 0),
        "mediatype": "episode",
    })
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def list_dirs(path):
    if not os.path.exists(path):
        return []
    return sorted([x for x in os.listdir(path) if os.path.isdir(os.path.join(path, x))])


def list_strm_files(path):
    if not os.path.exists(path):
        return []
    return sorted([x for x in os.listdir(path) if x.lower().endswith(".strm")])


def count_strm_files(path):
    if not os.path.exists(path):
        return 0

    count = 0
    for root, dirs, files in os.walk(path):
        count += len([name for name in files if name.lower().endswith(".strm")])
    return count


def delete_strm_files_and_empty_dirs(path):
    path = xbmcvfs.translatePath(path)
    if not path:
        return 0

    root_path = os.path.abspath(path)
    if not os.path.isdir(root_path):
        return 0

    removed_files = 0
    for current_root, dirs, files in os.walk(root_path, topdown=False):
        current_abs = os.path.abspath(current_root)
        if os.path.commonpath([root_path, current_abs]) != root_path:
            continue

        for file_name in files:
            if not file_name.lower().endswith(".strm"):
                continue
            file_path = os.path.abspath(os.path.join(current_abs, file_name))
            if os.path.commonpath([root_path, file_path]) != root_path:
                continue
            os.remove(file_path)
            removed_files += 1

        if current_abs != root_path and not os.listdir(current_abs):
            os.rmdir(current_abs)

    return removed_files


def show_series_library():
    base = get_series_folder()
    series_items = list_dirs(base)

    if not series_items:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Serien gefunden")
        return

    for serie in series_items:
        full_path = os.path.join(base, serie)
        li = xbmcgui.ListItem(serie)
        li.addContextMenuItems([
            ("Ganze Serie entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': full_path})})")
        ])
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "library_seasons", "path": full_path}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_library_seasons(path):
    path = xbmcvfs.translatePath(path)
    seasons = list_dirs(path)

    if not seasons:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Staffeln gefunden")
        return

    for season in seasons:
        season_path = os.path.join(path, season)
        li = xbmcgui.ListItem(season)
        li.addContextMenuItems([
            ("Staffel entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': season_path})})")
        ])
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "library_episodes", "path": season_path}),
            li,
            True
        )

    xbmcplugin.endOfDirectory(HANDLE)


def show_library_episodes(path):
    path = xbmcvfs.translatePath(path)
    files = list_strm_files(path)

    if not files:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Folgen gefunden")
        return

    for file_name in files:
        file_path = os.path.join(path, file_name)
        label = file_name[:-5]
        li = xbmcgui.ListItem(label)
        li.addContextMenuItems([
            ("Folge entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': file_path})})")
        ])
        xbmcplugin.addDirectoryItem(HANDLE, file_path, li, False)

    xbmcplugin.endOfDirectory(HANDLE)


def show_movies_library():
    base = get_movie_folder()

    if not os.path.exists(base):
        xbmcgui.Dialog().ok("Bibliothek", "Keine Filme gefunden")
        return

    entries = []
    for root, dirs, files in os.walk(base):
        for file_name in files:
            if file_name.lower().endswith(".strm"):
                entries.append(os.path.join(root, file_name))

    if not entries:
        xbmcgui.Dialog().ok("Bibliothek", "Keine Filme gefunden")
        return

    for file_path in sorted(entries):
        rel = os.path.relpath(file_path, base)
        label = rel[:-5]
        li = xbmcgui.ListItem(label)
        li.addContextMenuItems([
            ("Film entfernen", f"RunPlugin({build_url({'mode': 'delete_library_item', 'path': file_path})})")
        ])
        xbmcplugin.addDirectoryItem(HANDLE, file_path, li, False)

    xbmcplugin.endOfDirectory(HANDLE)


def delete_library_item(path):
    path = xbmcvfs.translatePath(path)

    if not path or not os.path.exists(path):
        xbmcgui.Dialog().ok("Löschen", "Datei oder Ordner nicht gefunden")
        return

    confirm = xbmcgui.Dialog().yesno(
        "Aus Bibliothek entfernen",
        "Möchtest du diesen Eintrag wirklich löschen?\n\n" + path
    )

    if not confirm:
        return

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        xbmcgui.Dialog().notification(
            "Gelöscht",
            "Eintrag wurde entfernt",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        xbmc.executebuiltin("Container.Refresh")

    except Exception as e:
        xbmcgui.Dialog().ok("Fehler", str(e))


def delete_all_streams():
    movie_folder = get_movie_folder()
    series_folder = get_series_folder()
    movie_count = count_strm_files(movie_folder)
    series_count = count_strm_files(series_folder)
    total = movie_count + series_count

    if total == 0:
        xbmcgui.Dialog().ok("Streams löschen", "Keine exportierten Streams gefunden.")
        return

    confirm = xbmcgui.Dialog().yesno(
        "Alle Streams löschen",
        "Möchtest du wirklich alle exportierten Streams löschen?\n\n"
        "Filme: {0}\nSerien: {1}\n\n"
        "Die Addon-Einstellungen und Zugangsdaten bleiben erhalten.".format(movie_count, series_count),
        nolabel="Nein",
        yeslabel="Löschen"
    )

    if not confirm:
        return

    try:
        removed_files = delete_strm_files_and_empty_dirs(movie_folder) + delete_strm_files_and_empty_dirs(series_folder)
        xbmc.executebuiltin("CleanLibrary(video)")
        xbmc.executebuiltin("Container.Refresh")
        xbmcgui.Dialog().notification(
            "Streams gelöscht",
            "{0} Streams entfernt".format(removed_files),
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
        xbmc.log(
            "[IPTV Addon] Alle Streams geloescht: {0} Dateien".format(removed_files),
            xbmc.LOGINFO
        )
    except Exception as e:
        xbmcgui.Dialog().ok("Fehler", str(e))
