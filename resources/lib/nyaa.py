#!/usr/bin/env python3
import time
from datetime import datetime
from urllib.parse import quote

import requests
import xbmc
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup
from resources.lib.util import *


class Nyaa:
    def __init__(self, db, mode):
        self.db = db
        if mode == "fun":
            self.hostname = "nyaa.si"
            self.db_prefix = "nt"
            self.page_action = "nyaa_page"
            self.search_results_action = "nyaa_search_results"
            self.toggle_watched_action = "toggle_watched_nyaa"
            self.play_action = "play_nyaa"
        if mode == "fap":
            self.hostname = "sukebei.nyaa.si"
            self.db_prefix = "sb"
            self.page_action = "sukebei_page"
            self.search_results_action = "sukebei_search_results"
            self.toggle_watched_action = "toggle_watched_sukebei"
            self.play_action = "play_sukebei"
        self.mode = mode

    def get_categories(self):
        page = requests.get(f"https://{self.hostname}")
        soup = BeautifulSoup(page.text, "html.parser")
        select = soup.find("select", title="Category")
        options = select.find_all("option")
        categories = [(option.text.strip(), option["value"]) for option in options]
        return categories

    def set_watched(self, torrent_name, file_name, nyaa_url, watched=True):
        if watched == "False":
            del self.db.database[f"{self.db_prefix}:watch"][torrent_name][file_name]
            if self.db.database[f"{self.db_prefix}:history"].get(file_name, None):
                del self.db.database[f"{self.db_prefix}:history"][file_name]
            if not self.db.database[f"{self.db_prefix}:watch"][torrent_name]:
                del self.db.database[f"{self.db_prefix}:watch"][torrent_name]
            self.db.commit()
            return

        if f"{self.db_prefix}:watch" not in self.db.database:
            self.db.database[f"{self.db_prefix}:watch"] = {}

        if torrent_name not in self.db.database[f"{self.db_prefix}:watch"]:
            self.db.database[f"{self.db_prefix}:watch"][torrent_name] = {}

        self.db.database[f"{self.db_prefix}:history"][file_name] = {
            "timestamp": datetime.now(),
            "torrent_name": torrent_name,
            "nyaa_url": nyaa_url,
        }

        self.db.database[f"{self.db_prefix}:watch"][torrent_name][file_name] = True
        self.db.commit()

    def is_file_watched(self, torrent_name, file_name):
        return (
            self.db.database[f"{self.db_prefix}:watch"]
            .get(torrent_name, {})
            .get(file_name, False)
        )

    def is_torrent_watched(self, torrent_name):
        return self.db.database[f"{self.db_prefix}:watch"].get(torrent_name, False)

    def search(self):
        keyboard = xbmc.Keyboard("", "Search for torrents:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            return
        escaped = quote(text)

        category = select_option(self.get_categories(), "Category")
        if not category:
            return

        sort = select_option(
            [
                ("Seeders", "seeders"),
                ("Date", "id"),
                ("Size", "size"),
                ("Leechers", "leechers"),
                ("Downloads", "downloads"),
                ("Comments", "comments"),
            ],
            "Sort by",
        )
        if not sort:
            return

        sort_order = select_option(
            [("Descending", "desc"), ("Ascending", "asc")], "Sort order"
        )
        if not sort_order:
            return

        xbmcplugin.setPluginCategory(HANDLE, "Torrent Search")
        xbmcplugin.addDirectoryItem(
            HANDLE,
            get_url(
                action=self.search_results_action,
                text=escaped,
                category=category,
                sort=sort,
                order=sort_order,
            ),
            xbmcgui.ListItem(
                label=f"View Results - '{escaped}', {category}, {sort}, {sort_order}"
            ),
            isFolder=True,
        )
        xbmcplugin.endOfDirectory(HANDLE)

    def search_results(self, category, text, sort="seeders", order="desc"):
        page = requests.get(
            f"https://{self.hostname}/?f=0&c={category}&q={text}&s={sort}&o={order}"
        )
        soup = BeautifulSoup(page.text, "html.parser")

        rows = soup.find_all("tr")[1:]

        for row in rows:
            columns = row.find_all("td")
            link = next(
                filter(
                    lambda x: not x["href"].endswith("#comments"),
                    columns[1].find_all("a"),
                )
            )
            torrent_name = link.string

            size = columns[3].text
            date = columns[4].text
            formatted_date = datetime(
                *(time.strptime(date, "%Y-%m-%d %H:%M")[0:6])
            ).strftime("%Y-%m-%d")

            seeds = columns[5].text

            title = torrent_name
            watched = self.is_torrent_watched(torrent_name)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"
            title = f"{title}[CR][I][LIGHT][COLOR lightgray]{formatted_date}, {size}, {seeds} seeds[/COLOR][/LIGHT][/I]"

            list_item = xbmcgui.ListItem(label=title)
            set_torrent_art(list_item, torrent_name)

            is_folder = True
            xbmcplugin.addDirectoryItem(
                HANDLE,
                get_url(action=self.page_action, url=link["href"]),
                list_item,
                is_folder,
            )

        xbmcplugin.setPluginCategory(HANDLE, f"Torrents - {text}")
        xbmcplugin.endOfDirectory(HANDLE)

    def page(self, url):
        nyaa_url = (
            url if url.startswith("https://") else f"https://{self.hostname}{url}"
        )

        page = requests.get(nyaa_url)
        soup = BeautifulSoup(page.text, "html.parser")
        magnet = soup.find("a", class_="card-footer-item").get("href")
        torrent_name = soup.find("h3", class_="panel-title").text.strip()
        description = soup.find(id="torrent-description").text.strip()

        xbmcplugin.setPluginCategory(HANDLE, torrent_name)

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
            title = file_name

            watched = self.is_file_watched(torrent_name, file_name)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            set_torrent_art(list_item, file_name)
            list_item.setInfo(
                "video",
                {"title": title, "mediatype": "video", "plot": description},
            )
            list_item.setProperty("IsPlayable", "true")
            list_item.addContextMenuItems(
                [
                    (
                        "Toggle Watched",
                        "RunPlugin(%s)"
                        % get_url(
                            action=self.toggle_watched_action,
                            torrent_name=torrent_name,
                            file_name=file_name,
                            nyaa_url=nyaa_url,
                            watched=not watched,
                        ),
                    )
                ]
            )
            is_folder = False
            url = get_url(
                action=self.play_action,
                magnet=magnet,
                selected_file=file_name,
                name=torrent_name,
                nyaa_url=nyaa_url,
            )
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def history(self):
        xbmcplugin.setPluginCategory(HANDLE, f"Torrents - History")

        for title, data in reversed(
            self.db.database[f"{self.db_prefix}:history"].items()
        ):
            formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
            label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
            url = get_url(
                action=self.page_action,
                url=data.get("nyaa_url", False),
            )
            list_item = xbmcgui.ListItem(label=label)
            set_torrent_art(list_item, title)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
