#!/usr/bin/env python3
import sys
from urllib.parse import urlencode

import xbmc
import xbmcaddon
import xbmcgui
from resolveurl.lib import kodi

_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))


def get_setting(setting, default=None):
    return xbmcaddon.Addon(id="plugin.video.haru").getSetting(setting) or default


def log(x):
    xbmc.log("[HARU] " + str(x), xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def set_art(list_item, artwork_url):
    if artwork_url:
        list_item.setArt({"poster": artwork_url, "thumb": artwork_url})


def slugify(text):
    return (
        text.lower()
        .replace(" ", "-")
        .replace(",", "")
        .replace("!", "")
        .replace("+", "")
    )


def open_settings(addon_id):
    xbmcaddon.Addon(id=addon_id).openSettings()
