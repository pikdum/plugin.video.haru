#!/usr/bin/env python3
import xbmc
import xbmcgui
import xbmcplugin
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
from resources.lib.util import *


class Nyaa:
    def __init__(self, db):
        self.db = db

    def set_watched(self, torrent_name, file_name, watched=True):

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

            title = torrent_name
            watched = self.is_torrent_watched(torrent_name)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            is_folder = True
            xbmcplugin.addDirectoryItem(
                HANDLE,
                get_url(action="nyaa_page", url=link["href"]),
                list_item,
                is_folder,
            )

        xbmcplugin.setPluginCategory(HANDLE, f"Search Nyaa - {text}")
        xbmcplugin.endOfDirectory(HANDLE)

    def page(self, url):
        xbmcplugin.setPluginCategory(HANDLE, "Search Results")

        page = requests.get(f"https://nyaa.si{url}")
        soup = BeautifulSoup(page.text, "html.parser")
        magnet = soup.find("a", class_="card-footer-item").get("href")
        torrent_name = soup.find("h3", class_="panel-title").text.strip()

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
                {
                    "title": title,
                    "mediatype": "video",
                },
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
            )
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)
