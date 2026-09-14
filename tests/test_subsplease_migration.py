import unittest
from datetime import datetime

from resources.lib import subsplease_migration as migration

CATALOG = [
    {
        "id": 1,
        "title": "Zatsu Tabi – That’s Journey",
        "slug": "zatsu-tabi-thats-journey",
    },
    {"id": 2, "title": "A Very Long Light Novel Title", "slug": "iseleve"},
    {"id": 3, "title": "Lord of Mysteries", "slug": "lord-of-mysteries"},
    {
        "id": 4,
        "title": "Lord of Mysteries – Specials",
        "slug": "lord-of-mysteries-specials",
    },
]

DETAILS = {
    3: {
        "releases": [
            {"name": "Lord of Mysteries - 01"},
            {"name": "Lord of Mysteries - Chibi Theatre - 01"},
        ]
    },
    4: {"releases": [{"name": "Lord of Mysteries - Specials - 01"}]},
}

WHEN = datetime(2026, 1, 1, 12, 0)


def legacy_database():
    return {
        "sp:watch": {
            "Zatsu Tabi - That's Journey": {"01": True, "02": True},
            "Iseleve": {"01": True},
            "Lord of Mysteries": {"01": True},
            "Lord of Mysteries - Chibi Theatre": {"01": True},
            "Lord of Mysteries - Specials": {"01": True},
            "Cached Old Name": {"05": True},
            "Gone Forever": {"01": True},
        },
        "sp:history": {
            "Zatsu Tabi - That's Journey - 02": {"timestamp": WHEN},
            "Lord of Mysteries - Chibi Theatre - 01": {"timestamp": WHEN},
            "Gone Forever - 01": {"timestamp": WHEN},
        },
        "cache": {"sp": {"show": {"Cached Old Name": {"show_id": 2}}}},
    }


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.fetched = []
        self.db = legacy_database()

    def fetch_show(self, show_id):
        self.fetched.append(show_id)
        return DETAILS[show_id]

    def test_resolves_by_compact_title_slug_cache_and_release_prefix(self):
        report = migration.migrate(self.db, CATALOG, self.fetch_show)

        watch = self.db[migration.WATCH]
        self.assertEqual(sorted(watch), [1, 2, 3, 4])
        self.assertEqual(
            sorted(watch[1]["episodes"]),
            ["Zatsu Tabi - That's Journey - 01", "Zatsu Tabi - That's Journey - 02"],
        )
        # Slug match and cached id both land on show 2 and merge.
        self.assertEqual(
            sorted(watch[2]["episodes"]), ["Cached Old Name - 05", "Iseleve - 01"]
        )
        # Sub-series stay inside the main show; specials are their own show.
        self.assertEqual(
            sorted(watch[3]["episodes"]),
            ["Lord of Mysteries - 01", "Lord of Mysteries - Chibi Theatre - 01"],
        )
        self.assertEqual(
            list(watch[4]["episodes"]), ["Lord of Mysteries - Specials - 01"]
        )
        self.assertEqual(self.fetched, [3])

        self.assertEqual(report["shows"], 6)
        self.assertEqual(report["unresolved_shows"], ["Gone Forever"])

    def test_history_keeps_release_name_and_gains_show_id(self):
        migration.migrate(self.db, CATALOG, self.fetch_show)
        history = self.db[migration.HISTORY]
        self.assertEqual(
            history["Lord of Mysteries - Chibi Theatre - 01"],
            {"timestamp": WHEN, "show_id": 3},
        )
        self.assertNotIn("Gone Forever - 01", history)

    def test_unresolved_is_parked_and_legacy_keys_removed(self):
        migration.migrate(self.db, CATALOG, self.fetch_show)
        self.assertEqual(
            self.db[migration.LEGACY_BUCKET],
            {
                "watch": {"Gone Forever": {"01": True}},
                "history": {"Gone Forever - 01": {"timestamp": WHEN}},
            },
        )
        self.assertNotIn("sp:watch", self.db)
        self.assertNotIn("sp:history", self.db)
        self.assertEqual(self.db["cache"], {})
        self.assertFalse(migration.needs_migration(self.db))

    def test_second_run_is_a_no_op(self):
        migration.migrate(self.db, CATALOG, self.fetch_show)
        snapshot = dict(self.db)
        report = migration.migrate(self.db, CATALOG, self.fetch_show)
        self.assertEqual(self.db, snapshot)
        self.assertEqual(report["shows"], 0)

    def test_version_suffix_is_stripped(self):
        self.assertEqual(migration.normalize_release_name("Show - 05v2"), "Show - 05")
        self.assertEqual(migration.normalize_release_name("Show - 05"), "Show - 05")


if __name__ == "__main__":
    unittest.main()
