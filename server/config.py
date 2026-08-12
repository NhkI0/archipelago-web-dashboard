"""
Host configuration — the single ``config.toml`` a host edits to control the site.

Parsed with the stdlib :mod:`tomllib` (Python 3.11+), so there is no extra
dependency. A missing or partial file still boots: whatever the host provides is
deep-merged over :data:`DEFAULTS`. Environment variables continue to override
the resolved values in ``main.py`` for backward compatibility with the existing
VPS/tmux deploy (``scripts/start.sh`` and ``.github/workflows/deploy.yml``).

Only the subset returned by :func:`public_config` is ever sent to browsers —
the AP password and filesystem paths never leave the backend.
"""

from __future__ import annotations

import copy
import logging
import os
import pathlib
import tomllib
from typing import Any

log = logging.getLogger("ap.config")

DEFAULTS: dict[str, Any] = {
    "server": {
        "ap_host": "localhost",
        "ap_port": 38281,
        # Folder scanned for the newest *.archipelago, or a direct file path.
        "multiworld_dir": "./multiworld",
        "web_port": 8080,
        "bind": "127.0.0.1",   # use "0.0.0.0" to expose on the local network
        "password": "",
        # Used only when no host.yaml is found next to multiworld_dir
        # Meaning: the multiworld runs on someone else's machine and this dashboard just watches it.
        # Ignored entirely when a local host.yaml is present.
        "remote": {
            "host": "",
            "port": 38281,
            "password": "",
            # Public rooms (e.g. archipelago.gg) are served over TLS — leave
            # this on unless your remote server specifically isn't.
            "tls": True,
        },
    },
    "paths": {
        # Host-droppable images (hero/border image, etc.) served under /host/.
        "assets_dir": "./assets",
        # Where the runtime JSON logs live (deaths / received items / hint tags).
        "data_dir": "./data",
        # Optional explicit host.yaml; empty => <multiworld_dir>/host.yaml.
        "host_yaml": "",
        # Hall of Fame images + entries.toml (see server/hall_of_fame.py).
        "hall_of_fame_dir": "./hall-of-fame",
    },
    "branding": {
        "hero_title": "ArchipelaGoats",     # big hero headline
        "hero_image": "leEm.png",           # decorative image; "" hides it
        # How far the shadow-like fade into the navy band reaches into the image (its left edge).
        # 0 = barely faded, nearly the whole image
        # shows; 1 = a long, soft transition.
        "hero_image_fade": 0.35,
        "loading_name": "ArchipelaGoats",   # splash-screen wordmark
    },
    "footer": {
        "left": "archipelago · nguengant.fr",
        "right": "Have fun guys :)",
    },
    "features": {
        "hall_of_fame": True,
        "death_leaderboard": True,
        "constellation": True,
    },
    "hints": {
        # Which tag drives the dashboard "BKed checks" panel; "" hides it.
        "blocked_tag": "bked",
        "tags": [
            {"id": "bked", "label": "BKed", "label_fr": "BKed", "emoji": "🍔"},
            {"id": "mandatory", "label": "Mandatory", "label_fr": "Obligatoire", "emoji": ""},
            {"id": "comfort", "label": "Comfort", "label_fr": "Confort", "emoji": ""},
        ],
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Recursively merge ``override`` into ``base`` in place.

    Nested tables are merged key-by-key; every other value (including lists such
    as ``hints.tags``) is replaced wholesale, so a host that lists their own tags
    gets exactly that list rather than an element-wise merge.
    """
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load config.toml over the defaults. Never raises for a bad/missing file."""
    resolved = pathlib.Path(path or os.environ.get("AP_CONFIG") or "config.toml")
    cfg = copy.deepcopy(DEFAULTS)
    if resolved.is_file():
        try:
            with open(resolved, "rb") as fp:
                user = tomllib.load(fp)
            _deep_merge(cfg, user)
            log.info("loaded config from %s", resolved)
        except (OSError, tomllib.TOMLDecodeError) as e:
            log.error("=" * 78)
            log.error("COULD NOT PARSE %s, IGNORING IT AND USING BUILT-IN DEFAULTS", resolved)
            log.error("Reason: %s", e)
            log.error("Your config.toml changes are NOT applied until this is fixed.")
            log.error("=" * 78)
    else:
        log.info("no config file at %s; using built-in defaults", resolved)
    return cfg


def tag_ids(cfg: dict[str, Any]) -> list[str]:
    """Ordered list of configured hint-tag ids."""
    return [str(t["id"]) for t in cfg["hints"]["tags"] if t.get("id")]


def find_multiworld_file(multiworld: str) -> str:
    """Resolve the .archipelago to load.

    ``multiworld`` may be a direct file path or a folder; a folder is scanned for
    the most-recently-modified ``*.archipelago`` (the drag-and-drop flow).
    Raises :class:`FileNotFoundError` with an actionable message when nothing is
    found, so a fresh install fails loudly instead of with a bare traceback.
    """
    p = pathlib.Path(multiworld)
    if p.is_file():
        return str(p)
    if p.is_dir():
        files = sorted(p.glob("*.archipelago"), key=lambda f: f.stat().st_mtime, reverse=True)
        if files:
            return str(files[0])
        raise FileNotFoundError(
            f"no *.archipelago file found in {p.resolve()}, drop your "
            f"multiworld-generated file there and restart"
        )
    raise FileNotFoundError(
        f"multiworld path {p.resolve()} does not exist, set [server].multiworld_dir "
        f"in config.toml (or AP_FILE) to your .archipelago file or its folder"
    )


def public_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """The browser-safe subset: branding, footer, socials, features, tags.

    Excludes the AP password and every filesystem path.
    """
    return {
        "branding": dict(cfg["branding"]),
        "footer": dict(cfg["footer"]),
        "features": dict(cfg["features"]),
        "hints": {
            "blocked_tag": cfg["hints"]["blocked_tag"],
            "tags": [dict(t) for t in cfg["hints"]["tags"]],
        },
    }
