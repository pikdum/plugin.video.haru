#!/usr/bin/env python3
import sys
from urllib.parse import urlencode, parse_qsl
import xbmc
import xbmcgui
import xbmcplugin
import requests
import resolveurl
from bs4 import BeautifulSoup
from resolveurl.lib import kodi

_URL = sys.argv[0]
_HANDLE = int(sys.argv[1])

VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))


def log(x):
    xbmc.log("[HARU] " + x, xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def show_main_menu():
    xbmcplugin.setPluginCategory(_HANDLE, "Main Menu")
    xbmcplugin.setContent(_HANDLE, "videos")

    list_item = xbmcgui.ListItem(label="Subsplease - All")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        _HANDLE, get_url(action="subsplease_all"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="ResolveURL Settings")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        _HANDLE, get_url(action="resolveurl_settings"), list_item, is_folder
    )

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_subsplease_all():
    xbmcplugin.setPluginCategory(_HANDLE, "Subsplease - All")

    page = requests.get("https://subsplease.org/shows/")
    soup = BeautifulSoup(page.text, "html.parser")
    links = filter(lambda x: x["href"].startswith("/shows/"), soup.find_all("a"))

    for link in links:
        list_item = xbmcgui.ListItem(label=link["title"])
        is_folder = True
        url = get_url(
            action="subsplease_show", url="https://subsplease.org" + link["href"]
        )
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_subsplease_show(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    sid = soup.find(id="show-release-table")["sid"]
    log(f"{sid=}")
    show_title = soup.find("h1", class_="entry-title").text
    log(f"{show_title=}")

    xbmcplugin.setPluginCategory(_HANDLE, show_title)

    episodes = requests.get(
        f"https://subsplease.org/api/?f=show&tz=America/Chicago&sid={sid}"
    ).json()

    if episodes["episode"]:
        for episode, episode_info in episodes["episode"].items():
            list_item = xbmcgui.ListItem(label=episode)
            list_item.setInfo(
                "video",
                {"title": episode, "genre": "Anime", "mediatype": "video"},
            )
            list_item.setProperty("IsPlayable", "true")
            hq_download = episode_info["downloads"][-1]
            is_folder = False
            magnet = get_nyaa_magnet(hq_download["torrent"])
            url = get_url(action="play_magnet", magnet=magnet)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    if episodes["batch"]:
        for batch, batch_info in episodes["batch"].items():
            list_item = xbmcgui.ListItem(label=batch)
            hq_download = batch_info["downloads"][-1]
            is_folder = True
            url = get_url(
                action="subsplease_batch",
                batch=batch,
                batch_torrent=hq_download["torrent"],
            )
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_subsplease_batch(batch, batch_torrent):
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

    for f in file_list:
        list_item = xbmcgui.ListItem(label=f)
        list_item.setInfo(
            "video",
            {"title": f, "genre": "Anime", "mediatype": "video"},
        )
        list_item.setProperty("IsPlayable", "true")
        is_folder = False
        url = get_url(action="play_batch", magnet=magnet, selected_file=f)
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(_HANDLE)


def get_nyaa_magnet(url):
    page = requests.get(url.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")
    return magnet


def play_magnet(magnet):
    resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


def play_batch(magnet, selected_file):
    resolved_url = resolveurl.HostedMediaFile(
        url=magnet, selected_file=f"/{selected_file}"
    ).resolve()
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


def router(paramstring):
    params = dict(parse_qsl(paramstring))

    if params:
        if params["action"] == "play_magnet":
            play_magnet(params["magnet"])
        elif params["action"] == "play_batch":
            play_batch(params["magnet"], params["selected_file"])
        elif params["action"] == "subsplease_all":
            show_subsplease_all()
        elif params["action"] == "subsplease_show":
            show_subsplease_show(params["url"])
        elif params["action"] == "subsplease_batch":
            show_subsplease_batch(params["batch"], params["batch_torrent"])
        elif params["action"] == "resolveurl_settings":
            resolveurl.display_settings()
        else:
            raise ValueError("Invalid paramstring: {}!".format(paramstring))
    else:
        show_main_menu()


if __name__ == "__main__":
    router(sys.argv[2][1:])
