#!/usr/bin/env bash
set -euo pipefail

COMMIT_HASH="$(git log -n 2 --pretty=format:%H -- CHANGELOG.md | tail -n+2)"
CHANGES="$(diff --changed-group-format='%>' --unchanged-group-format='' <(git show "$COMMIT_HASH":CHANGELOG.md) CHANGELOG.md || true)"

xmlstarlet ed --inplace -u "//news" -v "$CHANGES" addon.xml
