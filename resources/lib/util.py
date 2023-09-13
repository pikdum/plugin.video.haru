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

__addon_id = _URL.replace("plugin://", "").replace("/", "")
__settings__ = xbmcaddon.Addon(id=__addon_id)


def get_setting(name, default=None):
    value = __settings__.getSetting(name)
    if not value:
        return default

    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        return value


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
