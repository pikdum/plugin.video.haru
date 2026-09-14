#!/usr/bin/env python3
"""One-time cutover of SubsPlease watch data from title keys to Histoire show ids.

The legacy maps split every release name on its last `` - ``, so
``"Show - 05"`` became ``sp:watch["Show"]["05"]``. That prefix is not always
a show: SubsPlease files sub-series such as
``"Lord of Mysteries - Chibi Theatre - 05"`` under the main show's page, where
episode ``05`` would collide with the main series. The v2 maps key shows by
Histoire id and episodes by their full release name, which SubsPlease keeps
unique:

    sp:watch_v2[show_id]         = {"slug", "episodes": {"Show - 05": True}}
    sp:history_v2["Show - 05"]   = {"timestamp", "show_id"}

Anything that cannot be resolved against the catalog is parked under
``sp:legacy`` untouched, so nothing is lost even though the UI never reads it.
This module has no Kodi imports so the migration can be exercised from plain
Python against a copy of a real database.
"""

import re

LEGACY_WATCH = "sp:watch"
LEGACY_HISTORY = "sp:history"
WATCH = "sp:watch_v2"
HISTORY = "sp:history_v2"
LEGACY_BUCKET = "sp:legacy"


def normalize_release_name(name):
    """Drop a trailing version marker so ``Show - 05v2`` matches ``Show - 05``."""
    return re.sub(r"v\d+$", "", name)


def compact(text):
    """Reduce a title or slug to lowercase alphanumerics.

    Histoire titles come from SubsPlease show pages, which use en dashes and
    curly quotes where release names use ``-`` and ``'``. A few shows also
    release under their slug as a short name (``Iseleve - 01``). Comparing
    compacted forms against both title and slug covers all of those.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


class Resolver:
    """Map a legacy release-name prefix to a catalog show.

    ``fetch_show`` loads one show with its releases; it is only called for the
    prefix fallback, to confirm that the shorter match really carries releases
    under the longer name.
    """

    def __init__(self, shows, show_cache=None, fetch_show=None):
        self.by_id = {show["id"]: show for show in shows}
        self.by_compact = {}
        for show in shows:
            self.by_compact.setdefault(compact(show["title"]), show)
            self.by_compact.setdefault(compact(show["slug"]), show)
        self.show_cache = show_cache or {}
        self.fetch_show = fetch_show
        self.memo = {}

    def resolve(self, title):
        if title not in self.memo:
            self.memo[title] = self._resolve(title)
        return self.memo[title]

    def _resolve(self, title):
        cached_id = self.show_cache.get(title, {}).get("show_id")
        if cached_id in self.by_id:
            return self.by_id[cached_id]

        direct = self.by_compact.get(compact(title))
        if direct:
            return direct

        parts = title.split(" - ")
        for length in range(len(parts) - 1, 0, -1):
            candidate = self.by_compact.get(compact(" - ".join(parts[:length])))
            if candidate and self._carries_prefix(candidate, title):
                return candidate

        return None

    def _carries_prefix(self, show, prefix):
        if not self.fetch_show:
            return False
        detail = self.fetch_show(show["id"])
        return any(
            release["name"].startswith(prefix + " - ")
            for release in detail.get("releases", [])
        )


def needs_migration(database):
    return LEGACY_WATCH in database or LEGACY_HISTORY in database


def migrate(database, shows, fetch_show=None):
    """Move legacy maps into v2 in place. Returns a summary dict.

    ``shows`` is the Histoire catalog listing. The legacy keys and the old
    per-title show cache are removed once consumed.
    """
    legacy_watch = database.pop(LEGACY_WATCH, {}) or {}
    legacy_history = database.pop(LEGACY_HISTORY, {}) or {}
    show_cache = database.get("cache", {}).get("sp", {}).get("show", {})
    resolver = Resolver(shows, show_cache, fetch_show)

    watch = database.setdefault(WATCH, {})
    history = database.setdefault(HISTORY, {})
    unresolved_watch = {}
    unresolved_history = {}

    for title, episodes in legacy_watch.items():
        show = resolver.resolve(title)
        if not show:
            unresolved_watch[title] = episodes
            continue
        entry = watch.setdefault(show["id"], {"slug": show["slug"], "episodes": {}})
        for episode in episodes:
            entry["episodes"][f"{title} - {episode}"] = True

    for name, data in legacy_history.items():
        title = " - ".join(name.split(" - ")[:-1])
        show = resolver.resolve(title)
        if not show:
            unresolved_history[name] = data
            continue
        history[name] = {**data, "show_id": show["id"]}

    if unresolved_watch or unresolved_history:
        bucket = database.setdefault(LEGACY_BUCKET, {"watch": {}, "history": {}})
        bucket["watch"].update(unresolved_watch)
        bucket["history"].update(unresolved_history)

    database.get("cache", {}).pop("sp", None)

    return {
        "shows": len(legacy_watch) - len(unresolved_watch),
        "history": len(legacy_history) - len(unresolved_history),
        "unresolved_shows": sorted(unresolved_watch),
        "unresolved_history": len(unresolved_history),
    }
