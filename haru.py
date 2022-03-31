#!/usr/bin/env python3
import sys
from urllib.parse import parse_qsl
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
from resources.lib.subsplease import SubsPlease
from resources.lib.util import *

routes = {}


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f


db = Database()
subsplease = SubsPlease(db)


def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Main Menu")
    xbmcplugin.setContent(HANDLE, "videos")

    list_item = xbmcgui.ListItem(label="SubsPlease - All")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="subsplease_all"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="SubsPlease - Airing")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="subsplease_airing"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="ResolveURL Settings")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="resolveurl_settings"), list_item, is_folder
    )

    xbmcplugin.endOfDirectory(HANDLE)


@register
def subsplease_all():
    return subsplease.all()


@register
def subsplease_show(url):
    return subsplease.show(**locals())


@register
def subsplease_batch(batch, batch_torrent, artwork_url):
    return subsplease.batch(**locals())


@register
def subsplease_airing():
    return subsplease.airing()


@register
def subsplease_all_airing():
    return subsplease.all_airing()


@register
def subsplease_day(day):
    return subsplease.day(**locals())


def get_nyaa_magnet(url):
    page = requests.get(url.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")
    return magnet


@register
def play_nyaa(name, selected_file=None, url=None, magnet=None):
    subsplease.set_watched(name)
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
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)


@register
def resolveurl_settings():
    resolveurl.display_settings()


@register
def toggle_watched(name, watched):
    subsplease.set_watched(name, watched)
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
