#!/usr/bin/env bash
set -euo pipefail

COMMIT_HASH="$(git log -n 2 --pretty=format:%H -- CHANGELOG.md | tail -n+2)"
CHANGES="$(diff --changed-group-format='%>' --unchanged-group-format='' <(git show "$COMMIT_HASH":CHANGELOG.md) CHANGELOG.md || true)"
CHANGES_FORMATTED="$(echo "$CHANGES" | pandoc --from markdown --to plain)"

xmlstarlet ed --inplace -u "//news" -v "$CHANGES_FORMATTED" addon.xml
