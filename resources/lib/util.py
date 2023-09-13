#!/usr/bin/env python3
import re
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
    log(artwork_url)
    if artwork_url:
        list_item.setArt({"poster": artwork_url, "thumb": artwork_url})


def slugify(text):
    # lowercase
    text = text.lower()
    # strip bbcode
    text = re.sub(r"\[.*?\]", "", text)
    # remove parens
    text = text.replace("(", "").replace(")", "")
    # remove apostrophes of all sorts
    text = text.replace("'", "").replace("’", "")
    # remove whatever this is
    text = text.replace("+", "").replace("@", "")
    # replace non-alphanumeric with dashes
    text = re.sub(r"[^a-zA-Z0-9_]+", "-", text)
    # strip leading and trailing dashes
    text = text.strip("-")
    log(text)

    return text


def slugify_torrent(text):
    pattern = r"\[(.+)?\] (.+?) (S\d* )?- (\d+)"
    match = re.match(pattern, text)
    if match:
        print(match)
        return slugify(match.group(2))
    else:
        return None


def open_settings(addon_id):
    xbmcaddon.Addon(id=addon_id).openSettings()
