#!/usr/bin/env python3
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

    def get_cached_art(self, show):
        return self.db.database["sp:art_cache"].get(show, None)

    def set_cached_art(self, show, art):
        if not self.db.database["sp:art_cache"].get(show, None):
            self.db.database["sp:art_cache"][show] = art
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

    def all(self):
        xbmcplugin.setPluginCategory(HANDLE, "SubsPlease - All")

        page = requests.get("https://subsplease.org/shows/")
        soup = BeautifulSoup(page.text, "html.parser")
        links = filter(lambda x: x["href"].startswith("/shows/"), soup.find_all("a"))

        for link in links:
            title = link["title"]

            watched = self.is_show_watched(title)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            artwork_url = self.get_cached_art(title)
            if artwork_url:
                list_item.setArt({"poster": artwork_url})

            is_folder = True
            url = get_url(
                action="subsplease_show", url="https://subsplease.org" + link["href"]
            )
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def show(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        sid = soup.find(id="show-release-table")["sid"]
        show_title = soup.find("h1", class_="entry-title").text
        artwork_url = "https://subsplease.org" + soup.find("img")["src"]
        description = soup.find("div", class_="series-syn").find("p").text.strip()
        self.set_cached_art(show_title, artwork_url)

        xbmcplugin.setPluginCategory(HANDLE, show_title)

        episodes = requests.get(
            f"https://subsplease.org/api/?f=show&tz={self.timezone}&sid={sid}"
        ).json()

        if episodes["batch"]:
            for batch, batch_info in episodes["batch"].items():
                list_item = xbmcgui.ListItem(label=f"[B][Batch][/B] {batch}")
                hq_download = batch_info["downloads"][-1]
                is_folder = True
                url = get_url(
                    action="subsplease_batch",
                    batch=batch,
                    batch_torrent=hq_download["torrent"],
                )
                list_item.setArt({"poster": artwork_url})
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

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
                list_item.setArt({"poster": artwork_url})
                list_item.addContextMenuItems(
                    [
                        (
                            "Toggle Watched",
                            "RunPlugin(%s)"
                            % get_url(
                                action="toggle_watched_subsplease",
                                name=display_name,
                                watched=not watched,
                            ),
                        )
                    ]
                )
                hq_download = episode_info["downloads"][-1]
                is_folder = False
                url = get_url(
                    action="play_subsplease",
                    url=hq_download["torrent"],
                    name=display_name,
                )
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def batch(self, batch, batch_torrent):
        xbmcplugin.setPluginCategory(HANDLE, batch)

        page = requests.get(batch_torrent.replace("/torrent", ""))
        soup = BeautifulSoup(page.text, "html.parser")
        magnet = soup.find("a", class_="card-footer-item").get("href")

        split = batch.split(" - ")
        show = " - ".join(split[:-1])
        artwork_url = self.get_cached_art(show)

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
            if artwork_url:
                list_item.setArt({"poster": artwork_url})
            list_item.addContextMenuItems(
                [
                    (
                        "Toggle Watched",
                        "RunPlugin(%s)"
                        % get_url(
                            action="toggle_watched_subsplease",
                            name=display_name,
                            watched=not watched,
                        ),
                    )
                ]
            )
            is_folder = False
            url = get_url(
                action="play_subsplease",
                magnet=magnet,
                selected_file=file_name,
                name=display_name,
            )
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def airing(self):
        xbmcplugin.setPluginCategory(HANDLE, "SubsPlease - Airing")

        list_item = xbmcgui.ListItem(label="All")
        url = get_url(action="subsplease_all_airing")
        is_folder = True
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        for day in [
            "Today",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "TBD",
        ]:
            list_item = xbmcgui.ListItem(label=day)
            url = get_url(action="subsplease_day", day=day)
            is_folder = True
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def all_airing(self):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - All Airing")

        schedule = requests.get(
            f"https://subsplease.org/api/?f=schedule&tz={self.timezone}"
        ).json()["schedule"]

        flattened_schedule = []

        for day, shows in schedule.items():
            for show in shows:
                show["day"] = day
                flattened_schedule.append(show)

        flattened_schedule = sorted(flattened_schedule, key=lambda x: x["title"])

        for show in flattened_schedule:
            # workaround: https://forum.kodi.tv/showthread.php?pid=1214507#pid1214507
            formatted_time = datetime(
                *(time.strptime(show["time"], "%H:%M")[0:6])
            ).strftime("%I:%M %p")
            artwork_url = "https://subsplease.org" + show["image_url"]
            self.set_cached_art(show["title"], artwork_url)

            title = f"""{show["title"]} [I][LIGHT]— {show["day"]} @ {formatted_time}[/LIGHT][/I]"""

            watched = self.is_show_watched(show["title"])
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({"poster": artwork_url})
            url = get_url(
                action="subsplease_show",
                url="https://subsplease.org/shows/" + show["page"],
            )
            is_folder = True
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

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

        for show in schedule:
            # workaround: https://forum.kodi.tv/showthread.php?pid=1214507#pid1214507
            formatted_time = datetime(
                *(time.strptime(show["time"], "%H:%M")[0:6])
            ).strftime("%I:%M %p")
            artwork_url = "https://subsplease.org" + show["image_url"]
            self.set_cached_art(show["title"], artwork_url)

            title = f"""[B]{formatted_time}[/B] - {show["title"]}"""

            watched = self.is_show_watched(show["title"])
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({"poster": artwork_url})
            url = get_url(
                action="subsplease_show",
                url="https://subsplease.org/shows/" + show["page"],
            )
            is_folder = True
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def history(self):
        xbmcplugin.setPluginCategory(HANDLE, f"SubsPlease - History")

        list_item = xbmcgui.ListItem(label="Clear History")
        xbmcplugin.addDirectoryItem(
            HANDLE, get_url(action="clear_history_subsplease"), list_item
        )

        for title, data in reversed(self.db.database["sp:history"].items()):
            split = title.split(" - ")
            show = " - ".join(split[:-1])

            formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
            label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
            artwork_url = self.get_cached_art(show)
            url = get_url(
                action="subsplease_show",
                url=f"https://subsplease.org/shows/{show}/",
            )
            list_item = xbmcgui.ListItem(label=label)
            if artwork_url:
                list_item.setArt({"poster": artwork_url})
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
