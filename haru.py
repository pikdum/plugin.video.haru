#!/usr/bin/env python3
import sys
from urllib.parse import urlencode, parse_qsl
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import requests
import resolveurl
import re
import time
import pickle
import os
import xbmcvfs
import inspect
from datetime import datetime
from bs4 import BeautifulSoup
from resolveurl.lib import kodi
from resources.lib.database import Database

routes = {}


def log(x):
    xbmc.log("[HARU] " + str(x), xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f


_URL = sys.argv[0]
_HANDLE = int(sys.argv[1])

TZ = time.localtime().tm_gmtoff / 60 / 60
VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))

db = Database()


def set_watched(name, watched=True):
    split = name.split(" - ")
    episode = split[-1]
    show = " - ".join(split[:-1])

    if watched == "False":
        del db.database["sp:watch"][show][episode]
        if not db.database["sp:watch"][show]:
            del db.database["sp:watch"][show]
        db.commit()
        return

    if "sp:watch" not in db.database:
        db.database["sp:watch"] = {}

    if show not in db.database["sp:watch"]:
        db.database["sp:watch"][show] = {}

    db.database["sp:watch"][show][episode] = True
    db.commit()


def is_show_watched(name):
    return name in db.database["sp:watch"]


def is_episode_watched(name):
    split = name.split(" - ")
    episode = split[-1]
    show = " - ".join(split[:-1])

    if show not in db.database["sp:watch"]:
        return False
    if episode in db.database["sp:watch"][show]:
        return True
    return False


def main_menu():
    xbmcplugin.setPluginCategory(_HANDLE, "Main Menu")
    xbmcplugin.setContent(_HANDLE, "videos")

    list_item = xbmcgui.ListItem(label="SubsPlease - All")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        _HANDLE, get_url(action="subsplease_all"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="SubsPlease - Airing")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        _HANDLE, get_url(action="subsplease_airing"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="ResolveURL Settings")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        _HANDLE, get_url(action="resolveurl_settings"), list_item, is_folder
    )

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_all():
    xbmcplugin.setPluginCategory(_HANDLE, "SubsPlease - All")

    page = requests.get("https://subsplease.org/shows/")
    soup = BeautifulSoup(page.text, "html.parser")
    links = filter(lambda x: x["href"].startswith("/shows/"), soup.find_all("a"))

    for link in links:
        title = link["title"]

        watched = is_show_watched(title)
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=title)
        is_folder = True
        url = get_url(
            action="subsplease_show", url="https://subsplease.org" + link["href"]
        )
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_show(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    sid = soup.find(id="show-release-table")["sid"]
    show_title = soup.find("h1", class_="entry-title").text
    artwork_url = "https://subsplease.org" + soup.find("img")["src"]

    xbmcplugin.setPluginCategory(_HANDLE, show_title)

    episodes = requests.get(
        f"https://subsplease.org/api/?f=show&tz={TZ}&sid={sid}"
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
                artwork_url=artwork_url,
            )
            list_item.setArt({"poster": artwork_url})
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    if episodes["episode"]:
        for episode, episode_info in reversed(episodes["episode"].items()):
            release_date = re.sub(r" \d{2}:.*$", "", episode_info["release_date"])

            display_name = re.sub(r"v\d$", "", episode)
            title = f"{display_name} [I][LIGHT]— {release_date}[/LIGHT][/I]"

            watched = is_episode_watched(display_name)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo(
                "video",
                {"title": title, "genre": "Anime", "mediatype": "video"},
            )
            list_item.setProperty("IsPlayable", "true")
            list_item.setArt({"poster": artwork_url})
            list_item.addContextMenuItems(
                [
                    (
                        "Toggle Watched",
                        "RunPlugin(%s)"
                        % get_url(
                            action="toggle_watched",
                            name=display_name,
                            watched=not watched,
                        ),
                    )
                ]
            )
            hq_download = episode_info["downloads"][-1]
            is_folder = False
            url = get_url(
                action="play_nyaa", url=hq_download["torrent"], name=display_name
            )
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_batch(batch, batch_torrent, artwork_url):
    xbmcplugin.setPluginCategory(_HANDLE, batch)

    page = requests.get(batch_torrent.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")

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
        title = file_name.replace("[SubsPlease] ", "")
        title = re.sub(r"(v\d)? \(.*p\) \[.*\]\..*", "", title)

        watched = is_episode_watched(title)
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
        list_item.setArt({"poster": artwork_url})
        list_item.addContextMenuItems(
            [
                (
                    "Toggle Watched",
                    "RunPlugin(%s)"
                    % get_url(
                        action="toggle_watched",
                        name=title,
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
            name=title,
        )
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_airing():
    xbmcplugin.setPluginCategory(_HANDLE, "SubsPlease - Airing")

    list_item = xbmcgui.ListItem(label="All")
    url = get_url(action="subsplease_all_airing")
    is_folder = True
    xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

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
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_all_airing():
    xbmcplugin.setPluginCategory(_HANDLE, f"SubsPlease - All Airing")

    schedule = requests.get(f"https://subsplease.org/api/?f=schedule&tz={TZ}").json()[
        "schedule"
    ]

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

        title = f"""{show["title"]} [I][LIGHT]— {show["day"]} @ {formatted_time}[/LIGHT][/I]"""

        watched = is_show_watched(show["title"])
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=title)
        list_item.setArt({"poster": artwork_url})
        url = get_url(
            action="subsplease_show", url="https://subsplease.org/shows/" + show["page"]
        )
        is_folder = True
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


@register
def subsplease_day(day):
    xbmcplugin.setPluginCategory(_HANDLE, f"SubsPlease - {day}")

    if day == "Today":
        schedule = requests.get(
            f"https://subsplease.org/api/?f=schedule&h=true&tz={TZ}"
        ).json()["schedule"]
    else:
        schedule = requests.get(
            f"https://subsplease.org/api/?f=schedule&tz={TZ}"
        ).json()["schedule"][day]

    for show in schedule:
        # workaround: https://forum.kodi.tv/showthread.php?pid=1214507#pid1214507
        formatted_time = datetime(
            *(time.strptime(show["time"], "%H:%M")[0:6])
        ).strftime("%I:%M %p")
        artwork_url = "https://subsplease.org" + show["image_url"]

        title = f"""[B]{formatted_time}[/B] - {show["title"]}"""

        watched = is_show_watched(show["title"])
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=title)
        list_item.setArt({"poster": artwork_url})
        url = get_url(
            action="subsplease_show", url="https://subsplease.org/shows/" + show["page"]
        )
        is_folder = True
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


def get_nyaa_magnet(url):
    page = requests.get(url.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")
    return magnet


@register
def play_nyaa(name, selected_file=None, url=None, magnet=None):
    set_watched(name)
    # allow passing magnet instead of url if already handy
    if url:
        magnet = get_nyaa_magnet(url)
    # single video
    if not selected_file:
        resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
    # batch
    else:
        all_urls = resolveurl.resolve(magnet, return_all=True)
        selected_url = next(filter(lambda x: x["name"] == selected_file, all_urls))[
            "link"
        ]
        resolved_url = resolveurl.resolve(selected_url)
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


@register
def resolveurl_settings():
    resolveurl.display_settings()


@register
def toggle_watched(name, watched):
    set_watched(name, watched)
    xbmc.executebuiltin("Container.Refresh")


def router(paramstring):
    params = dict(parse_qsl(paramstring))

    if params:
        if routes[params["action"]]:
            route = routes[params["action"]]
            filtered_args = {k: v for (k, v) in params.items() if k in route["args"]}
            route["function"](**filtered_args)
        else:
            raise ValueError("Invalid paramstring: {}!".format(paramstring))
    else:
        main_menu()


if __name__ == "__main__":
    router(sys.argv[2][1:])
