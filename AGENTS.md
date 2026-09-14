# Repository Guidelines

## Project Structure & Module Organization

`haru.py` is the Kodi plugin entrypoint and router. Core logic lives in `resources/lib/`, with feature modules such as `subsplease.py`, `nyaa.py`, `history.py`, `database.py`, and shared helpers in `util.py`. Static addon metadata is in `addon.xml`. Top-level assets such as `icon.png` and `fanart*.jpg` are used by Kodi. CI and automation live under `.github/workflows/`.

## Build, Test, and Development Commands

- `devenv shell` starts the project development environment.
- `devenv test` is the standard verification command after code changes. It runs the repo’s formatting and lint checks in one step.
- `devenv shell ruff check` runs linting only.
- `devenv shell ruff format` formats Python files.

Prefer `devenv test` before finishing work, even for small edits.

## Coding Style & Naming Conventions

Use 4-space indentation and keep Python code simple and direct. Follow existing naming: modules and functions use `snake_case`, classes use `PascalCase`, and route names in `haru.py` mirror callable function names. Prefer explicit imports over `from ... import *`. Keep shared cross-feature logic in focused modules like `resources/lib/history.py` instead of growing `util.py` without need.

## Testing Guidelines

`devenv test` runs the lint and format hooks and then the unit tests in `tests/` (plain `unittest`, no Kodi required; modules under test must stay free of `xbmc*` imports, as `resources/lib/subsplease_migration.py` does). Treat it as the required post-change verification step. When changing routing, history views, or playback helpers, sanity-check the affected Kodi navigation flow as part of review. Place new tests in `tests/` and keep filenames aligned with the module under test.

## Commit & Pull Request Guidelines

Recent history follows conventional-style subjects such as `feat: history overhaul`, `fix(subsplease): ...`, and `chore: add devenv, format + lint`. Keep commit messages short, imperative, and scoped when useful. Pull requests should explain user-visible behavior changes, mention any affected providers (`SubsPlease`, `Nyaa`, `Sukebei`), and include screenshots only when UI navigation or presentation changes materially.
