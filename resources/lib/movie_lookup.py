# -*- coding: utf-8 -*-

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import xbmc
import xbmcgui
from common import ADDON
from strm import clean_filename

TMDB_API_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_MOVIE_DETAILS_URL = "https://api.themoviedb.org/3/movie/{0}"
TMDB_TV_DETAILS_URL = "https://api.themoviedb.org/3/tv/{0}"
TMDB_TV_SEARCH_URL = "https://api.themoviedb.org/3/search/tv"
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"

TMDB_MOVIE_ID_CACHE = {}
TMDB_TV_ID_CACHE = {}

NOISE_WORDS = [
    "KINO", "CINEMA", "CAM", "CAMRIP", "CAM VERSION", "CAM-VERSION", "HDCAM", "HD CAM",
    "TS", "TELESYNC", "HDTS", "DVDSCR", "SCREENER",
    "GERMAN", "GER", "DEUTSCH", "DE", "ENG", "ENGLISH", "EN", "TAMIL", "TAM", "TA", "MULTI", "MULTIAUDIO",
    "DUAL AUDIO", "DUAL-AUDIO", "SUBBED", "DUBBED",
    "1080P", "720P", "2160P", "4K", "UHD", "HD", "HDR", "HDR10", "DOLBY", "ATMOS",
    "WEB-DL", "WEBDL", "WEBRIP", "WEB", "BLURAY", "BDRIP", "BRRIP", "HDRIP",
    "X264", "X265", "H264", "H265", "HEVC", "AAC", "AC3", "DTS"
]


def get_tmdb_api_key():
    try:
        return ADDON.getSetting("tmdb_api_key").strip()
    except Exception:
        return ""


def prepare_movie_search_title(title):
    if not title:
        return ""

    text = str(title)
    text = text.replace("\\r", " ").replace("\\n", " ").replace("\r", " ").replace("\n", " ")
    text = text.replace("â”ƒ", " ").replace("┃", " ").replace("|", " ").replace("│", " ")

    # Alles nach alternativen Titeln in eckigen Klammern entfernen, z.B. [ The Devil Wears Prada 2
    text = re.sub(r"\[\s*the\s+[^\]]*$", " ", text, flags=re.IGNORECASE)

    # Inhalte in []/()/{} entfernen, ausser reine Jahreszahl merken wir später separat über TMDb.
    text = re.sub(r"[\[\{][^\]\}]*[\]\}]", " ", text)
    text = re.sub(r"\((?!\d{4}\))[^)]*\)", " ", text)

    # Jahreszahl am Ende entfernen, damit TMDb freier suchen kann.
    text = re.sub(r"\(\s*(19|20)\d{2}\s*\)", " ", text)
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)

    for word in NOISE_WORDS:
        text = re.sub(r"\b" + re.escape(word) + r"\b", " ", text, flags=re.IGNORECASE)

    # Häufige Trenner säubern
    text = text.replace("|", " ").replace("_", " ").replace(".", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -_:;.,[](){}")

    return clean_filename(text)


def search_tmdb_movie(query, language="de-DE"):
    api_key = get_tmdb_api_key()
    if not api_key or not query:
        return []

    params = {
        "api_key": api_key,
        "query": query,
        "language": language,
        "include_adult": "false"
    }

    url = TMDB_API_URL + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Xtream IPTV Ultimate"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            payload = json.loads(data)
            return payload.get("results", []) or []
    except Exception as e:
        xbmc.log("[IPTV Addon] TMDb Suche fehlgeschlagen: " + str(e), xbmc.LOGERROR)
        return []


def get_tmdb_movie_by_id(tmdb_id, language="de-DE"):
    api_key = get_tmdb_api_key()
    tmdb_id = str(tmdb_id or "").strip()
    if not api_key or not tmdb_id:
        return None

    cache_key = (tmdb_id, language)
    if cache_key in TMDB_MOVIE_ID_CACHE:
        return TMDB_MOVIE_ID_CACHE[cache_key]

    params = {
        "api_key": api_key,
        "language": language
    }
    url = TMDB_MOVIE_DETAILS_URL.format(urllib.parse.quote(tmdb_id)) + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Xtream IPTV Ultimate"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            payload = json.loads(data)
            TMDB_MOVIE_ID_CACHE[cache_key] = payload
            return payload
    except Exception as e:
        xbmc.log("[IPTV Addon] TMDb Film-ID Suche fehlgeschlagen: " + str(tmdb_id) + " | " + str(e), xbmc.LOGERROR)
        TMDB_MOVIE_ID_CACHE[cache_key] = None
        return None


def search_tmdb_tv(query, language="de-DE"):
    api_key = get_tmdb_api_key()
    if not api_key or not query:
        return []

    params = {
        "api_key": api_key,
        "query": query,
        "language": language,
        "include_adult": "false"
    }

    url = TMDB_TV_SEARCH_URL + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Xtream IPTV Ultimate"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            payload = json.loads(data)
            return payload.get("results", []) or []
    except Exception as e:
        xbmc.log("[IPTV Addon] TMDb TV-Suche fehlgeschlagen: " + str(e), xbmc.LOGERROR)
        return []


def get_tmdb_tv_by_id(tmdb_id, language="de-DE"):
    api_key = get_tmdb_api_key()
    tmdb_id = str(tmdb_id or "").strip()
    if not api_key or not tmdb_id:
        return None

    cache_key = (tmdb_id, language)
    if cache_key in TMDB_TV_ID_CACHE:
        return TMDB_TV_ID_CACHE[cache_key]

    params = {
        "api_key": api_key,
        "language": language
    }
    url = TMDB_TV_DETAILS_URL.format(urllib.parse.quote(tmdb_id)) + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Xtream IPTV Ultimate"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            payload = json.loads(data)
            TMDB_TV_ID_CACHE[cache_key] = payload
            return payload
    except Exception as e:
        xbmc.log("[IPTV Addon] TMDb Serien-ID Suche fehlgeschlagen: " + str(tmdb_id) + " | " + str(e), xbmc.LOGERROR)
        TMDB_TV_ID_CACHE[cache_key] = None
        return None


def search_tmdb_movie_fuzzy(query, limit=8):
    results = search_tmdb_movie(query, "de-DE")
    if not results:
        results = search_tmdb_movie(query, "en-US")
    return results[:int(limit)]


def search_tmdb_tv_fuzzy(query, limit=8):
    results = search_tmdb_tv(query, "de-DE")
    if not results:
        results = search_tmdb_tv(query, "en-US")
    return results[:int(limit)]


def format_tmdb_search_label(item, media_type="movie"):
    if media_type == "tv":
        title = item.get("name") or item.get("original_name") or ""
        date = item.get("first_air_date") or ""
    else:
        title = item.get("title") or item.get("original_title") or ""
        date = item.get("release_date") or ""

    year = date[:4] if len(date) >= 4 else ""
    if year:
        return "{0} ({1})".format(title, year)
    return title


def format_tmdb_title(movie):
    title = movie.get("title") or movie.get("name") or movie.get("original_title") or ""
    date = movie.get("release_date") or ""
    year = date[:4] if len(date) >= 4 else ""

    if year:
        return clean_filename(f"{title} ({year})")

    return clean_filename(title)


def title_from_tmdb_id(tmdb_id, fallback_name=""):
    movie = get_tmdb_movie_by_id(tmdb_id, "de-DE")
    if not movie:
        movie = get_tmdb_movie_by_id(tmdb_id, "en-US")

    if movie:
        title = movie.get("title") or movie.get("original_title") or fallback_name
        date = movie.get("release_date") or ""
        year = date[:4] if len(date) >= 4 else ""
        if year:
            return clean_filename("{0} ({1})".format(title, year))
        if title:
            return clean_filename(title)

    return clean_filename(prepare_movie_search_title(fallback_name) or fallback_name)


def tv_title_from_tmdb_id(tmdb_id, fallback_name=""):
    serie = get_tmdb_tv_by_id(tmdb_id, "de-DE")
    if not serie:
        serie = get_tmdb_tv_by_id(tmdb_id, "en-US")

    if serie:
        title = serie.get("name") or serie.get("original_name") or fallback_name
        if title:
            return clean_filename(title)

    return clean_filename(fallback_name)

def get_top_matches(original_title, limit=5):
    query = prepare_movie_search_title(original_title)

    if not query:
        return [], ""

    results = search_tmdb_movie(query, "de-DE")

    if not results:
        results = search_tmdb_movie(query, "en-US")

    return results[:limit], query


def get_best_match(original_title):
    query = prepare_movie_search_title(original_title)
    if not query:
        return None, ""

    results = search_tmdb_movie(query, "de-DE")

    if not results:
        # Fallback auf Englisch, falls deutscher Titel nicht gefunden wird.
        results = search_tmdb_movie(query, "en-US")

    if not results:
        return None, query

    # TMDb sortiert bereits grob nach Relevanz/Popularität.
    return results[0], query


def choose_movie_title(original_title):
    fallback_title = clean_filename(prepare_movie_search_title(original_title) or original_title)
    api_key = get_tmdb_api_key()

    if not api_key:
        xbmcgui.Dialog().ok(
            "TMDb API Key fehlt",
            "Bitte zuerst in den Addon-Einstellungen den TMDb API Key eintragen.\n\n"
            "Der Film wird vorerst nur lokal bereinigt gespeichert."
        )
        return fallback_title

    results, search_title = get_top_matches(original_title, 5)

    if not results:
        manual = xbmcgui.Dialog().yesno(
            "Kein Film gefunden",
            f"Für '{search_title}' wurde kein Treffer gefunden.\n\nMöchtest du den Namen manuell eingeben?"
        )

        if manual:
            keyboard = xbmc.Keyboard(fallback_title, "Filmtitel eingeben")
            keyboard.doModal()

            if keyboard.isConfirmed() and keyboard.getText().strip():
                return clean_filename(keyboard.getText().strip())

        return fallback_title

    options = []

    for movie in results:
        title = format_tmdb_title(movie)
        original = movie.get("original_title") or ""
        date = movie.get("release_date") or ""
        overview = movie.get("overview") or ""

        if len(overview) > 80:
            overview = overview[:80].rstrip() + "..."

        label = title

        if original and original not in title:
            label += f" / {original}"

        if overview:
            label += f" - {overview}"

        options.append(label)

    options.append("Manuell eingeben")
    options.append("Originalname verwenden")

    index = xbmcgui.Dialog().select(
        "Filmtitel auswählen",
        options
    )

    if index == -1:
        return fallback_title

    if index < len(results):
        return format_tmdb_title(results[index])

    selected_option = options[index]

    if selected_option == "Manuell eingeben":
        keyboard = xbmc.Keyboard(fallback_title, "Filmtitel eingeben")
        keyboard.doModal()

        if keyboard.isConfirmed() and keyboard.getText().strip():
            return clean_filename(keyboard.getText().strip())

        return fallback_title

    return fallback_title
    fallback_title = clean_filename(prepare_movie_search_title(original_title) or original_title)
    api_key = get_tmdb_api_key()

    if not api_key:
        xbmcgui.Dialog().ok(
            "TMDb API Key fehlt",
            "Bitte zuerst in den Addon-Einstellungen den TMDb API Key eintragen.\n\n"
            "Der Film wird vorerst nur lokal bereinigt gespeichert."
        )
        return fallback_title

    match, search_title = get_best_match(original_title)

    if not match:
        manual = xbmcgui.Dialog().yesno(
            "Kein Film gefunden",
            f"Für '{search_title}' wurde kein Treffer gefunden.\n\nMöchtest du den Namen manuell eingeben?"
        )
        if manual:
            keyboard = xbmc.Keyboard(fallback_title, "Filmtitel eingeben")
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText().strip():
                return clean_filename(keyboard.getText().strip())
        return fallback_title

    suggested = format_tmdb_title(match)
    overview = match.get("overview") or ""
    if len(overview) > 220:
        overview = overview[:220].rstrip() + "..."

    message = (
        f"Vorschlag:\n{suggested}\n\n"
        f"Originalname:\n{original_title}\n\n"
        f"Suchtext:\n{search_title}"
    )

    if overview:
        message += "\n\n" + overview

    use_suggestion = xbmcgui.Dialog().yesno(
        "Filmtitel gefunden",
        message,
        nolabel="Nein / manuell",
        yeslabel="Ja verwenden"
    )

    if use_suggestion:
        return suggested

    keyboard = xbmc.Keyboard(fallback_title, "Filmtitel eingeben")
    keyboard.doModal()

    if keyboard.isConfirmed() and keyboard.getText().strip():
        return clean_filename(keyboard.getText().strip())

    return fallback_title


def auto_movie_title(original_title):
    """Für Massenexport ohne Dialog: nutzt TMDb, fällt sonst auf lokale Bereinigung zurück."""
    fallback_title = clean_filename(prepare_movie_search_title(original_title) or original_title)
    match, _query = get_best_match(original_title)
    if match:
        return format_tmdb_title(match)
    return fallback_title


def get_movie_metadata(original_title):
    match, query = get_best_match(original_title)
    if not match:
        return None

    release_date = match.get("release_date") or ""
    title = match.get("title") or match.get("original_title") or original_title

    return {
        "tmdb_id": match.get("id"),
        "tmdb_title": title,
        "tmdb_original_title": match.get("original_title") or "",
        "release_date": release_date,
        "release_year": release_date[:4] if len(release_date) >= 4 else "",
        "search_query": query
    }


def discover_recent_movies(
    original_language_codes,
    months=3,
    max_pages=5,
    language="de-DE",
    sort_by="popularity.desc",
    vote_count_gte=10,
    release_types="2|3",
    region="DE"
):
    api_key = get_tmdb_api_key()
    if not api_key:
        return []

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=int(months) * 31)
    results = []
    seen_ids = set()

    for language_code in original_language_codes:
        for page in range(1, int(max_pages) + 1):
            params = {
                "api_key": api_key,
                "language": language,
                "include_adult": "false",
                "include_video": "false",
                "primary_release_date.gte": start_date.isoformat(),
                "primary_release_date.lte": today.isoformat(),
                "sort_by": sort_by,
                "page": page
            }

            if vote_count_gte:
                params["vote_count.gte"] = vote_count_gte
            if release_types:
                params["with_release_type"] = release_types
            if region:
                params["region"] = region
            if language_code:
                params["with_original_language"] = language_code

            url = TMDB_DISCOVER_URL + "?" + urllib.parse.urlencode(params)

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Xtream IPTV Ultimate"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception as e:
                xbmc.log("[IPTV Addon] TMDb Discover fehlgeschlagen: " + str(e), xbmc.LOGERROR)
                break

            page_results = payload.get("results", []) or []
            for movie in page_results:
                movie_id = movie.get("id")
                if movie_id in seen_ids:
                    continue
                seen_ids.add(movie_id)
                results.append(movie)

            if page >= int(payload.get("total_pages", page)):
                break

    return sorted(results, key=lambda item: item.get("release_date", ""), reverse=True)
