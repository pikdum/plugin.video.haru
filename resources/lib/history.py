#!/usr/bin/env python3
from calendar import month_name

import xbmcgui

from resources.lib.util import get_url, set_icon_art


def format_history_count(count):
    noun = "entry" if count == 1 else "entries"
    return f"{count} {noun}"


class HistoryArchive:
    def __init__(self, history):
        self.entries = sorted(
            history.items(), key=lambda item: item[1]["timestamp"], reverse=True
        )

    def total_count(self):
        return len(self.entries)

    def normalize_year(self, year):
        try:
            return int(year)
        except (TypeError, ValueError):
            return None

    def normalize_month(self, month):
        try:
            parsed = int(month)
        except (TypeError, ValueError):
            return None

        if 1 <= parsed <= 12:
            return parsed
        return None

    def is_full_view(self, full):
        return str(full).lower() == "true"

    def get_years(self):
        counts = {}

        for _, data in self.entries:
            year = data["timestamp"].year
            counts[year] = counts.get(year, 0) + 1

        return [(year, counts[year]) for year in sorted(counts, reverse=True)]

    def get_months(self, year):
        year = self.normalize_year(year)
        if year is None:
            return []

        counts = {}

        for _, data in self.entries:
            timestamp = data["timestamp"]
            if timestamp.year != year:
                continue
            counts[timestamp.month] = counts.get(timestamp.month, 0) + 1

        return [
            (month, month_name[month], counts[month])
            for month in sorted(counts, reverse=True)
        ]

    def get_entries(self, year=None, month=None):
        year = self.normalize_year(year)
        month = self.normalize_month(month)

        if month is not None and year is None:
            return []

        filtered_entries = []
        for item in self.entries:
            timestamp = item[1]["timestamp"]

            if year is not None and timestamp.year != year:
                continue

            if month is not None and timestamp.month != month:
                continue

            filtered_entries.append(item)

        return filtered_entries


def build_history_directory(
    archive,
    action,
    category,
    render_entries,
    year=None,
    month=None,
    full=False,
):
    year = archive.normalize_year(year)
    month = archive.normalize_month(month)
    full = archive.is_full_view(full)

    if month is not None and year is not None:
        return (
            f"{category} - {year} - {month:02d}",
            render_entries(archive.get_entries(year=year, month=month)),
        )

    if year is not None and full:
        return (
            f"{category} - {year}",
            render_entries(archive.get_entries(year=year)),
        )

    if year is not None:
        year_entries = archive.get_entries(year=year)
        items = [
            (
                get_url(action=action, year=year, full=True),
                set_icon_art(
                    xbmcgui.ListItem(
                        label=(
                            f"[B]All {year}[/B] "
                            f"[I][LIGHT]— {format_history_count(len(year_entries))}[/LIGHT][/I]"
                        )
                    ),
                    "video-playlist",
                ),
                True,
            )
        ]

        for month_number, label, count in archive.get_months(year):
            items.append(
                (
                    get_url(action=action, year=year, month=f"{month_number:02d}"),
                    set_icon_art(
                        xbmcgui.ListItem(
                            label=(
                                f"{month_number:02d} - {label} "
                                f"[I][LIGHT]— {format_history_count(count)}[/LIGHT][/I]"
                            )
                        ),
                        "calendar",
                    ),
                    True,
                )
            )

        return f"{category} - {year}", items

    if full:
        return category, render_entries(archive.get_entries())

    items = []
    if archive.total_count():
        items.append(
            (
                get_url(action=action, full=True),
                set_icon_art(
                    xbmcgui.ListItem(
                        label=(
                            "[B]All[/B] "
                            f"[I][LIGHT]— {format_history_count(archive.total_count())}[/LIGHT][/I]"
                        )
                    ),
                    "video-playlist",
                ),
                True,
            )
        )

    for history_year, count in archive.get_years():
        items.append(
            (
                get_url(action=action, year=history_year),
                set_icon_art(
                    xbmcgui.ListItem(
                        label=(
                            f"{history_year} "
                            f"[I][LIGHT]— {format_history_count(count)}[/LIGHT][/I]"
                        )
                    ),
                    "calendar",
                ),
                True,
            )
        )

    return category, items
