#!/usr/bin/env python3
import re
import sys
from urllib.parse import urlencode, quote

import xbmc
import xbmcaddon
import xbmcgui
from resolveurl.lib import kodi

_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))
MONA_URL = "https://wild-fire-3987.fly.dev"


def get_setting(setting, default=None):
    return xbmcaddon.Addon(id="plugin.video.haru").getSetting(setting) or default


def log(x):
    xbmc.log("[HARU] " + str(x), xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def set_show_art(list_item, title):
    poster = f"{MONA_URL}/poster/show/{quote(title)}"
    fanart = f"{MONA_URL}/fanart/show/{quote(title)}"
    list_item.setArt({"poster": poster, "thumb": poster, "fanart": fanart})


def set_torrent_art(list_item, name):
    pattern = r"\[(.+)?\] (.+?) (S\d* )?- (\d+)"
    match = re.match(pattern, name)
    if match and match.group(2):
        set_show_art(list_item, match.group(2))


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
    return text


def open_settings(addon_id):
    xbmcaddon.Addon(id=addon_id).openSettings()
