"""
Spawns Universal Tracker (FarisTheAncient's Archipelago apworld) headlessly to
compute which of a slot's remaining locations are currently in logic. See
config.toml's [tracker] block for setup.
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re

log = logging.getLogger("ap.ut_tracker")

MAX_YAML_BYTES = 256 * 1024

_NOISE_SUBSTRINGS = ("[", "Archipelago", "Connecting", "Connected", "Skipping", "host", "Warning")
_FILLER_RE = re.compile(r"adding \d+ filler items", re.IGNORECASE)
# Every AP client prints this once right after a successful Connect; a more
# stable anchor than blocklisting each version's pre-connect noise.
_HANDSHAKE_MARKER = "now that you are connected"


class UTError(Exception):
    """Base for tracker-run failures; message is safe to show the user."""


class NoYamlError(UTError):
    pass


class UTTimeoutError(UTError):
    pass


class UTProcessError(UTError):
    pass


def _yaml_player_name(path: pathlib.Path) -> str | None:
    """Top-level `name:` scalar from a YAML file, or None. No PyYAML needed."""
    try:
        with open(path, encoding="utf-8") as fp:
            for line in fp:
                if line.startswith(("name:", "name :")):
                    return line.split(":", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return None


def find_duplicate_player_name(yaml_dir: pathlib.Path) -> str | None:
    """A player name shared by two+ YAML files in yaml_dir, or None.

    Universal Tracker regenerates from every YAML in that folder at once, and
    crashes (then hangs indefinitely instead of exiting) on a name collision.
    Checking this upfront turns a silent multi-minute hang into an instant,
    actionable error.
    """
    seen: dict[str, str] = {}
    for path in sorted(yaml_dir.glob("*.yaml")):
        name = _yaml_player_name(path)
        if not name:
            continue
        key = name.lower()
        if key in seen and seen[key] != path.name:
            return name
        seen[key] = path.name
    return None


def parse_ut_output(stdout: str) -> list[str]:
    """Pure text filter; standalone so it's unit-testable without a subprocess."""
    lines = stdout.split("\n")
    start = None
    for i, raw_line in enumerate(lines):
        if _HANDSHAKE_MARKER in raw_line.lower():
            start = i + 1  # last match wins, in case of multiple connect attempts
    if start is None:
        return []  # never actually connected; nothing here is a real location
    out = []
    for raw_line in lines[start:]:
        line = raw_line.strip()
        if not line:
            continue
        if _FILLER_RE.search(line.lower()):
            continue
        if line.startswith("Notice ("):
            continue
        if any(x in line for x in _NOISE_SUBSTRINGS):
            continue
        out.append(line)
    return out


class UTRunner:
    def __init__(
        self,
        *,
        launcher: pathlib.Path,
        python_bin: str,
        yaml_dir: pathlib.Path,
        host: str,
        port: int,
        password: str,
        timeout: float,
    ) -> None:
        self.launcher = launcher
        self.python_bin = python_bin
        self.yaml_dir = yaml_dir
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        # UT processes are heavy (a full AP client re-running game logic); only
        # run one at a time rather than letting concurrent requests pile up.
        self._lock = asyncio.Lock()

    def _yaml_path(self, slot_name: str) -> pathlib.Path:
        # Slot names are validated against multidata by callers before reaching
        # here, but keep the on-disk name inert regardless.
        safe = re.sub(r"[^\w.\- ]", "_", slot_name)
        return self.yaml_dir / f"{safe}.yaml"

    def has_yaml(self, slot_name: str) -> bool:
        return self._yaml_path(slot_name).is_file()

    def save_yaml(self, slot_name: str, content: bytes) -> None:
        if len(content) > MAX_YAML_BYTES:
            raise ValueError(f"YAML file exceeds the {MAX_YAML_BYTES} byte limit")
        self.yaml_dir.mkdir(parents=True, exist_ok=True)
        self._yaml_path(slot_name).write_bytes(content)

    def _argv(self, slot_name: str) -> list[str]:
        connect = f"archipelago://{slot_name}:{self.password or 'None'}@{self.host}:{self.port}"
        program = str(self.launcher)
        args = [program]
        if self.launcher.suffix.lower() == ".py":
            args = [self.python_bin, program]
        return [*args, "Universal Tracker", "--", "--nogui", "--list", connect]

    async def run(self, slot_name: str) -> list[str]:
        if not self.has_yaml(slot_name):
            raise NoYamlError(f"no YAML on file for slot {slot_name!r}; upload one first")
        dup = find_duplicate_player_name(self.yaml_dir)
        if dup:
            raise UTProcessError(
                f"two YAML files in {self.yaml_dir} both use player name {dup!r}; "
                f"Universal Tracker's generation fails on that, remove or rename one"
            )

        argv = self._argv(slot_name)
        log.info("running UT for slot %r: %s", slot_name, " ".join(argv).replace(self.password, "***") if self.password else " ".join(argv))
        async with self._lock:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=str(self.launcher.parent),
                    stdin=asyncio.subprocess.DEVNULL,  # never let UT block waiting on input
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    # Piped stdout isn't a tty, so Python block-buffers it instead of
                    # flushing per line; without this, output sits unseen in the
                    # child's buffer until it exits, defeating the timeout diagnostics.
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
            except OSError as e:
                raise UTProcessError(f"could not start Universal Tracker: {e}") from e

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()  # drain whatever it had already printed
                log.warning(
                    "UT timed out for slot %r after %.0fs; stdout=%r stderr=%r",
                    slot_name, self.timeout, stdout.decode(errors="replace")[-2000:], stderr.decode(errors="replace")[-2000:],
                )
                raise UTTimeoutError(
                    f"Universal Tracker did not finish within {self.timeout:.0f}s for slot {slot_name!r}"
                ) from None

            if proc.returncode != 0:
                log.warning(
                    "UT exited %s for slot %r: %s",
                    proc.returncode, slot_name, stderr.decode(errors="replace")[-2000:],
                )

        text = stdout.decode(errors="replace")
        locations = parse_ut_output(text)
        log.info("UT for slot %r returned %d locations; raw stdout=%r", slot_name, len(locations), text[-3000:])
        if not locations and proc.returncode != 0:
            raise UTProcessError(f"Universal Tracker failed (exit {proc.returncode}); check server logs")
        return locations
