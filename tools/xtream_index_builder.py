# -*- coding: utf-8 -*-
"""
Standalone Xtream index builder.

Runs outside Kodi and writes the same index format used by the addon:
xtream_index_<Sprache>.json
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed


INDEX_VERSION = 3
MAX_METADATA_WORKERS = 2
DEFAULT_METADATA_WORKERS = 1
DEFAULT_DELAY_SECONDS = 0.35
DEFAULT_RETRIES = 3

ADDON_ID = "plugin.video.xtream.strm"

LANGUAGE_NAMES = {
    "DE": "Deutsch",
    "GER": "Deutsch",
    "DEU": "Deutsch",
    "AR": "Arabisch",
    "ARA": "Arabisch",
    "EN": "Englisch",
    "ENG": "Englisch",
    "UK": "Englisch",
    "US": "Englisch",
    "FR": "Franzoesisch",
    "ES": "Spanisch",
    "IT": "Italienisch",
    "TR": "Tuerkisch",
    "IN": "Indisch",
    "HI": "Hindi",
    "TA": "Tamil",
    "TAM": "Tamil",
    "RU": "Russisch",
    "AL": "Albanisch",
    "EXYU": "Ex-Yu",
    "YU": "Ex-Yu",
    "MULTI": "Mehrsprachig",
}


def kodi_profile_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "Kodi", "userdata", "addon_data", ADDON_ID)
    return os.path.join(os.path.expanduser("~"), ".kodi", "userdata", "addon_data", ADDON_ID)


def read_kodi_settings(profile_dir):
    path = os.path.join(profile_dir, "settings.xml")
    settings = {}
    if not os.path.exists(path):
        return settings

    try:
        root = ET.parse(path).getroot()
    except Exception:
        return settings

    for item in root.iter("setting"):
        key = item.get("id")
        if not key:
            continue
        value = item.get("value")
        if value is None:
            value = item.text or ""
        settings[key] = value.strip()

    return settings


def get_credential(args, settings, key, env_key):
    value = getattr(args, key, "") or os.environ.get(env_key, "") or settings.get(key, "")
    return value.strip()


def safe_index_name(value):
    safe = str(value or "Andere").strip()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        safe = safe.replace(source, target)
    for char in '<>:"/\\|?* ':
        safe = safe.replace(char, "_")
    return safe or "Andere"


def index_filename(language):
    return "xtream_index_{0}.json".format(safe_index_name(language))


def empty_index(server_url, language):
    return {
        "version": INDEX_VERSION,
        "created_at": time.time(),
        "signature": {
            "server_url": server_url.rstrip("/"),
            "languages": [language],
        },
        "movies": [],
        "series": [],
    }


def extract_language_from_category(category_name):
    if not category_name:
        return "Andere"

    name = category_name.upper()

    for keyword in ["TAMIL", "TAM", "KOLLYWOOD"]:
        if keyword in name:
            return "Tamil"

    for keyword in ["MULTI", "MULTI AUDIO", "MULTI-AUDIO", "MULTIAUDIO", "DUAL AUDIO", "DUAL-AUDIO"]:
        if keyword in name:
            return "Mehrsprachig"

    match = re.search(r"[^A-Z0-9]*([A-Z]{2,5})[^A-Z0-9]+", name)
    if match:
        code = match.group(1)
        if code in LANGUAGE_NAMES:
            return LANGUAGE_NAMES[code]

    if "ARABIC" in name or "ARAB" in name:
        return "Arabisch"
    if "GERMAN" in name or "DEUTSCH" in name:
        return "Deutsch"
    if "ENGLISH" in name:
        return "Englisch"
    if "TURKISH" in name or "TURK" in name:
        return "Tuerkisch"
    if "HINDI" in name or "BOLLYWOOD" in name:
        return "Hindi"
    if "FRENCH" in name:
        return "Franzoesisch"
    if "SPANISH" in name:
        return "Spanisch"
    if "ITALIAN" in name:
        return "Italienisch"

    for code, lang_name in LANGUAGE_NAMES.items():
        if name.startswith(code + " ") or name.startswith(code + "-") or name.startswith(code + "|") or name.startswith(code + "_"):
            return lang_name

    return "Andere"


def request_json(server_url, username, password, action, extra, retries, delay_seconds):
    params = {
        "username": username,
        "password": password,
        "action": action,
    }
    if extra:
        params.update(extra)

    url = server_url.rstrip("/") + "/player_api.php?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "VLC/3.0.18 LibVLC/3.0.18",
        "Accept": "*/*",
        "Connection": "close",
    }

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8", errors="ignore")
            if not raw:
                return []
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt >= retries:
                print("HTTP error for {0}: {1}".format(action, exc.code))
                return []
        except Exception as exc:
            if attempt >= retries:
                print("Request failed for {0}: {1}".format(action, exc))
                return []

        sleep_for = delay_seconds * (2 ** attempt) + 1.0
        print("Retry {0}/{1} for {2} after {3:.1f}s".format(attempt + 1, retries, action, sleep_for))
        time.sleep(sleep_for)

    return []


def first_value(data, keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def get_id_key(value):
    if value is None:
        return ""
    return str(value)


def load_old_metadata(path):
    if not os.path.exists(path):
        return {}, {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}, {}

    movies = {}
    for item in data.get("movies", []):
        if item.get("tmdb_id") or item.get("metadata_checked_at"):
            movies[get_id_key(item.get("stream_id"))] = item

    series = {}
    for item in data.get("series", []):
        if item.get("tmdb_id") or item.get("metadata_checked_at"):
            series[get_id_key(item.get("series_id"))] = item

    return movies, series


def write_index_checkpoint(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception as exc:
        print("Checkpoint failed: {0}".format(exc))


def copy_metadata(target, old_item):
    if not old_item:
        return False
    copied = False
    for field in ["tmdb_id", "metadata_checked_at"]:
        value = old_item.get(field)
        if value not in (None, ""):
            target[field] = value
            copied = True
    return copied


def fetch_movie_metadata(client, stream_id):
    payload = client("get_vod_info", {"vod_id": stream_id})
    info = payload.get("info", {}) if isinstance(payload, dict) else {}
    return {
        "tmdb_id": first_value(info, ["tmdb_id", "tmdb"]),
        "metadata_checked_at": int(time.time()),
    }


def fetch_series_metadata(client, series_id):
    payload = client("get_series_info", {"series_id": series_id})
    info = payload.get("info", {}) if isinstance(payload, dict) else {}
    return {
        "tmdb_id": first_value(info, ["tmdb_id", "tmdb"]),
        "metadata_checked_at": int(time.time()),
    }


def enrich_missing(items, id_field, old_metadata, fetch_func, workers, delay_seconds, checkpoint=None):
    pending = []
    fetched = 0

    for item in items:
        if copy_metadata(item, old_metadata.get(get_id_key(item.get(id_field)))):
            continue
        pending.append(item)

    if not pending:
        return 0

    print("Metadata missing: {0}".format(len(pending)))

    def task(item):
        time.sleep(delay_seconds)
        return item, fetch_func(item.get(id_field))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(task, item) for item in pending]
        for index, future in enumerate(as_completed(futures), 1):
            item, metadata = future.result()
            copy_metadata(item, metadata)
            fetched += 1
            if checkpoint:
                checkpoint()
            if index % 50 == 0 or index == len(pending):
                print("Metadata checked: {0}/{1}".format(index, len(pending)))

    return fetched


def build_language_index(language, args, server_url, username, password, output_dir):
    output_path = os.path.join(output_dir, index_filename(language))
    old_movie_metadata, old_series_metadata = load_old_metadata(output_path)

    def client(action, extra=None):
        return request_json(server_url, username, password, action, extra, args.retries, args.delay)

    data = empty_index(server_url, language)
    print("Building {0} -> {1}".format(language, output_path))

    movie_categories = client("get_vod_categories") or []
    series_categories = client("get_series_categories") or []

    for category in movie_categories:
        category_name = category.get("category_name", "")
        if extract_language_from_category(category_name) != language:
            continue

        print("Movies: {0}".format(category_name))
        movies = client("get_vod_streams", {"category_id": category.get("category_id")}) or []
        category_items = []
        for movie in movies:
            category_items.append({
                "name": movie.get("name", ""),
                "stream_id": movie.get("stream_id"),
                "category_name": category_name,
                "container_extension": movie.get("container_extension", "mp4"),
                "added": movie.get("added"),
            })
        data["movies"].extend(category_items)
        write_index_checkpoint(output_path, data)

    for category in series_categories:
        category_name = category.get("category_name", "")
        if extract_language_from_category(category_name) != language:
            continue

        print("Series: {0}".format(category_name))
        series = client("get_series", {"category_id": category.get("category_id")}) or []
        category_items = []
        for serie in series:
            category_items.append({
                "name": serie.get("name", ""),
                "series_id": serie.get("series_id"),
                "category_name": category_name,
                "last_modified": serie.get("last_modified"),
                "added": serie.get("added"),
            })
        data["series"].extend(category_items)
        write_index_checkpoint(output_path, data)

    if not args.skip_metadata:
        print("Movies found: {0}".format(len(data["movies"])))
        enrich_missing(
            data["movies"],
            "stream_id",
            old_movie_metadata,
            lambda item_id: fetch_movie_metadata(client, item_id),
            args.metadata_workers,
            args.delay,
            lambda: write_index_checkpoint(output_path, data),
        )

        print("Series found: {0}".format(len(data["series"])))
        enrich_missing(
            data["series"],
            "series_id",
            old_series_metadata,
            lambda item_id: fetch_series_metadata(client, item_id),
            args.metadata_workers,
            args.delay,
            lambda: write_index_checkpoint(output_path, data),
        )

    write_index_checkpoint(output_path, data)

    print("Done: {0} movies, {1} series".format(len(data["movies"]), len(data["series"])))
    return output_path


def parse_languages(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def build_parser():
    parser = argparse.ArgumentParser(description="Build Xtream index files outside Kodi.")
    parser.add_argument("--languages", required=True, help="Comma separated languages, e.g. Deutsch,Tamil")
    parser.add_argument("--server-url", default="", help="Xtream server URL. Default: Kodi settings or XTREAM_SERVER_URL.")
    parser.add_argument("--username", default="", help="Xtream username. Default: Kodi settings or XTREAM_USERNAME.")
    parser.add_argument("--password", default="", help="Xtream password. Default: Kodi settings or XTREAM_PASSWORD.")
    parser.add_argument("--output-dir", default="", help="Default: Kodi userdata addon_data folder.")
    parser.add_argument("--metadata-workers", type=int, default=DEFAULT_METADATA_WORKERS, help="1 or 2. Default: 1.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Delay between detail requests. Default: 0.35.")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retries for temporary server errors.")
    parser.add_argument("--skip-metadata", action="store_true", help="Build basic index without TMDb ids.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.metadata_workers = max(1, min(MAX_METADATA_WORKERS, int(args.metadata_workers or 1)))
    args.delay = max(0.1, float(args.delay or DEFAULT_DELAY_SECONDS))
    args.retries = max(0, int(args.retries or DEFAULT_RETRIES))

    profile_dir = kodi_profile_dir()
    settings = read_kodi_settings(profile_dir)
    server_url = get_credential(args, settings, "server_url", "XTREAM_SERVER_URL")
    username = get_credential(args, settings, "username", "XTREAM_USERNAME")
    password = get_credential(args, settings, "password", "XTREAM_PASSWORD")
    output_dir = args.output_dir.strip() or profile_dir

    if not server_url or not username or not password:
        print("Missing credentials. Use Kodi settings or pass --server-url --username --password.")
        return 2

    languages = parse_languages(args.languages)
    if not languages:
        print("No languages selected.")
        return 2

    print("Output folder: {0}".format(output_dir))
    print("Metadata workers: {0} (maximum allowed: {1})".format(args.metadata_workers, MAX_METADATA_WORKERS))

    written = []
    for language in languages:
        written.append(build_language_index(language, args, server_url, username, password, output_dir))

    print("Written files:")
    for path in written:
        print("  {0}".format(path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
