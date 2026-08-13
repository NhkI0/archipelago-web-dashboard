"""
Hall of Fame — host-droppable images + a small TOML manifest, no rebuild needed.

A host drops image files into ``hall_of_fame_dir`` (see config.toml) alongside
an ``entries.toml`` describing them:

    [[entries]]
    file = "some-drawing.png"
    artist = "Name"
    date = "2026-04-20"
    title = "Optional caption"

The directory is served statically at /hall-of-fame/<file>; /api/hall_of_fame
returns the parsed entries. A missing manifest is treated as "no entries yet",
not an error — the folder may legitimately be empty. A malformed one is loud,
same as a bad config.toml, since it silently dropping entries would be
confusing.
"""

from __future__ import annotations

import logging
import pathlib
import tomllib
from typing import Any

log = logging.getLogger("ap.hall_of_fame")


def load_entries(directory: pathlib.Path) -> list[dict[str, Any]]:
    manifest = directory / "entries.toml"
    if not manifest.is_file():
        return []
    try:
        with open(manifest, "rb") as fp:
            data = tomllib.load(fp)
    except (OSError, tomllib.TOMLDecodeError) as e:
        log.error("=" * 78)
        log.error("COULD NOT PARSE %s, HALL OF FAME WILL BE EMPTY", manifest)
        log.error("Reason: %s", e)
        log.error("=" * 78)
        return []

    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return []

    entries: list[dict[str, Any]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        file = str(raw.get("file", "")).strip()
        if not file:
            continue
        if not (directory / file).is_file():
            log.warning("hall of fame entry %r has no matching file in %s; skipping", file, directory)
            continue
        entries.append({
            "file": file,
            "artist": str(raw.get("artist", "")).strip() or "Unknown",
            "date": str(raw.get("date", "")).strip(),
            "title": str(raw.get("title", "")).strip() or None,
        })
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries
