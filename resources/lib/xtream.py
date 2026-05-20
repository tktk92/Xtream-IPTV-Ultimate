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


def validate_credentials(server, username, password):
    server = str(server or "").strip().rstrip("/")
    username = str(username or "").strip()
    password = str(password or "").strip()

    if not server or not username or not password:
        return False, "Server URL, Benutzername und Passwort muessen ausgefuellt sein."

    params = {
        "username": username,
        "password": password,
    }
    url = server + "/player_api.php?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "VLC/3.0.18 LibVLC/3.0.18",
        "Accept": "*/*",
        "Connection": "close",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode("utf-8", errors="ignore")

        payload = json.loads(data)
        user_info = payload.get("user_info", {}) if isinstance(payload, dict) else {}
        status = str(user_info.get("status", "")).lower()
        auth = str(user_info.get("auth", "")).lower()

        if status == "active" or auth in ("1", "true"):
            return True, "Zugangsdaten sind gueltig."

        if status:
            return False, "Zugang ist nicht aktiv: " + status

        return False, "Serverantwort konnte nicht als gueltiger Xtream-Zugang bestaetigt werden."
    except Exception as e:
        xbmc.log("XTREAM LOGIN CHECK ERROR: " + str(e), xbmc.LOGERROR)
        return False, "Loginpruefung fehlgeschlagen: " + str(e)


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
