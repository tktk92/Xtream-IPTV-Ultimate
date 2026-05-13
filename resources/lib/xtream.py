# -*- coding: utf-8 -*-

import json
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
from common import get_setting


def api(action, extra=None, show_error=True):
    server = get_setting("server_url").rstrip("/")
    username = get_setting("username")
    password = get_setting("password")

    params = {
        "username": username,
        "password": password,
        "action": action
    }

    if extra:
        params.update(extra)

    url = server + "/player_api.php?" + urllib.parse.urlencode(params)

    headers = {
        "User-Agent": "VLC/3.0.18 LibVLC/3.0.18",
        "Accept": "*/*",
        "Connection": "close"
    }

    xbmc.log("XTREAM URL: " + url, xbmc.LOGINFO)

    try:
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read().decode("utf-8", errors="ignore")
            xbmc.log("XTREAM RESPONSE LENGTH: " + str(len(data)), xbmc.LOGINFO)

            if not data:
                raise Exception("Leere Serverantwort")

            return json.loads(data)

    except Exception as e:
        xbmc.log("XTREAM ERROR: " + str(e), xbmc.LOGERROR)
        if show_error:
            xbmcgui.Dialog().ok("Xtream Fehler", str(e))
        return []


def movie_url(stream_id, extension="mp4"):
    server = get_setting("server_url").rstrip("/")
    username = get_setting("username")
    password = get_setting("password")
    return f"{server}/movie/{username}/{password}/{stream_id}.{extension}"


def series_url(episode_id, extension="mp4"):
    server = get_setting("server_url").rstrip("/")
    username = get_setting("username")
    password = get_setting("password")
    return f"{server}/series/{username}/{password}/{episode_id}.{extension}"


def live_url(stream_id, extension="ts"):
    server = get_setting("server_url").rstrip("/")
    username = get_setting("username")
    password = get_setting("password")
    return f"{server}/live/{username}/{password}/{stream_id}.{extension}"
