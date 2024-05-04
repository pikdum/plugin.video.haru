#!/usr/bin/env bash
NEWS="$(pandoc --from markdown --to plain CHANGELOG.md | tail -n+3 | head -c 1000 && printf '...')"
xmlstarlet ed --inplace -u "//news" -v "$NEWS" addon.xml
