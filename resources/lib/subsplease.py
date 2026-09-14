#!/usr/bin/env python3
import re
from datetime import datetime, time, timedelta, timezone

import xbmcgui
import xbmcplugin
from resources.lib import subsplease_migration as migration
from resources.lib.histoire import Histoire
from resources.lib.history import HistoryArchive, build_history_directory
from resources.lib.util import (
    HANDLE,
    VIDEO_FORMATS,
    get_url,
    log,
    set_icon_art,
    set_show_art,
)


class SubsPlease:
    def __init__(self, db, client=None):
        self.db = db
        self.client = client or Histoire()
        self._migrate_legacy()

    # Watch data is keyed by Histoire show id, then by full release name; see
    # subsplease_migration for the shape and the one-time cutover.
    def _migrate_legacy(self):
        if not migration.needs_migration(self.db.database):
            return

        try:
            report = migration.migrate(
                self.db.database, self.client.shows(), self.client.show
            )
        except Exception as error:
            log(f"SubsPlease watch migration failed, will retry: {error!r}")
            xbmcgui.Dialog().notification(
                "haru", "SubsPlease watch data migration failed; will retry."
            )
            return

        self.db.commit()
        log(f"SubsPlease watch migration: {report}")

    @property
    def watch(self):
        return self.db.database.setdefault(migration.WATCH, {})

    @property
    def history_entries(self):
        return self.db.database.setdefault(migration.HISTORY, {})

    def normalize_episode_name(self, episode):
        return migration.normalize_release_name(episode)

    def set_watched(self, name, show_id, watched=True):
        show_id = int(show_id)
        name = self.normalize_episode_name(name)

        if watched == "False":
            entry = self.watch.get(show_id)
            if entry:
                entry["episodes"].pop(name, None)
                if not entry["episodes"]:
                    del self.watch[show_id]
            self.history_entries.pop(name, None)
            self.db.commit()
            return

        entry = self.watch.setdefault(show_id, {"slug": None, "episodes": {}})
        entry["episodes"][name] = True
        self.history_entries[name] = {"timestamp": datetime.now(), "show_id": show_id}
        self.db.commit()

    def is_show_watched(self, show_id):
        return show_id is not None and int(show_id) in self.watch

    def is_episode_watched(self, show_id, name):
        episodes = self.watch.get(int(show_id), {}).get("episodes", {})
        return bool(episodes.get(self.normalize_episode_name(name)))

    def all(self, search=False):
        category = "Search" if search else "All"
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - {category}")

        query = xbmcgui.Dialog().input("Search for show:") if search else None
        shows = self.client.shows(query) if not search or query else []

        xbmcplugin.addDirectoryItems(
            HANDLE, [self._show_directory_item(show) for show in shows]
        )
        xbmcplugin.endOfDirectory(HANDLE)

    def show(self, show_id):
        show = self.client.show(show_id)
        description = show.get("synopsis") or ""
        xbmcplugin.setPluginCategory(HANDLE, show["title"])

        entry = self.watch.get(show["id"])
        if entry and entry.get("slug") != show.get("slug"):
            entry["slug"] = show.get("slug")
            self.db.commit()

        batches = [
            release for release in show["releases"] if release["kind"] == "batch"
        ]
        episodes = [
            release for release in show["releases"] if release["kind"] == "episode"
        ]

        items = [self._batch_item(show, release) for release in batches]
        items.extend(
            self._episode_item(show, release, description)
            for release in reversed(episodes)
        )

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def _batch_item(self, show, release):
        download = self._highest_resolution(release["downloads"])
        list_item = xbmcgui.ListItem(label=f"[B][Batch][/B] {release['name']}")
        self._set_show_info(list_item, show, release["name"])
        self._set_art(list_item, show)

        return (
            get_url(
                action="subsplease_batch",
                batch=release["name"],
                download_id=download["id"],
                show_id=show["id"],
            ),
            list_item,
            True,
        )

    def _episode_item(self, show, release, description):
        display_name = self.normalize_episode_name(release["name"])
        release_date = release.get("release_date") or ""
        title = display_name
        if release_date:
            title = f"{title} [I][LIGHT]— {release_date}[/LIGHT][/I]"

        watched = self.is_episode_watched(show["id"], display_name)
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=title)
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "plot": description},
        )
        list_item.setProperty("IsPlayable", "true")
        self._set_art(list_item, show)

        download = self._highest_resolution(release["downloads"])
        url = get_url(
            action="play_subsplease",
            magnet=download["magnet_uri"],
            name=display_name,
            show_id=show["id"],
        )
        list_item.addContextMenuItems(self._episode_context(url, show, display_name))
        return url, list_item, False

    def _episode_context(self, play_url, show, display_name):
        watched = self.is_episode_watched(show["id"], display_name)
        return [
            ("[B]Play[/B]", f"PlayMedia({play_url})"),
            (
                "[B]Toggle Watched[/B]",
                "RunPlugin(%s)"
                % get_url(
                    action="toggle_watched_subsplease",
                    name=display_name,
                    show_id=show["id"],
                    watched=not watched,
                ),
            ),
        ]

    def batch(self, batch, download_id, show_id):
        xbmcplugin.setPluginCategory(HANDLE, batch)
        show = self.client.show(show_id)
        torrent = self.client.download_files(download_id)

        items = []
        for file in torrent["files"]:
            file_name = file["path"]
            if not any(file_name.lower().endswith(ext) for ext in VIDEO_FORMATS):
                continue

            display_name = file_name.rsplit("/", 1)[-1].replace("[SubsPlease] ", "")
            display_name = re.sub(r"(v\d)? \(.*p\) \[.*\]\..*", "", display_name)
            title = display_name
            if self.is_episode_watched(show["id"], display_name):
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo(
                "video",
                {
                    "title": title,
                    "genre": "Anime",
                    "mediatype": "video",
                    "plot": show.get("synopsis") or "",
                },
            )
            list_item.setProperty("IsPlayable", "true")
            self._set_art(list_item, show)
            url = get_url(
                action="play_subsplease",
                magnet=torrent["magnet_uri"],
                selected_file=file_name,
                name=display_name,
                show_id=show["id"],
            )
            list_item.addContextMenuItems(
                self._episode_context(url, show, display_name)
            )
            items.append((url, list_item, False))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def airing(self):
        xbmcplugin.setPluginCategory(HANDLE, "SubsPlease - Airing")
        xbmcplugin.addDirectoryItems(
            HANDLE,
            [
                (
                    get_url(action="subsplease_day", day=day),
                    set_icon_art(xbmcgui.ListItem(day), day.lower()),
                    True,
                )
                for day in [
                    "Today",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
            ]
            + [
                (
                    get_url(action="subsplease_all_airing"),
                    set_icon_art(xbmcgui.ListItem("All"), "video-playlist"),
                    True,
                ),
                (
                    get_url(action="subsplease_unfinished", airing_only=True),
                    set_icon_art(xbmcgui.ListItem("Unfinished"), "in-progress"),
                    True,
                ),
            ],
        )
        xbmcplugin.endOfDirectory(HANDLE)

    def get_schedule(self):
        return sorted(
            (self._localize_schedule(show) for show in self.client.schedule()),
            key=lambda show: show["title"],
        )

    def _localize_schedule(self, show):
        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        now = datetime.now(timezone.utc)
        monday = (now - timedelta(days=now.weekday())).date()
        hour, minute, *_rest = map(int, show["scheduled_time"].split(":"))
        scheduled_at = datetime.combine(
            monday + timedelta(days=weekdays.index(show["weekday"])),
            time(hour, minute),
            tzinfo=timezone.utc,
        ).astimezone()

        localized = dict(show)
        localized["day"] = weekdays[scheduled_at.weekday()]
        localized["time"] = scheduled_at.strftime("%H:%M")
        return localized

    def _build_schedule_item(self, show, label):
        catalog_show = show.get("show")
        watched = catalog_show and self.is_show_watched(catalog_show["id"])

        if watched:
            label = f"[COLOR palevioletred]{label}[/COLOR]"
        elif not catalog_show:
            label = f"[COLOR gray]{label}[/COLOR]"

        list_item = xbmcgui.ListItem(label=label)
        if catalog_show:
            self._set_show_info(list_item, catalog_show, show["title"])
        set_show_art(
            list_item,
            show["title"],
            show.get("poster_url"),
            show.get("fanart_url"),
        )

        if catalog_show:
            return (
                get_url(action="subsplease_show", show_id=catalog_show["id"]),
                list_item,
                True,
            )

        return (
            get_url(action="notify", title="haru", message="Show not available yet."),
            list_item,
            False,
        )

    def all_airing(self):
        xbmcplugin.setPluginCategory(HANDLE, "SubsPlease - All Airing")
        items = []
        for show in self.get_schedule():
            formatted_time = datetime.strptime(show["time"], "%H:%M").strftime(
                "%I:%M %p"
            )
            label = f"{show['title']} [I][LIGHT]— {show['day']} @ {formatted_time}[/LIGHT][/I]"
            items.append(self._build_schedule_item(show, label))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def day(self, day):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - {day}")
        schedule = self.get_schedule()
        selected_day = datetime.now().strftime("%A") if day == "Today" else day

        items = []
        for show in (show for show in schedule if show["day"] == selected_day):
            formatted_time = datetime.strptime(show["time"], "%H:%M").strftime(
                "%I:%M %p"
            )
            items.append(
                self._build_schedule_item(
                    show, f"[B]{formatted_time}[/B] - {show['title']}"
                )
            )

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def _history_items(self, entries):
        catalog = self._catalog_by_id(data["show_id"] for _name, data in entries)
        items = []

        for name, data in entries:
            show = catalog.get(data["show_id"])
            formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
            label = f"[COLOR palevioletred]{name} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
            list_item = xbmcgui.ListItem(label=label)

            if show:
                self._set_show_info(list_item, show)
                self._set_art(list_item, show)
            else:
                set_show_art(list_item, " - ".join(name.split(" - ")[:-1]))

            items.append(
                (
                    get_url(action="subsplease_show", show_id=data["show_id"]),
                    list_item,
                    True,
                )
            )

        return items

    def history(self, year=None, month=None, full=False):
        archive = HistoryArchive(self.history_entries)
        category, items = build_history_directory(
            archive=archive,
            action="subsplease_history",
            category="SubsPlease - History",
            render_entries=self._history_items,
            year=year,
            month=month,
            full=full,
        )

        xbmcplugin.setPluginCategory(HANDLE, category)
        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def unfinished(self, airing_only=False):
        category = (
            "SubsPlease - Unfinished"
            if not airing_only
            else "SubsPlease - Unfinished Airing"
        )
        xbmcplugin.setPluginCategory(HANDLE, category)

        catalog = self._catalog_by_id(self.watch)
        airing_ids = None
        if airing_only:
            airing_ids = {
                entry["show"]["id"]
                for entry in self.client.schedule()
                if entry.get("show")
            }

        shows = []
        for show_id in self.watch:
            if airing_ids is not None and show_id not in airing_ids:
                continue

            show = catalog.get(show_id)
            if not show:
                continue

            latest_episode = show.get("latest_episode")
            if latest_episode and not self.is_episode_watched(show_id, latest_episode):
                shows.append(show)

        shows.sort(key=lambda show: show["title"])
        xbmcplugin.addDirectoryItems(
            HANDLE,
            [self._show_directory_item(show, watched_color=True) for show in shows],
        )
        xbmcplugin.endOfDirectory(HANDLE)

    def _catalog_by_id(self, ids):
        ids = list(ids)
        if not ids:
            return {}
        return {show["id"]: show for show in self.client.shows_by_id(ids)}

    def _show_directory_item(self, show, watched_color=False):
        title = show["title"]
        label = title
        if watched_color or self.is_show_watched(show["id"]):
            label = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=label)
        self._set_show_info(list_item, show)
        self._set_art(list_item, show)
        return (
            get_url(action="subsplease_show", show_id=show["id"]),
            list_item,
            True,
        )

    def _set_art(self, list_item, show):
        return set_show_art(
            list_item,
            show["title"],
            show.get("poster_url"),
            show.get("fanart_url"),
        )

    def _set_show_info(self, list_item, show, title=None):
        list_item.setInfo(
            "video",
            {
                "title": title or show["title"],
                "mediatype": "tvshow",
                "plot": show.get("synopsis") or "",
            },
        )

    def _highest_resolution(self, downloads):
        return max(
            downloads,
            key=lambda download: int(re.sub(r"\D", "", download["resolution"]) or 0),
        )
