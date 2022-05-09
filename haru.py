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
from resources.lib.nyaa import Nyaa
from resources.lib.util import *

routes = {}


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f


db = Database()
subsplease = SubsPlease(db)
nyaa = Nyaa(db)


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

    list_item = xbmcgui.ListItem(label="SubsPlease - History")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="subsplease_history"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Torrents - Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="nyaa_search"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Torrents - History")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="nyaa_history"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="ResolveURL Settings")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="resolveurl_settings"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Set Language Invoker")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="toggle_language_invoker"), list_item, is_folder
    )

    xbmcplugin.endOfDirectory(HANDLE)


@register
def subsplease_all():
    return subsplease.all()


@register
def subsplease_show(url):
    return subsplease.show(**locals())


@register
def subsplease_batch(batch, batch_torrent):
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


@register
def subsplease_history():
    return subsplease.history()


def get_nyaa_magnet(url):
    page = requests.get(url.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")
    return magnet


def _play_nyaa(selected_file=None, url=None, magnet=None):
    # allow passing magnet instead of url if already handy
    if url:
        magnet = get_nyaa_magnet(url)
    # single video
    if not selected_file:
        resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
    # batch
    else:
        all_urls = resolveurl.resolve(magnet, return_all=True)
        selected_url = next(filter(lambda x: selected_file in x["name"], all_urls))[
            "link"
        ]
        resolved_url = resolveurl.resolve(selected_url)
    play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)


@register
def play_subsplease(name, selected_file=None, url=None, magnet=None):
    subsplease.set_watched(name)
    return _play_nyaa(selected_file, url, magnet)


@register
def play_nyaa(name, selected_file, nyaa_url, magnet):
    nyaa.set_watched(torrent_name=name, file_name=selected_file, nyaa_url=nyaa_url)
    return _play_nyaa(selected_file=selected_file, magnet=magnet)


@register
def resolveurl_settings():
    resolveurl.display_settings()


@register
def toggle_watched_subsplease(name, watched):
    subsplease.set_watched(name, watched)
    xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_subsplease():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["sp:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


@register
def nyaa_search():
    nyaa.search()


@register
def nyaa_page(url):
    nyaa.page(url)


@register
def nyaa_history():
    nyaa.history()


@register
def toggle_watched_nyaa(torrent_name, file_name, nyaa_url, watched):
    nyaa.set_watched(torrent_name, file_name, nyaa_url, watched)
    xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_nyaa():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["nt:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


@register
def toggle_language_invoker():
    import xml.etree.ElementTree as ET

    addon_xml = db.addon_xml_path
    tree = ET.parse(addon_xml)
    root = tree.getroot()

    current_value = ""
    for item in root.iter("reuselanguageinvoker"):
        current_value = item.text
        break

    new_value = "false" if current_value == "true" else "true"

    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Toggle Reuse Language Invoker",
        f"This is currently '{current_value}', do you want to change to '{new_value}'?\n\nThis should be set to 'true' for performance, unless you run into issues.",
    )
    if confirmed:
        for item in root.iter("reuselanguageinvoker"):
            item.text = new_value
            tree.write(addon_xml)
            break

        dialog.ok("Success!", "Your profile will now be reloaded.")
        xbmc.executebuiltin("LoadProfile(%s)" % xbmc.getInfoLabel("system.profilename"))


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
