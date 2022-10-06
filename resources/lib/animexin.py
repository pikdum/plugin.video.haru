#!/usr/bin/env python3
import requests
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup
from resources.lib.util import *


class AnimeXin:
    def all(self):
        xbmcplugin.setPluginCategory(HANDLE, "AnimeXin - All")

        page = requests.get("https://animexin.xyz/anime/list-mode/")
        soup = BeautifulSoup(page.text, "html.parser")
        links = soup.find("div", class_="soralist").find_all("a")
        links = filter(lambda x: x.get("href"), links)

        for link in links:
            title = link.text

            list_item = xbmcgui.ListItem(label=title)
            is_folder = True
            url = get_url(action="animexin_show", url=link["href"])
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def show(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        show_title = soup.find("h1", class_="entry-title").text

        xbmcplugin.setPluginCategory(HANDLE, show_title)

        episodes = soup.find("div", class_="eplister").find_all("a")

        for e in reversed(episodes):
            episode_title = e.find("div", class_="epl-title").text
            release_date = e.find("div", class_="epl-date").text
            episode_url = e.get("href")

            title = f"{episode_title} [I][LIGHT]— {release_date}[/LIGHT][/I]"
            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo(
                "video",
                {"title": title, "genre": "Anime", "mediatype": "video"},
            )
            list_item.setProperty("IsPlayable", "true")
            is_folder = False
            url = get_url(action="play_animexin", url=episode_url)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)

    def get_video_url(self, episode_url):
        page = requests.get(episode_url)
        soup = BeautifulSoup(page.text, "html.parser")
        url = soup.find("iframe")["src"]
        if url.startswith("//"):
            url = "https:" + url
        return url

    def get_subtitle_urls(self, video_url):
        subtitle_urls = []
        if "dailymotion" in video_url:
            video_id = video_url.split("?")[0].split("/")[-1]
            metadata = requests.get(
                f"https://www.dailymotion.com/player/metadata/video/{video_id}"
            ).json()
            for k, v in metadata["subtitles"]["data"].items():
                subtitle_urls += v["urls"]
        return subtitle_urls
