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
    def __init__(self, db):
        self.db = db

    def set_watched(self, torrent_name, file_name, nyaa_url, watched=True):
        if watched == "False":
            del self.db.database["nt:watch"][torrent_name][file_name]
            if self.db.database["nt:history"].get(file_name, None):
                del self.db.database["nt:history"][file_name]
            if not self.db.database["nt:watch"][torrent_name]:
                del self.db.database["nt:watch"][torrent_name]
            self.db.commit()
            return

        if "nt:watch" not in self.db.database:
            self.db.database["nt:watch"] = {}

        if torrent_name not in self.db.database["nt:watch"]:
            self.db.database["nt:watch"][torrent_name] = {}

        self.db.database["nt:history"][file_name] = {
            "timestamp": datetime.now(),
            "torrent_name": torrent_name,
            "nyaa_url": nyaa_url,
        }

        self.db.database["nt:watch"][torrent_name][file_name] = True
        self.db.commit()

    def is_file_watched(self, torrent_name, file_name):
        return self.db.database["nt:watch"].get(torrent_name, {}).get(file_name, False)

    def is_torrent_watched(self, torrent_name):
        return self.db.database["nt:watch"].get(torrent_name, False)

    def search(self):
        keyboard = xbmc.Keyboard("", "Search for torrents:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            return

        escaped = quote(text)
        page = requests.get(f"https://nyaa.si/?f=0&c=1_2&q={escaped}&s=seeders&o=desc")
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
            is_folder = True
            xbmcplugin.addDirectoryItem(
                HANDLE,
                get_url(action="nyaa_page", url=link["href"]),
                list_item,
                is_folder,
            )

        xbmcplugin.setPluginCategory(HANDLE, f"Torrents - {text}")
        xbmcplugin.endOfDirectory(HANDLE)

    def page(self, url):
        nyaa_url = url if url.startswith("https://") else f"https://nyaa.si{url}"

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
                            action="toggle_watched_nyaa",
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
                action="play_nyaa",
                magnet=magnet,
                selected_file=file_name,
                name=torrent_name,
                nyaa_url=nyaa_url,
            )
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def history(self):
        xbmcplugin.setPluginCategory(HANDLE, f"Torrents - History")

        list_item = xbmcgui.ListItem(label="Clear History")
        xbmcplugin.addDirectoryItem(
            HANDLE, get_url(action="clear_history_nyaa"), list_item
        )

        for title, data in reversed(self.db.database["nt:history"].items()):
            formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
            label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
            url = get_url(
                action="nyaa_page",
                url=data.get("nyaa_url", False),
            )
            list_item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
