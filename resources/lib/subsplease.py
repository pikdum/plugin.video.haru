#!/usr/bin/env python3
import concurrent.futures as cf
import re
import time
from datetime import datetime

import requests
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup
from resources.lib.util import *


class SubsPlease:
    def __init__(self, db):
        self.db = db
        self.timezone = time.localtime().tm_gmtoff / 60 / 60

    def set_watched(self, name, watched=True):
        split = name.split(" - ")
        episode = split[-1]
        show = " - ".join(split[:-1])

        if watched == "False":
            del self.db.database["sp:watch"][show][episode]
            if self.db.database["sp:history"].get(name, None):
                del self.db.database["sp:history"][name]
            if not self.db.database["sp:watch"][show]:
                del self.db.database["sp:watch"][show]
            self.db.commit()
            return

        if "sp:watch" not in self.db.database:
            self.db.database["sp:watch"] = {}

        if show not in self.db.database["sp:watch"]:
            self.db.database["sp:watch"][show] = {}

        self.db.database["sp:history"][name] = {"timestamp": datetime.now()}

        self.db.database["sp:watch"][show][episode] = True
        self.db.commit()

    def is_show_watched(self, name):
        return name in self.db.database["sp:watch"]

    def is_episode_watched(self, name):
        split = name.split(" - ")
        episode = split[-1]
        show = " - ".join(split[:-1])

        if show not in self.db.database["sp:watch"]:
            return False
        if episode in self.db.database["sp:watch"][show]:
            return True
        return False

    def all(self, search=False):
        category = "Search" if search else "All"
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - {category}")

        page = requests.get("https://subsplease.org/shows/")
        soup = BeautifulSoup(page.text, "html.parser")
        links = filter(lambda x: x["href"].startswith("/shows/"), soup.find_all("a"))

        if search:
            search_term = xbmcgui.Dialog().input("Search for show:")
            if search_term:
                links = filter(
                    lambda x: search_term.lower() in x["title"].lower(), links
                )

        items = []
        for link in links:
            title = link["title"]
            label = title

            watched = self.is_show_watched(title)
            if watched:
                label = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=label)
            set_show_art(list_item, title)

            url = get_url(
                action="subsplease_show", url="https://subsplease.org" + link["href"]
            )
            items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def show(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        sid = soup.find(id="show-release-table")["sid"]
        show_title = soup.find("h1", class_="entry-title").text
        description = soup.find("div", class_="series-syn").find("p").text.strip()
        # TODO: fix multi-line descriptions

        xbmcplugin.setPluginCategory(HANDLE, show_title)

        episodes = requests.get(
            f"https://subsplease.org/api/?f=show&tz={self.timezone}&sid={sid}"
        ).json()

        items = []
        if episodes["batch"]:
            for batch, batch_info in episodes["batch"].items():
                list_item = xbmcgui.ListItem(label=f"[B][Batch][/B] {batch}")
                hq_download = batch_info["downloads"][-1]
                url = get_url(
                    action="subsplease_batch",
                    batch=batch,
                    batch_torrent=hq_download["torrent"],
                )
                set_show_art(list_item, show_title)
                items.append((url, list_item, True))

        if episodes["episode"]:
            for episode, episode_info in reversed(episodes["episode"].items()):
                release_date = re.sub(r" \d{2}:.*$", "", episode_info["release_date"])

                display_name = re.sub(r"v\d$", "", episode)
                title = f"{display_name} [I][LIGHT]— {release_date}[/LIGHT][/I]"

                watched = self.is_episode_watched(display_name)
                if watched:
                    title = f"[COLOR palevioletred]{title}[/COLOR]"

                list_item = xbmcgui.ListItem(label=title)
                list_item.setInfo(
                    "video",
                    {
                        "title": title,
                        "mediatype": "video",
                        "plot": description,
                    },
                )
                list_item.setProperty("IsPlayable", "true")
                set_show_art(list_item, show_title)
                hq_download = episode_info["downloads"][-1]
                url = get_url(
                    action="play_subsplease",
                    url=hq_download["torrent"],
                    name=display_name,
                )
                list_item.addContextMenuItems(
                    [
                        ('[B]Play[/B]', f'PlayMedia({url})'),
                        (
                            "[B]Toggle Watched[/B]",
                            "RunPlugin(%s)"
                            % get_url(
                                action="toggle_watched_subsplease",
                                name=display_name,
                                watched=not watched,
                            ),
                        )
                    ]
                )
                items.append((url, list_item, False))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def batch(self, batch, batch_torrent):
        xbmcplugin.setPluginCategory(HANDLE, batch)

        page = requests.get(batch_torrent.replace("/torrent", ""))
        soup = BeautifulSoup(page.text, "html.parser")
        magnet = soup.find("a", class_="card-footer-item").get("href")

        split = batch.split(" - ")
        show = " - ".join(split[:-1])

        while soup.i:
            soup.i.decompose()
        while soup.span:
            soup.span.decompose()
        file_list = filter(
            lambda x: any(x.lower().endswith(ext) for ext in VIDEO_FORMATS),
            map(
                lambda x: x.strip(),
                soup.find("div", class_="torrent-file-list").text.split("\n"),
            ),
        )

        items = []
        for file_name in file_list:
            display_name = file_name.replace("[SubsPlease] ", "")
            display_name = re.sub(r"(v\d)? \(.*p\) \[.*\]\..*", "", display_name)
            title = display_name

            watched = self.is_episode_watched(title)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo(
                "video",
                {
                    "title": title,
                    "genre": "Anime",
                    "mediatype": "video",
                },
            )
            list_item.setProperty("IsPlayable", "true")
            set_show_art(list_item, show)
            url = get_url(
                action="play_subsplease",
                magnet=magnet,
                selected_file=file_name,
                name=display_name,
            )
            list_item.addContextMenuItems(
                [
                    ('[B]Play[/B]', f'PlayMedia({url})'),
                    (
                        "[B]Toggle Watched[/B]",
                        "RunPlugin(%s)"
                        % get_url(
                            action="toggle_watched_subsplease",
                            name=display_name,
                            watched=not watched,
                        ),
                    )
                ]
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
        schedule = requests.get(
            f"https://subsplease.org/api/?f=schedule&tz={self.timezone}"
        ).json()["schedule"]

        flattened_schedule = []

        for day, shows in schedule.items():
            for show in shows:
                show["day"] = day
                flattened_schedule.append(show)

        flattened_schedule = sorted(flattened_schedule, key=lambda x: x["title"])
        return flattened_schedule

    def all_airing(self):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - All Airing")
        schedule = self.get_schedule()

        items = []
        for show in schedule:
            # workaround: https://forum.kodi.tv/showthread.php?pid=1214507#pid1214507
            formatted_time = datetime(
                *(time.strptime(show["time"], "%H:%M")[0:6])
            ).strftime("%I:%M %p")

            title = f"""{show["title"]} [I][LIGHT]— {show["day"]} @ {formatted_time}[/LIGHT][/I]"""

            watched = self.is_show_watched(show["title"])
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            set_show_art(list_item, show["title"])
            url = get_url(
                action="subsplease_show",
                url="https://subsplease.org/shows/" + show["page"],
            )
            items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def day(self, day):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - {day}")

        if day == "Today":
            schedule = requests.get(
                f"https://subsplease.org/api/?f=schedule&h=true&tz={self.timezone}"
            ).json()["schedule"]
        else:
            schedule = requests.get(
                f"https://subsplease.org/api/?f=schedule&tz={self.timezone}"
            ).json()["schedule"][day]

        items = []
        for show in schedule:
            # workaround: https://forum.kodi.tv/showthread.php?pid=1214507#pid1214507
            formatted_time = datetime(
                *(time.strptime(show["time"], "%H:%M")[0:6])
            ).strftime("%I:%M %p")
            title = show["title"]

            label = f"""[B]{formatted_time}[/B] - {title}"""

            watched = self.is_show_watched(title)
            if watched:
                label = f"[COLOR palevioletred]{label}[/COLOR]"

            list_item = xbmcgui.ListItem(label=label)
            set_show_art(list_item, title)
            url = get_url(
                action="subsplease_show",
                url="https://subsplease.org/shows/" + show["page"],
            )
            items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def history(self):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - History")

        items = []
        for title, data in reversed(self.db.database["sp:history"].items()):
            split = title.split(" - ")
            show = " - ".join(split[:-1])

            formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
            label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
            url = get_url(
                action="subsplease_show",
                url=f"https://subsplease.org/shows/{slugify(show)}/",
            )
            list_item = xbmcgui.ListItem(label=label)
            set_show_art(list_item, show)
            items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(HANDLE, items)
        xbmcplugin.endOfDirectory(HANDLE)

    def is_unfinished(self, show):
        page = requests.get(f"https://subsplease.org/shows/{slugify(show)}/")
        soup = BeautifulSoup(page.text, "html.parser")
        sid = soup.find(id="show-release-table")["sid"]

        episodes = requests.get(
            f"https://subsplease.org/api/?f=show&tz={self.timezone}&sid={sid}"
        ).json()
        if not episodes["episode"]:
            return False
        latest_episode = list(episodes["episode"].keys())[0]

        if self.is_episode_watched(latest_episode):
            return False

        return True

    def unfinished(self, airing_only=False):
        category = (
            "SubsPlease - Unfinished"
            if not airing_only
            else "SubsPlease - Unfinished Airing"
        )
        xbmcplugin.setPluginCategory(HANDLE, category)

        shows = []
        sorted_items = sorted(self.db.database["sp:watch"].items(), key=lambda x: x[0])

        # if airing_only, filter out shows that are not in current schedule
        if airing_only:
            schedule = self.get_schedule()
            sorted_items = list(
                filter(
                    lambda x: x[0] in [show["title"] for show in schedule], sorted_items
                )
            )

        total_items = len(sorted_items)

        progress_dialog = xbmcgui.DialogProgress()
        progress_dialog.create(
            category,
            "Checking shows...",
        )

        progress = 0
        with cf.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.is_unfinished, show) for show, _ in sorted_items
            ]

            for future in cf.as_completed(futures):
                progress += 1
                is_unfinished = future.result()
                index = futures.index(future)
                item = sorted_items[index]

                if is_unfinished:
                    shows.append(item[0])

                if progress_dialog.iscanceled():
                    break

                progress_dialog.update(
                    int((progress / total_items) * 100),
                    f"Checking {item[0]}...",
                )

        progress_dialog.close()

        xbmcplugin.addDirectoryItems(
            HANDLE,
            [
                (
                    get_url(
                        action="subsplease_show",
                        url=f"https://subsplease.org/shows/{slugify(show)}/",
                    ),
                    set_show_art(
                        xbmcgui.ListItem(f"[COLOR palevioletred]{show}[/COLOR]"), show
                    ),
                    True,
                )
                for show in sorted(shows)
            ],
        )
        xbmcplugin.endOfDirectory(HANDLE)
