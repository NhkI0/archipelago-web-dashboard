"""
Host configuration — the single ``config.toml`` a host edits to control the site.

Parsed with the stdlib :mod:`tomllib` (Python 3.11+), so there is no extra
dependency. A missing or partial file still boots: whatever the host provides is
deep-merged over :data:`DEFAULTS`. Environment variables continue to override
the resolved values in ``main.py``, for hosts that prefer env-based config
(e.g. Docker) over editing ``config.toml``.

Only the subset returned by :func:`public_config` is ever sent to browsers
the AP password and filesystem paths never leave the backend.
"""

from __future__ import annotations

import copy
import logging
import os
import pathlib
import tomllib
from dataclasses import dataclass
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
        "hero_image": "banner.png",         # decorative image; "" hides it
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


@dataclass
class RoomConfig:
    """Everything `build_app()` needs to serve one room.

    Self-hosted mode builds this from `config.toml` + env vars via
    `resolve_room_config()` below. Hosted mode (ap-dashboard-hosted) builds
    it directly from the room's creation-form data instead — it already
    knows the AP host/port/password, so it never needs to touch
    `config.toml`'s `[server]`/`[server.remote]` tables or a local
    `host.yaml`.
    """

    config: dict[str, Any]          # merged config.toml (branding, features, hint tags, ...)
    ap_file: str
    ap_host: str
    ap_port: int
    ap_password: str
    ap_secure: bool
    hint_cost: int | None           # from host.yaml server_options, if found/parseable
    deaths_file: pathlib.Path
    items_file: pathlib.Path
    tags_file: pathlib.Path
    assets_dir: pathlib.Path
    hall_of_fame_dir: pathlib.Path
    static_dir: pathlib.Path
    sanitized_file: pathlib.Path | None = None  # hosted mode: load via load_sanitized() instead of ap_file
    base_path: str = "/"                        # e.g. "/<uuid>/" for a hosted room, injected into index.html


def _read_server_options_from_host_yaml(path: str) -> dict[str, str]:
    """Parse scalars under `server_options:` from Archipelago's host.yaml.

    Tiny ad-hoc YAML parse: we only need single-line scalars under a known section,
    so avoiding a PyYAML dependency keeps the web service slim.
    Values are returned as raw strings; callers cast as needed.
    """
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fp:
            in_server_options = False
            for line in fp:
                stripped = line.split("#", 1)[0].rstrip()
                if not stripped:
                    continue
                if not line.startswith((" ", "\t")):
                    in_server_options = stripped.rstrip(":") == "server_options"
                    continue
                if in_server_options and ":" in stripped:
                    key, _, value = stripped.strip().partition(":")
                    out[key.strip()] = value.strip()
    except OSError:
        return out
    return out


def _coerce_yaml_scalar(raw: str) -> str:
    """Strip quotes and turn YAML null sentinels into empty strings."""
    s = raw.strip()
    if s.lower() in ("null", "~", ""):
        return ""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s


def _env_or(cfg_val: Any, env_key: str, cast=str) -> Any:
    raw = os.environ.get(env_key)
    return cast(raw) if raw is not None else cfg_val


def resolve_room_config(path: str | os.PathLike[str] | None = None) -> RoomConfig:
    """Resolve one room's `RoomConfig` from `config.toml` + env vars.

    This is the self-hosted-only "figure out my one room from the files on disk" step:
    locate the `.archipelago`, decide whether to connect to a local `host.yaml`-described server or 
    `[server.remote]`, and resolve the runtime data-file paths. Raises `FileNotFoundError` / `RuntimeError` with
    an actionable message on misconfiguration rather than exiting the process-callers (the CLI entrypoint) decide
    how to report that.
    """
    cfg = load_config(path)

    data_dir = pathlib.Path(cfg["paths"]["data_dir"])
    multiworld = cfg["server"]["multiworld_dir"]
    ap_file = os.environ.get("AP_FILE") or find_multiworld_file(multiworld)

    ap_host_yaml = os.environ.get("AP_HOST_YAML") or (
        cfg["paths"]["host_yaml"] or str(pathlib.Path(multiworld).parent / "host.yaml")
        if pathlib.Path(multiworld).is_file()
        else cfg["paths"]["host_yaml"] or str(pathlib.Path(multiworld) / "host.yaml")
    )

    host_yaml_found = pathlib.Path(ap_host_yaml).is_file()
    server_opts = _read_server_options_from_host_yaml(ap_host_yaml) if host_yaml_found else {}

    hint_cost: int | None
    try:
        hint_cost = int(server_opts["hint_cost"])
        log.info("hint_cost = %d%% (from %s)", hint_cost, ap_host_yaml)
    except (KeyError, ValueError):
        hint_cost = None
        log.warning("could not read hint_cost from %s; using default", ap_host_yaml)

    # AP_HOST/AP_PORT/AP_PASSWORD: an explicit env override always wins.
    # Otherwise, a host.yaml found next to the multiworld file means the multiworld is running locally
    # So we connect to localhost using its own port (and password, read above).
    # No host.yaml means the multiworld runs elsewhere;
    # fall back to [server.remote] in config.toml, since there's no local host.yaml
    # to read a port/password from.
    remote = cfg["server"]["remote"]
    if os.environ.get("AP_HOST") or os.environ.get("AP_PORT"):
        ap_host = _env_or(cfg["server"]["ap_host"], "AP_HOST")
        ap_port = int(_env_or(cfg["server"]["ap_port"], "AP_PORT", int))
        ap_password = os.environ.get("AP_PASSWORD") or _coerce_yaml_scalar(server_opts.get("password", ""))
        ap_secure = os.environ.get("AP_SECURE", "").lower() in ("1", "true", "yes")
    elif host_yaml_found:
        log.info("host.yaml found at %s; connecting to the local multiworld", ap_host_yaml)
        ap_host = cfg["server"]["ap_host"]
        try:
            ap_port = int(server_opts["port"])
        except (KeyError, ValueError):
            ap_port = int(cfg["server"]["ap_port"])
        ap_password = os.environ.get("AP_PASSWORD") or _coerce_yaml_scalar(server_opts.get("password", ""))
        ap_secure = False
    else:
        if not remote.get("host"):
            raise RuntimeError(
                f"no host.yaml found at {ap_host_yaml} and no [server.remote].host set in "
                f"config.toml, either drop host.yaml next to your .archipelago file, or set "
                f"[server.remote] to the address of the remotely hosted multiworld"
            )
        log.info("no host.yaml at %s; connecting to remote multiworld at %s:%s",
                  ap_host_yaml, remote["host"], remote["port"])
        ap_host = remote["host"]
        ap_port = int(remote["port"])
        ap_password = os.environ.get("AP_PASSWORD") or remote.get("password", "")
        # Public rooms (archipelago.gg and most hosted ones) are wss://
        ap_secure = bool(remote.get("tls", True))

    if ap_password:
        log.info("server password loaded (%d chars)", len(ap_password))
    log.info("connecting to %s:%s (%s)", ap_host, ap_port, "wss" if ap_secure else "ws")

    return RoomConfig(
        config=cfg,
        ap_file=ap_file,
        ap_host=ap_host,
        ap_port=ap_port,
        ap_password=ap_password,
        ap_secure=ap_secure,
        hint_cost=hint_cost,
        deaths_file=pathlib.Path(os.environ.get("DEATHS_FILE") or str(data_dir / "death_leaderboard.json")),
        items_file=pathlib.Path(os.environ.get("ITEMS_FILE") or str(data_dir / "received_items.json")),
        tags_file=pathlib.Path(os.environ.get("TAGS_FILE") or str(data_dir / "hint_tags.json")),
        assets_dir=pathlib.Path(cfg["paths"]["assets_dir"]),
        hall_of_fame_dir=pathlib.Path(cfg["paths"]["hall_of_fame_dir"]),
        static_dir=pathlib.Path(os.environ.get("WEB_DIST", pathlib.Path(__file__).parent.parent / "frontend" / "dist")),
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
