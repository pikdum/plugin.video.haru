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
from datetime import datetime
from bs4 import BeautifulSoup
from resolveurl.lib import kodi


def log(x):
    xbmc.log("[HARU] " + x, xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


_URL = sys.argv[0]
_HANDLE = int(sys.argv[1])

VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))
BASE_DATABASE = {"sp:watch": {}}

addon = xbmcaddon.Addon()
data_dir = xbmcvfs.translatePath(
    os.path.join("special://profile/addon_data/", addon.getAddonInfo("id"))
)
database_path = os.path.join(data_dir, "database.pickle")
xbmcvfs.mkdirs(data_dir)


def commit():
    with open(database_path, "wb") as f:
        pickle.dump(database, f)


if os.path.exists(database_path):
    with open(database_path, "rb") as f:
        database = pickle.load(f)
else:
    database = {}

database = {**BASE_DATABASE, **database}

# TODO: clean this up
def set_watched(name, watched=True):
    split = name.split(" - ")
    episode = split[-1]
    show = " - ".join(split[:-1])

    if watched == "False":
        del database["sp:watch"][show][episode]
        if not database["sp:watch"][show]:
            del database["sp:watch"][show]
        commit()
        return

    if "sp:watch" not in database:
        database["sp:watch"] = {}

    if show not in database["sp:watch"]:
        database["sp:watch"][show] = {}

    database["sp:watch"][show][episode] = True
    commit()


def is_show_watched(name):
    return name in database["sp:watch"]


def is_episode_watched(name):
    split = name.split(" - ")
    episode = split[-1]
    show = " - ".join(split[:-1])

    if show not in database["sp:watch"]:
        return False
    if episode in database["sp:watch"][show]:
        return True
    return False


def show_main_menu():
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


def show_subsplease_all():
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


def show_subsplease_show(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    sid = soup.find(id="show-release-table")["sid"]
    show_title = soup.find("h1", class_="entry-title").text
    artwork_url = "https://subsplease.org" + soup.find("img")["src"]

    xbmcplugin.setPluginCategory(_HANDLE, show_title)

    episodes = requests.get(
        f"https://subsplease.org/api/?f=show&tz=America/Chicago&sid={sid}"
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
            magnet = get_nyaa_magnet(hq_download["torrent"])
            url = get_url(action="play_magnet", magnet=magnet, name=display_name)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


def show_subsplease_batch(batch, batch_torrent, artwork_url):
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
        display_name = file_name.replace("[SubsPlease] ", "")
        display_name = re.sub(r"(v\d)? \(.*p\) \[.*\]\..*", "", display_name)
        title = display_name

        watched = is_episode_watched(display_name)
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        list_item = xbmcgui.ListItem(label=display_name)
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
                        name=display_name,
                        watched=not watched,
                    ),
                )
            ]
        )
        is_folder = False
        url = get_url(
            action="play_batch",
            magnet=magnet,
            selected_file=file_name,
            name=display_name,
        )
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_HANDLE)


def show_subsplease_airing():
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


def show_subsplease_all_airing():
    xbmcplugin.setPluginCategory(_HANDLE, f"SubsPlease - All Airing")

    schedule = requests.get(
        "https://subsplease.org/api/?f=schedule&tz=America/Chicago"
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


def show_subsplease_day(day):
    xbmcplugin.setPluginCategory(_HANDLE, f"SubsPlease - {day}")

    if day == "Today":
        schedule = requests.get(
            "https://subsplease.org/api/?f=schedule&h=true&tz=America/Chicago"
        ).json()["schedule"]
    else:
        schedule = requests.get(
            "https://subsplease.org/api/?f=schedule&tz=America/Chicago"
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


def play_magnet(magnet, name):
    set_watched(name)
    resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


def play_batch(magnet, selected_file, name):
    set_watched(name)
    resolved_urls = resolveurl.resolve(magnet, resolve_all=True)
    resolved_url = next(filter(lambda x: x["name"] == selected_file, resolved_urls))[
        "link"
    ]
    if resolveurl.HostedMediaFile(resolved_url):
        resolved_url = resolveurl.resolve(resolved_url)
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


def router(paramstring):
    params = dict(parse_qsl(paramstring))

    if params:
        if params["action"] == "play_magnet":
            play_magnet(params["magnet"], params["name"])
        elif params["action"] == "play_batch":
            play_batch(params["magnet"], params["selected_file"], params["name"])
        elif params["action"] == "subsplease_all":
            show_subsplease_all()
        elif params["action"] == "subsplease_airing":
            show_subsplease_airing()
        elif params["action"] == "subsplease_all_airing":
            show_subsplease_all_airing()
        elif params["action"] == "subsplease_day":
            show_subsplease_day(params["day"])
        elif params["action"] == "subsplease_show":
            show_subsplease_show(params["url"])
        elif params["action"] == "subsplease_batch":
            show_subsplease_batch(
                params["batch"], params["batch_torrent"], params["artwork_url"]
            )
        elif params["action"] == "toggle_watched":
            set_watched(params["name"], watched=params["watched"])
            xbmc.executebuiltin("Container.Refresh")
        elif params["action"] == "resolveurl_settings":
            resolveurl.display_settings()
        else:
            raise ValueError("Invalid paramstring: {}!".format(paramstring))
    else:
        show_main_menu()


if __name__ == "__main__":
    router(sys.argv[2][1:])
