#!/usr/bin/env python3
import inspect
import os
import shutil
import sys
import unicodedata
from urllib.parse import parse_qsl, quote_plus

import requests
import resolveurl
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
from bs4 import BeautifulSoup

from resources.lib.database import Database
from resources.lib.nyaa import Nyaa
from resources.lib.subsplease import SubsPlease
from resources.lib.util import (
    HANDLE,
    get_setting,
    get_url,
    log,
    open_settings,
    set_addon_art,
    set_icon_art,
)

routes = {}


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f


db = Database()
subsplease = SubsPlease(db)
nyaa = Nyaa(db, mode="fun")
sukebei = Nyaa(db, mode="fap")


def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Main Menu")

    items = [
        {"action": "subsplease_menu", "label": "SubsPlease", "icon": "cinema---v2"},
        {
            "action": "nyaa_menu",
            "label": "Torrents",
            "icon": "torrent",
        },
        {"action": "settings", "label": "Settings", "icon": "settings"},
    ]

    if get_setting("sukebei_enabled") == "true":
        items.insert(
            2, {"action": "sukebei_menu", "label": "Sukebei", "icon": "jackhammer"}
        )

    xbmcplugin.addDirectoryItems(
        HANDLE,
        [
            (
                get_url(action=item["action"]),
                set_icon_art(xbmcgui.ListItem(item["label"]), item["icon"]),
                True,
            )
            for item in items
        ],
    )
    xbmcplugin.endOfDirectory(HANDLE)


@register
def subsplease_menu():
    xbmcplugin.setPluginCategory(HANDLE, "SubsPlease")
    xbmcplugin.addDirectoryItems(
        HANDLE,
        [
            (
                get_url(action="subsplease_all"),
                set_icon_art(xbmcgui.ListItem("SubsPlease - All"), "video-playlist"),
                True,
            ),
            (
                get_url(action="subsplease_all", search=True),
                set_icon_art(xbmcgui.ListItem("SubsPlease - Search"), "search"),
                True,
            ),
            (
                get_url(action="subsplease_airing"),
                set_icon_art(xbmcgui.ListItem("SubsPlease - Airing"), "calendar"),
                True,
            ),
            (
                get_url(action="subsplease_unfinished"),
                set_icon_art(
                    xbmcgui.ListItem("SubsPlease - Unfinished"), "in-progress"
                ),
                True,
            ),
            (
                get_url(action="subsplease_history"),
                set_icon_art(xbmcgui.ListItem("SubsPlease - History"), "order-history"),
                True,
            ),
        ],
    )
    xbmcplugin.endOfDirectory(HANDLE)


@register
def nyaa_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Torrents")
    xbmcplugin.addDirectoryItems(
        HANDLE,
        [
            (
                get_url(action="nyaa_search"),
                set_icon_art(xbmcgui.ListItem("Torrents - Search"), "search"),
                True,
            ),
            (
                get_url(
                    action="nyaa_search_results",
                    text="",
                    category="1_2",
                    sort="id",
                    order="desc",
                ),
                set_icon_art(xbmcgui.ListItem("Torrents - Latest"), "new"),
                True,
            ),
            (
                get_url(
                    action="nyaa_search_results",
                    text="",
                    category="1_2",
                    sort="seeders",
                    order="desc",
                ),
                set_icon_art(xbmcgui.ListItem("Torrents - Popular"), "fire-element"),
                True,
            ),
            (
                get_url(action="nyaa_history"),
                set_icon_art(xbmcgui.ListItem("Torrents - History"), "order-history"),
                True,
            ),
        ],
    )
    xbmcplugin.endOfDirectory(HANDLE)


@register
def sukebei_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Sukebei")
    xbmcplugin.addDirectoryItems(
        HANDLE,
        [
            (
                get_url(action="sukebei_search"),
                set_icon_art(xbmcgui.ListItem("Sukebei - Search"), "search"),
                True,
            ),
            (
                get_url(
                    action="sukebei_search_results",
                    text="",
                    category="1_1",
                    sort="id",
                    order="desc",
                ),
                set_icon_art(xbmcgui.ListItem("Sukebei - Latest"), "new"),
                True,
            ),
            (
                get_url(
                    action="sukebei_search_results",
                    text="",
                    category="1_1",
                    sort="seeders",
                    order="desc",
                ),
                set_icon_art(xbmcgui.ListItem("Sukebei - Popular"), "fire-element"),
                True,
            ),
            (
                get_url(action="sukebei_history"),
                set_icon_art(xbmcgui.ListItem("Sukebei - History"), "order-history"),
                True,
            ),
        ],
    )
    xbmcplugin.endOfDirectory(HANDLE)


@register
def settings():
    xbmcplugin.setPluginCategory(HANDLE, "Settings")

    items = [
        {
            "url": get_url(action="display_settings", plugin="plugin.video.haru"),
            "label": "haru",
            "plugin": "plugin.video.haru",
        },
        {
            "url": get_url(action="resolveurl_settings"),
            "label": "ResolveURL",
            "plugin": "script.module.resolveurl",
        },
    ]

    if xbmc.getCondVisibility("System.AddonIsEnabled(plugin.video.torrest)"):
        items.append(
            {
                "url": get_url(
                    action="display_settings", plugin="plugin.video.torrest"
                ),
                "label": "Torrest",
                "plugin": "plugin.video.torrest",
            }
        )

    if xbmc.getCondVisibility("System.AddonIsEnabled(plugin.video.elementum)"):
        items.append(
            {
                "url": get_url(
                    action="display_settings", plugin="plugin.video.elementum"
                ),
                "label": "Elementum",
                "plugin": "plugin.video.elementum",
            }
        )

    xbmcplugin.addDirectoryItems(
        HANDLE,
        [
            (
                item["url"],
                set_addon_art(xbmcgui.ListItem(item["label"]), item["plugin"]),
            )
            for item in items
        ],
    )
    xbmcplugin.endOfDirectory(HANDLE)


@register
def subsplease_all(search=False):
    return subsplease.all(**locals())


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
def subsplease_history(year=None, month=None, full=False):
    return subsplease.history(year=year, month=month, full=full)


@register
def subsplease_unfinished(airing_only=False):
    return subsplease.unfinished(**locals())


def get_nyaa_magnet(url):
    page = requests.get(url.replace("/torrent", ""))
    soup = BeautifulSoup(page.text, "html.parser")
    magnet = soup.find("a", class_="card-footer-item").get("href")
    return magnet


def _play_nyaa(selected_file=None, url=None, magnet=None):
    # allow passing magnet instead of url if already handy
    if url:
        magnet = get_nyaa_magnet(url)

    engine = get_setting("engine")
    if engine == "Torrest":
        play_item = xbmcgui.ListItem(
            path=f"plugin://plugin.video.torrest/play_magnet?magnet={quote_plus(magnet)}"
        )
    elif engine == "Elementum":
        play_item = xbmcgui.ListItem(
            path=f"plugin://plugin.video.elementum/play?uri={quote_plus(magnet)}"
        )
    elif engine == "ResolveURL":
        if not selected_file:
            resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
        else:
            all_urls = resolveurl.resolve(magnet, return_all=True)
            log(
                "resolveurl return_all for selected_file={} -> type={} value={}".format(
                    selected_file, type(all_urls).__name__, all_urls
                )
            )
            if isinstance(all_urls, str):
                # sometimes we get it already resolved as a single string?
                # this should fix: string indices must be integers, not 'str'
                resolved_url = all_urls
            elif not all_urls:
                log("resolveurl return_all empty; falling back to magnet resolve")
                resolved_url = resolveurl.resolve(magnet)
            else:

                def normalize_match_text(value, ascii_only=False):
                    if not value:
                        return ""
                    normalized = unicodedata.normalize("NFKC", value)
                    if ascii_only:
                        normalized = normalized.encode("ascii", "ignore").decode(
                            "ascii"
                        )
                    return " ".join(normalized.split()).casefold()

                selected_normalized = normalize_match_text(selected_file)
                selected_ascii = normalize_match_text(selected_file, ascii_only=True)

                entries = []
                for item in all_urls:
                    name = item.get("name", "") if isinstance(item, dict) else str(item)
                    entries.append(
                        {
                            "item": item,
                            "normalized": normalize_match_text(name),
                            "ascii": normalize_match_text(name, ascii_only=True),
                        }
                    )

                def is_exact_match(entry):
                    return (
                        entry["normalized"]
                        and selected_normalized
                        and entry["normalized"] == selected_normalized
                    ) or (
                        entry["ascii"]
                        and selected_ascii
                        and entry["ascii"] == selected_ascii
                    )

                def is_partial_match(entry):
                    return (
                        entry["normalized"]
                        and selected_normalized
                        and (
                            selected_normalized in entry["normalized"]
                            or entry["normalized"] in selected_normalized
                        )
                    ) or (
                        entry["ascii"]
                        and selected_ascii
                        and (
                            selected_ascii in entry["ascii"]
                            or entry["ascii"] in selected_ascii
                        )
                    )

                matched_entry = next(
                    (entry["item"] for entry in entries if is_exact_match(entry)),
                    None,
                )
                if not matched_entry:
                    matched_entry = next(
                        (entry["item"] for entry in entries if is_partial_match(entry)),
                        None,
                    )
                if not matched_entry:
                    log(
                        "resolveurl could not match selected_file={}; normalized={} ascii={}; using first entry".format(
                            selected_file, selected_normalized, selected_ascii
                        )
                    )
                    matched_entry = all_urls[0]
                if isinstance(matched_entry, dict):
                    selected_url = matched_entry.get("link")
                else:
                    selected_url = matched_entry
                if not selected_url:
                    log(
                        "resolveurl selected_url missing; falling back to magnet resolve"
                    )
                    resolved_url = resolveurl.resolve(magnet)
                else:
                    resolved_url = resolveurl.resolve(selected_url)
        if not resolved_url:
            raise RuntimeError("Provider returned an invalid stream URL")
        if not isinstance(resolved_url, str):
            raise TypeError(
                "Provider returned a non-string stream URL: {} {!r}".format(
                    type(resolved_url).__name__, resolved_url
                )
            )
        play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)


@register
def play_subsplease(name, selected_file=None, url=None, magnet=None):
    _play_nyaa(selected_file, url, magnet)
    subsplease.set_watched(name)


@register
def play_nyaa(name, selected_file, nyaa_url, magnet):
    _play_nyaa(selected_file=selected_file, magnet=magnet)
    nyaa.set_watched(torrent_name=name, file_name=selected_file, nyaa_url=nyaa_url)


@register
def play_sukebei(name, selected_file, nyaa_url, magnet):
    _play_nyaa(selected_file=selected_file, magnet=magnet)
    sukebei.set_watched(torrent_name=name, file_name=selected_file, nyaa_url=nyaa_url)


@register
def resolveurl_settings():
    resolveurl.display_settings()


@register
def display_settings(plugin):
    open_settings(plugin)


@register
def notify(message, title="haru"):
    xbmcgui.Dialog().notification(title, message)


@register
def toggle_watched_subsplease(name, watched):
    subsplease.set_watched(name, watched)
    xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_subsplease():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear SubsPlease history?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["sp:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


@register
def nyaa_search():
    nyaa.search()


@register
def nyaa_search_results(category, sort, order, text=""):
    nyaa.search_results(category=category, text=text, sort=sort, order=order)


@register
def nyaa_page(url):
    nyaa.page(url)


@register
def nyaa_history(year=None, month=None, full=False):
    nyaa.history(year=year, month=month, full=full)


@register
def sukebei_search():
    sukebei.search()


@register
def sukebei_search_results(category, sort, order, text=""):
    sukebei.search_results(category=category, text=text, sort=sort, order=order)


@register
def sukebei_page(url):
    sukebei.page(url)


@register
def sukebei_history(year=None, month=None, full=False):
    sukebei.history(year=year, month=month, full=full)


@register
def toggle_watched_nyaa(torrent_name, file_name, nyaa_url, watched):
    nyaa.set_watched(torrent_name, file_name, nyaa_url, watched)
    xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_nyaa():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear Torrents history?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["nt:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_sukebei():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear Sukebei history?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["sb:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


@register
def toggle_watched_sukebei(torrent_name, file_name, nyaa_url, watched):
    sukebei.set_watched(torrent_name, file_name, nyaa_url, watched)
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
    if not confirmed:
        return

    for item in root.iter("reuselanguageinvoker"):
        item.text = new_value
        tree.write(addon_xml)
        break

    dialog.ok("Success!", "Your profile will now be reloaded.")
    xbmc.executebuiltin("LoadProfile(%s)" % xbmc.getInfoLabel("system.profilename"))


@register
def clear_thumbnail_cache():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear Thumbnail Cache",
        "Do you want to clear Kodi's thumbnail cache?",
    )
    if not confirmed:
        return

    thumbnail_dir = xbmcvfs.translatePath("special://thumbnails")
    for d in os.listdir(thumbnail_dir):
        shutil.rmtree(os.path.join(thumbnail_dir, d))

    dialog.ok("Success!", "You should restart Kodi now.")


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
    try:
        router(sys.argv[2][1:])
    except Exception as e:
        dialog = xbmcgui.Dialog()
        dialog.ok("Error", str(e))
        raise
