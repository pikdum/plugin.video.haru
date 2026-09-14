#!/usr/bin/env python3
import os
import pickle

import xbmcaddon
import xbmcvfs


class Database:
    def __init__(self):
        BASE_DATABASE = {
            "sp:watch_v2": {},
            "sp:history_v2": {},
            "nt:watch": {},
            "nt:history": {},
            "sb:watch": {},
            "sb:history": {},
            "cache": {},
        }

        addon = xbmcaddon.Addon()
        data_dir = xbmcvfs.translatePath(
            os.path.join("special://profile/addon_data/", addon.getAddonInfo("id"))
        )
        database_path = os.path.join(data_dir, "database.pickle")
        xbmcvfs.mkdirs(data_dir)

        if os.path.exists(database_path):
            with open(database_path, "rb") as f:
                database = pickle.load(f)
        else:
            database = {}

        database = {**BASE_DATABASE, **database}
        database, changed = self.normalize_database(database)

        self.database = database
        self.database_path = database_path
        self.addon_xml_path = xbmcvfs.translatePath(
            os.path.join(
                "special://home/addons/", addon.getAddonInfo("id"), "addon.xml"
            )
        )

        if changed:
            self.commit()

    def normalize_database(self, database):
        changed = False

        if not isinstance(database.get("cache"), dict):
            database["cache"] = {}
            changed = True

        if "sp:art_cache" in database:
            del database["sp:art_cache"]
            changed = True

        return database, changed

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)
