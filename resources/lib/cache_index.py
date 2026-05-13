
# -*- coding: utf-8 -*-
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import xbmcgui
import xbmcvfs
import xtream
from common import ADDON, ADDON_PROFILE, get_setting
from config import get_selected_languages
from language_filter import extract_language_from_category

LEGACY_INDEX_FILE = os.path.join(ADDON_PROFILE, "xtream_index.json")
BUNDLED_INDEX_FOLDER = os.path.join(ADDON.getAddonInfo("path"), "resources", "data")
INDEX_VERSION = 3
INDEX_MAX_AGE_SECONDS = 24 * 60 * 60
METADATA_WORKERS = 2
METADATA_RETRIES = 2
METADATA_RETRY_DELAY_SECONDS = 3

MOVIE_METADATA_FIELDS = ["tmdb_id", "metadata_checked_at"]

SERIES_METADATA_FIELDS = ["tmdb_id", "metadata_checked_at"]


def empty_index():
    return {
        "version": INDEX_VERSION,
        "created_at": 0,
        "signature": {},
        "movies": [],
        "series": []
    }


def get_index_path(languages=None):
    return xbmcvfs.translatePath(os.path.join(ADDON_PROFILE, get_index_filename(languages)))


def get_index_filename(languages=None):
    selected_languages = sorted(languages if languages is not None else get_selected_languages())
    if not selected_languages:
        return "xtream_index_all.json"

    safe_parts = [safe_index_name(language) for language in selected_languages]
    return "xtream_index_" + "_".join(safe_parts) + ".json"


def get_selected_index_languages():
    return sorted(get_selected_languages())


def get_index_language_sets():
    selected_languages = get_selected_index_languages()
    if not selected_languages:
        return [[]]
    return [[language] for language in selected_languages]


def safe_index_name(value):
    safe = str(value or "Andere").strip()
    for char in '<>:"/\\|?* ':
        safe = safe.replace(char, "_")
    return safe or "Andere"


def get_legacy_index_path():
    return xbmcvfs.translatePath(LEGACY_INDEX_FILE)


def get_bundled_index_paths(languages=None):
    language_path = xbmcvfs.translatePath(os.path.join(BUNDLED_INDEX_FOLDER, get_index_filename(languages)))
    return [language_path]


def load_index_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


def index_matches_signature(data, languages=None):
    if not isinstance(data, dict):
        return False
    return data.get("version") == INDEX_VERSION and normalize_signature(data.get("signature")) == get_signature(languages)


def normalize_signature(signature):
    signature = signature if isinstance(signature, dict) else {}
    return {
        "server_url": str(signature.get("server_url") or "").rstrip("/"),
        "languages": sorted(signature.get("languages") or [])
    }


def copy_index_file_if_matching(source, target, languages=None):
    if not os.path.exists(source):
        return False

    data = load_index_file(source)
    if not index_matches_signature(data, languages):
        return False

    try:
        write_index_file(target, data)
        return True
    except Exception:
        return False


def seed_index_file(languages=None):
    target = get_index_path(languages)
    if os.path.exists(target):
        return False

    if copy_index_file_if_matching(get_legacy_index_path(), target, languages):
        return True

    for bundled_path in get_bundled_index_paths(languages):
        if copy_index_file_if_matching(bundled_path, target, languages):
            return True

    return False


def normalize_index_data(data):
    if not isinstance(data, dict):
        return empty_index()
    data.setdefault("movies", [])
    data.setdefault("series", [])
    data.setdefault("version", 1)
    data.setdefault("created_at", 0)
    data.setdefault("signature", {})
    return data


def read_index_for_languages(languages):
    path = get_index_path(languages)
    seed_index_file(languages)
    if not os.path.exists(path):
        data = empty_index()
        data["signature"] = get_signature(languages)
        return data

    return normalize_index_data(load_index_file(path))


def merge_language_indexes(language_sets):
    merged = empty_index()
    merged["signature"] = get_signature()
    created_times = []
    all_current = True

    for language_set in language_sets:
        data = read_index_for_languages(language_set)
        if not index_matches_signature(data, language_set):
            all_current = False

        if not data.get("movies") and not data.get("series"):
            all_current = False

        if data.get("created_at"):
            created_times.append(float(data.get("created_at") or 0))

        merged["movies"].extend(data.get("movies", []))
        merged["series"].extend(data.get("series", []))

    merged["created_at"] = min(created_times) if created_times and all_current else 0
    return merged


def get_index():
    language_sets = get_index_language_sets()
    if len(language_sets) > 1:
        return merge_language_indexes(language_sets)

    path = get_index_path(language_sets[0])
    seed_index_file(language_sets[0])
    if not os.path.exists(path):
        return empty_index()
    return normalize_index_data(load_index_file(path))


def save_index(data):
    language_sets = get_index_language_sets()
    if len(language_sets) > 1:
        save_index_by_language(data, [language_set[0] for language_set in language_sets])
        return

    path = get_index_path(language_sets[0])
    write_index_file(path, data)


def write_index_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_index_by_language(data, languages):
    created_at = data.get("created_at") or time.time()

    for language in languages:
        language_data = empty_index()
        language_data["created_at"] = created_at
        language_data["signature"] = get_signature([language])

        for movie in data.get("movies", []):
            if extract_language_from_category(movie.get("category_name", "")) == language:
                language_data["movies"].append(movie)

        for serie in data.get("series", []):
            if extract_language_from_category(serie.get("category_name", "")) == language:
                language_data["series"].append(serie)

        path = get_index_path([language])
        write_index_file(path, language_data)


def save_existing_index(data):
    data["version"] = INDEX_VERSION
    data["created_at"] = time.time()
    data["signature"] = get_signature()
    save_index(data)


def get_signature(languages=None):
    return {
        "server_url": get_setting("server_url").rstrip("/"),
        "languages": sorted(languages if languages is not None else get_selected_languages())
    }


def has_credentials():
    server = get_setting("server_url").strip()
    username = get_setting("username").strip()
    password = get_setting("password").strip()
    return bool(server and username and password and "example.com" not in server)


def is_index_current(data):
    if data.get("version") != INDEX_VERSION:
        return False
    if normalize_signature(data.get("signature")) != get_signature():
        return False
    if not data.get("movies") and not data.get("series"):
        return False
    created_at = float(data.get("created_at") or 0)
    return (time.time() - created_at) < INDEX_MAX_AGE_SECONDS


def get_index_stats():
    data = get_index()
    movies_with_tmdb = len([m for m in data.get("movies", []) if m.get("tmdb_id")])
    series_with_tmdb = len([s for s in data.get("series", []) if s.get("tmdb_id")])
    filenames = [get_index_filename(language_set) for language_set in get_index_language_sets()]
    return {
        "movies": len(data.get("movies", [])),
        "series": len(data.get("series", [])),
        "movies_with_tmdb": movies_with_tmdb,
        "series_with_tmdb": series_with_tmdb,
        "created_at": data.get("created_at", 0),
        "current": is_index_current(data),
        "filename": ", ".join(filenames),
        "languages": ", ".join(get_signature().get("languages") or ["Alle"])
    }


def get_id_key(value):
    if value is None:
        return ""
    return str(value)


def copy_metadata(target, source, fields):
    if not source:
        return False

    copied = False
    for field in fields:
        value = source.get(field)
        if value not in (None, ""):
            target[field] = value
            copied = True

    return copied


def has_metadata(item):
    return bool(item.get("metadata_checked_at") or item.get("tmdb_id"))


def get_old_movie_metadata_map(old_index):
    result = {}
    for movie in old_index.get("movies", []):
        key = get_id_key(movie.get("stream_id"))
        if key and has_metadata(movie):
            result[key] = movie
    return result


def get_old_series_metadata_map(old_index):
    result = {}
    for serie in old_index.get("series", []):
        key = get_id_key(serie.get("series_id"))
        if key and has_metadata(serie):
            result[key] = serie
    return result


def first_value(data, keys, default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def fetch_movie_metadata(stream_id):
    if not stream_id:
        return {}

    payload = fetch_metadata_payload("get_vod_info", {"vod_id": stream_id})
    if not payload:
        return {}
    info = payload.get("info", {}) if isinstance(payload, dict) else {}

    return {
        "tmdb_id": first_value(info, ["tmdb_id", "tmdb"]),
        "metadata_checked_at": int(time.time())
    }


def fetch_series_metadata(series_id):
    if not series_id:
        return {}

    payload = fetch_metadata_payload("get_series_info", {"series_id": series_id})
    if not payload:
        return {}
    info = payload.get("info", {}) if isinstance(payload, dict) else {}

    return {
        "tmdb_id": first_value(info, ["tmdb_id", "tmdb"]),
        "metadata_checked_at": int(time.time())
    }


def fetch_metadata_payload(action, extra):
    for attempt in range(METADATA_RETRIES + 1):
        payload = xtream.api(action, extra, show_error=False)
        if payload:
            return payload
        if attempt < METADATA_RETRIES:
            time.sleep(METADATA_RETRY_DELAY_SECONDS * (attempt + 1))
    return {}


def checkpoint_save_index(data):
    try:
        save_index(data)
    except Exception:
        pass


def checkpoint_save_existing_index(data):
    try:
        save_existing_index(data)
    except Exception:
        pass


def enrich_items_with_metadata(items, old_metadata, id_field, fields, fetch_func, progress=None, label="Infos", checkpoint=None):
    pending = []
    new_count = 0

    for item in items:
        if has_metadata(item):
            continue
        key = get_id_key(item.get(id_field))
        if copy_metadata(item, old_metadata.get(key), fields):
            continue
        pending.append(item)

    if not pending:
        return 0, False

    canceled = False
    completed = 0
    total = len(pending)

    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as executor:
        futures = {
            executor.submit(fetch_func, item.get(id_field)): item
            for item in pending
        }

        for future in as_completed(futures):
            item = futures[future]

            if progress and progress.iscanceled():
                canceled = True
                for pending_future in futures:
                    pending_future.cancel()
                break

            try:
                metadata = future.result()
            except Exception:
                metadata = {"metadata_checked_at": int(time.time())}

            if copy_metadata(item, metadata, fields):
                new_count += 1

            if checkpoint:
                checkpoint()

            completed += 1
            if progress and total:
                name = item.get("name", "")
                progress.update(int(completed / total * 100), "{0}: {1}".format(label, name))

    return new_count, canceled


def rebuild_index(show_progress=True, notify=True):
    if not has_credentials():
        if notify:
            xbmcgui.Dialog().ok("Index", "Bitte zuerst Xtream Zugangsdaten eintragen.")
        return False

    selected_languages = get_selected_languages()
    old_index = get_index()
    old_movie_metadata = get_old_movie_metadata_map(old_index)
    old_series_metadata = get_old_series_metadata_map(old_index)
    new_movie_metadata_count = 0
    new_series_metadata_count = 0
    data = empty_index()
    data["created_at"] = time.time()
    data["signature"] = get_signature()

    progress = xbmcgui.DialogProgress() if show_progress else None
    if progress:
        progress.create("Index", "Lade Kategorien...")

    canceled = False

    movie_categories = xtream.api("get_vod_categories") or []
    series_categories = xtream.api("get_series_categories") or []
    total = len(movie_categories) + len(series_categories)
    done = 0

    for cat in movie_categories:
        if progress and progress.iscanceled():
            canceled = True
            break

        cname = cat.get("category_name","")
        lang = extract_language_from_category(cname)
        if selected_languages and lang not in selected_languages:
            done += 1
            continue

        cid = cat.get("category_id")
        if progress and total:
            progress.update(int(done / total * 100), "Filme: " + cname)

        movies = xtream.api("get_vod_streams", {"category_id": cid}) or []
        category_items = []
        for m in movies:
            if progress and progress.iscanceled():
                canceled = True
                break

            item = {
                "name": m.get("name",""),
                "stream_id": m.get("stream_id"),
                "category_name": cname,
                "container_extension": m.get("container_extension","mp4"),
                "added": m.get("added")
            }
            category_items.append(item)
        if canceled:
            break

        data["movies"].extend(category_items)
        checkpoint_save_index(data)

        count, canceled = enrich_items_with_metadata(
            category_items,
            old_movie_metadata,
            "stream_id",
            MOVIE_METADATA_FIELDS,
            fetch_movie_metadata,
            progress,
            "Film-Infos",
            lambda: checkpoint_save_index(data)
        )
        new_movie_metadata_count += count
        if canceled:
            checkpoint_save_index(data)
            break

        done += 1

    if not canceled:
        for cat in series_categories:
            if progress and progress.iscanceled():
                canceled = True
                break

            cname = cat.get("category_name","")
            lang = extract_language_from_category(cname)
            if selected_languages and lang not in selected_languages:
                done += 1
                continue

            cid = cat.get("category_id")
            if progress and total:
                progress.update(int(done / total * 100), "Serien: " + cname)

            series = xtream.api("get_series", {"category_id": cid}) or []
            category_items = []
            for s in series:
                if progress and progress.iscanceled():
                    canceled = True
                    break

                item = {
                    "name": s.get("name",""),
                    "series_id": s.get("series_id"),
                    "category_name": cname,
                    "last_modified": s.get("last_modified"),
                    "added": s.get("added")
                }
                category_items.append(item)
            if canceled:
                break

            data["series"].extend(category_items)
            checkpoint_save_index(data)

            count, canceled = enrich_items_with_metadata(
                category_items,
                old_series_metadata,
                "series_id",
                SERIES_METADATA_FIELDS,
                fetch_series_metadata,
                progress,
                "Serien-Infos",
                lambda: checkpoint_save_index(data)
            )
            new_series_metadata_count += count
            if canceled:
                checkpoint_save_index(data)
                break

            done += 1

    if progress:
        progress.close()

    if canceled:
        if notify:
            xbmcgui.Dialog().notification("Index", "Index-Erstellung abgebrochen", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    save_index(data)
    if notify:
        xbmcgui.Dialog().notification(
            "Index aktualisiert",
            f"{len(data['movies'])} Filme, {len(data['series'])} Serien | neue Infos: {new_movie_metadata_count + new_series_metadata_count}",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
    return True


def rebuild_basic_index(show_progress=True, notify=True):
    if not has_credentials():
        if notify:
            xbmcgui.Dialog().ok("Index", "Bitte zuerst Xtream Zugangsdaten eintragen.")
        return False

    selected_languages = get_selected_languages()
    old_index = get_index()
    old_movie_metadata = get_old_movie_metadata_map(old_index)
    old_series_metadata = get_old_series_metadata_map(old_index)
    data = empty_index()
    data["created_at"] = time.time()
    data["signature"] = get_signature()

    progress = xbmcgui.DialogProgress() if show_progress else None
    if progress:
        progress.create("Basis-Index", "Lade Kategorien...")

    canceled = False
    movie_categories = xtream.api("get_vod_categories") or []
    series_categories = xtream.api("get_series_categories") or []
    total = len(movie_categories) + len(series_categories)
    done = 0

    for cat in movie_categories:
        if progress and progress.iscanceled():
            canceled = True
            break

        cname = cat.get("category_name", "")
        lang = extract_language_from_category(cname)
        if selected_languages and lang not in selected_languages:
            done += 1
            continue

        if progress and total:
            progress.update(int(done / total * 100), "Filme: " + cname)

        movies = xtream.api("get_vod_streams", {"category_id": cat.get("category_id")}) or []
        for m in movies:
            item = {
                "name": m.get("name", ""),
                "stream_id": m.get("stream_id"),
                "category_name": cname,
                "container_extension": m.get("container_extension", "mp4"),
                "added": m.get("added")
            }
            copy_metadata(item, old_movie_metadata.get(get_id_key(item.get("stream_id"))), MOVIE_METADATA_FIELDS)
            data["movies"].append(item)

        checkpoint_save_index(data)
        done += 1

    if not canceled:
        for cat in series_categories:
            if progress and progress.iscanceled():
                canceled = True
                break

            cname = cat.get("category_name", "")
            lang = extract_language_from_category(cname)
            if selected_languages and lang not in selected_languages:
                done += 1
                continue

            if progress and total:
                progress.update(int(done / total * 100), "Serien: " + cname)

            series = xtream.api("get_series", {"category_id": cat.get("category_id")}) or []
            for s in series:
                item = {
                    "name": s.get("name", ""),
                    "series_id": s.get("series_id"),
                    "category_name": cname,
                    "last_modified": s.get("last_modified"),
                    "added": s.get("added")
                }
                copy_metadata(item, old_series_metadata.get(get_id_key(item.get("series_id"))), SERIES_METADATA_FIELDS)
                data["series"].append(item)

            checkpoint_save_index(data)
            done += 1

    if progress:
        progress.close()

    if canceled:
        if notify:
            xbmcgui.Dialog().notification("Index", "Basis-Index abgebrochen", xbmcgui.NOTIFICATION_WARNING, 3000)
        return False

    save_index(data)
    if notify:
        xbmcgui.Dialog().notification(
            "Basis-Index aktualisiert",
            f"{len(data['movies'])} Filme, {len(data['series'])} Serien",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
    return True


def ensure_index(show_progress=True, notify=None):
    if not has_credentials():
        return False

    if notify is None:
        notify = show_progress

    data = get_index()
    if is_index_current(data):
        return True

    return rebuild_basic_index(show_progress=show_progress, notify=notify)


def get_current_index_for_search():
    data = get_index()
    if is_index_current(data):
        return data
    if ensure_index(show_progress=True, notify=True):
        return get_index()
    return empty_index()


def show_index_info():
    stats = get_index_stats()
    created_at = stats.get("created_at") or 0
    if created_at:
        date_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_at))
    else:
        date_text = "Noch nicht erstellt"

    status = "Aktuell" if stats.get("current") else "Fehlt oder veraltet"
    xbmcgui.Dialog().ok(
        "Index",
        "Status: {0}\nSprache: {1}\nDatei: {2}\nFilme: {3} ({4} mit TMDb/Release-Info)\nSerien: {5} ({6} mit TMDb/Release-Info)\nErstellt: {7}".format(
            status,
            stats.get("languages", "Alle"),
            stats.get("filename", ""),
            stats.get("movies", 0),
            stats.get("movies_with_tmdb", 0),
            stats.get("series", 0),
            stats.get("series_with_tmdb", 0),
            date_text
        )
    )


def search_movies(query):
    data = get_current_index_for_search()
    q = query.lower()
    return [m for m in data.get("movies", []) if q in m.get("name", "").lower()]


def search_series(query):
    data = get_current_index_for_search()
    q = query.lower()
    return [s for s in data.get("series", []) if q in s.get("name", "").lower()]


def find_movies_by_tmdb_id(tmdb_id):
    if not tmdb_id:
        return []

    data = get_current_index_for_search()
    wanted = str(tmdb_id)
    return [m for m in data.get("movies", []) if str(m.get("tmdb_id") or "") == wanted]


def find_series_by_tmdb_id(tmdb_id):
    if not tmdb_id:
        return []

    data = get_current_index_for_search()
    wanted = str(tmdb_id)
    return [s for s in data.get("series", []) if str(s.get("tmdb_id") or "") == wanted]


def get_group_statuses():
    data = get_index()
    groups = {}

    for movie in data.get("movies", []):
        name = movie.get("category_name", "Unbekannt")
        key = ("movies", name)
        groups.setdefault(key, {"media": "movies", "category_name": name, "total": 0, "checked": 0, "tmdb": 0})
        groups[key]["total"] += 1
        if movie.get("metadata_checked_at"):
            groups[key]["checked"] += 1
        if movie.get("tmdb_id"):
            groups[key]["tmdb"] += 1

    for serie in data.get("series", []):
        name = serie.get("category_name", "Unbekannt")
        key = ("series", name)
        groups.setdefault(key, {"media": "series", "category_name": name, "total": 0, "checked": 0, "tmdb": 0})
        groups[key]["total"] += 1
        if serie.get("metadata_checked_at"):
            groups[key]["checked"] += 1
        if serie.get("tmdb_id"):
            groups[key]["tmdb"] += 1

    return sorted(groups.values(), key=lambda item: (item["media"], item["category_name"].lower()))


def format_group_status(group):
    media_label = "Filme" if group.get("media") == "movies" else "Serien"
    return "{0} | {1} | TMDb {2}/{3} | geprüft {4}/{3}".format(
        media_label,
        group.get("category_name", "Unbekannt"),
        group.get("tmdb", 0),
        group.get("total", 0),
        group.get("checked", 0)
    )


def update_metadata_group(media, category_name, show_progress=True):
    data = get_index()
    if not data.get("movies") and not data.get("series"):
        xbmcgui.Dialog().ok("Index", "Bitte zuerst den Basis-Index erstellen.")
        return False

    if media == "movies":
        items = [item for item in data.get("movies", []) if item.get("category_name") == category_name]
        id_field = "stream_id"
        fields = MOVIE_METADATA_FIELDS
        fetch_func = fetch_movie_metadata
        label = "Film-Infos"
    else:
        items = [item for item in data.get("series", []) if item.get("category_name") == category_name]
        id_field = "series_id"
        fields = SERIES_METADATA_FIELDS
        fetch_func = fetch_series_metadata
        label = "Serien-Infos"

    progress = xbmcgui.DialogProgress() if show_progress else None
    if progress:
        progress.create("TMDb-Infos", category_name)

    count, canceled = enrich_items_with_metadata(
        items,
        {},
        id_field,
        fields,
        fetch_func,
        progress,
        label,
        lambda: checkpoint_save_existing_index(data)
    )

    if progress:
        progress.close()

    if canceled:
        xbmcgui.Dialog().notification("TMDb-Infos", "Aktualisierung abgebrochen", xbmcgui.NOTIFICATION_WARNING, 3000)
        checkpoint_save_existing_index(data)
        return False

    save_existing_index(data)
    xbmcgui.Dialog().notification(
        "TMDb-Infos aktualisiert",
        "{0} neue Prüfungen".format(count),
        xbmcgui.NOTIFICATION_INFO,
        3000
    )
    return True


def update_next_metadata_group(show_progress=False, notify=False):
    groups = get_group_statuses()
    incomplete = sorted(
        [group for group in groups if group.get("checked", 0) < group.get("total", 0)],
        key=lambda group: group.get("total", 0)
    )

    if not incomplete:
        return False

    group = incomplete[0]
    data = get_index()
    media = group.get("media")
    category_name = group.get("category_name")

    if media == "movies":
        items = [item for item in data.get("movies", []) if item.get("category_name") == category_name]
        id_field = "stream_id"
        fields = MOVIE_METADATA_FIELDS
        fetch_func = fetch_movie_metadata
        label = "Film-Infos"
    else:
        items = [item for item in data.get("series", []) if item.get("category_name") == category_name]
        id_field = "series_id"
        fields = SERIES_METADATA_FIELDS
        fetch_func = fetch_series_metadata
        label = "Serien-Infos"

    progress = xbmcgui.DialogProgress() if show_progress else None
    if progress:
        progress.create("TMDb-Infos", category_name)

    count, canceled = enrich_items_with_metadata(
        items,
        {},
        id_field,
        fields,
        fetch_func,
        progress,
        label,
        lambda: checkpoint_save_existing_index(data)
    )

    if progress:
        progress.close()

    if canceled:
        checkpoint_save_existing_index(data)
        return False

    save_existing_index(data)

    if notify:
        xbmcgui.Dialog().notification(
            "TMDb-Infos aktualisiert",
            "{0}: {1} neue Prüfungen".format(category_name, count),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

    return True


def show_metadata_groups():
    groups = get_group_statuses()
    if not groups:
        xbmcgui.Dialog().ok("Index", "Keine Gruppen im Index gefunden. Bitte zuerst Basis-Index erstellen.")
        return

    labels = [format_group_status(group) for group in groups]
    index = xbmcgui.Dialog().select("TMDb-Infos pro Gruppe", labels)
    if index == -1:
        return

    group = groups[index]
    update_metadata_group(group.get("media"), group.get("category_name"), show_progress=True)


def parse_added_timestamp(value):
    if value is None:
        return 0

    try:
        timestamp = int(str(value).strip())
    except Exception:
        return 0

    if timestamp > 9999999999:
        timestamp = int(timestamp / 1000)

    return timestamp


def get_recent_movies_by_language(language, days=14):
    data = get_current_index_for_search()
    since = int(time.time()) - (int(days) * 24 * 60 * 60)
    results = []

    for movie in data.get("movies", []):
        category_name = movie.get("category_name", "")
        if extract_language_from_category(category_name) != language:
            continue

        added = parse_added_timestamp(movie.get("added"))
        if added >= since:
            movie["added_timestamp"] = added
            results.append(movie)

    return sorted(results, key=lambda item: item.get("added_timestamp", 0), reverse=True)


def get_latest_movies_per_category_by_languages(languages, per_category=20):
    data = get_current_index_for_search()
    wanted = set(languages or [])
    grouped = {}

    for movie in data.get("movies", []):
        category_name = movie.get("category_name", "")
        language = extract_language_from_category(category_name)

        if wanted and language not in wanted:
            continue

        item = dict(movie)
        item["added_timestamp"] = parse_added_timestamp(item.get("added"))
        grouped.setdefault(category_name, []).append(item)

    results = []
    for category_name, movies in grouped.items():
        latest = sorted(
            movies,
            key=lambda item: item.get("added_timestamp", 0),
            reverse=True
        )[:int(per_category)]
        results.extend(latest)

    return results
