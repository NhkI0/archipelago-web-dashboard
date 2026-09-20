"""Self-hosted admin panel: swap the running multiworld, gated by [admin].password.

Applies the change by re-execing the process (os.execv) rather than hot-swapping
the running app in place.
"""

from __future__ import annotations

import io
import logging
import os
import pathlib
import pickle
import secrets
import sys
import time
import zipfile
import zlib
from typing import Any

import tomlkit
from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .config import RoomConfig, _fetch_room_status, _parse_room_url, resolve_host_yaml_path
from .multidata import MAX_ARCHIPELAGO_FILE_BYTES, multidata_from_sanitized, parse_untrusted

log = logging.getLogger("ap.admin")

_COOKIE_NAME = "ap_admin"
_ZIP_MAX_DECOMPRESS_RATIO = 100

# In-memory only: a restart (which every reconfigure triggers) clears this,
# which is fine, the admin just logs in again after the new process is up.
_admin_tokens: set[str] = set()


class LoginBody(BaseModel):
    password: str


def _extract_archipelago_from_zip(zip_bytes: bytes, max_bytes: int) -> bytes | None:
    """Pull the single .archipelago member out of an uploaded .zip, or None."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            members = [i for i in zf.infolist() if i.filename.lower().endswith(".archipelago")]
            if len(members) != 1:
                return None
            info = members[0]
            if info.file_size > max_bytes:
                return None
            if info.compress_size and info.file_size / info.compress_size > _ZIP_MAX_DECOMPRESS_RATIO:
                return None
            return zf.read(info)
    except zipfile.BadZipFile:
        return None


def _archive_if_exists(path: pathlib.Path | None, ts: str) -> None:
    """Rename a runtime data file aside instead of deleting it, so a fresh
    game starts with clean state but nothing is destructively lost."""
    if path is None or not path.exists():
        return
    archived = path.with_name(f"{path.stem}.{ts}.bak{path.suffix}")
    try:
        path.rename(archived)
        log.info("archived %s -> %s", path, archived)
    except OSError as e:
        log.warning("could not archive %s: %s", path, e)


def _ensure_table(doc: Any, key: str) -> Any:
    if key not in doc:
        doc[key] = tomlkit.table()
    return doc[key]


def _restart() -> None:
    log.info("admin reconfigure: restarting the process now")
    os.execv(sys.executable, [sys.executable, "-m", "server"])


def build_admin_router(room: RoomConfig) -> APIRouter:
    router = APIRouter(prefix="/api/admin")
    admin_password = str(room.config["admin"].get("password") or "")

    def _require_admin(ap_admin: str | None) -> None:
        if not admin_password:
            raise HTTPException(503, "no [admin].password set in config.toml")
        if not ap_admin or ap_admin not in _admin_tokens:
            raise HTTPException(401, "not logged in")

    @router.post("/login")
    async def login(body: LoginBody, response: Response) -> dict[str, Any]:
        if not admin_password or not secrets.compare_digest(body.password, admin_password):
            raise HTTPException(401, "wrong password")
        token = secrets.token_urlsafe(32)
        _admin_tokens.add(token)
        response.set_cookie(_COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 8)
        return {"ok": True}

    @router.post("/logout")
    async def logout(response: Response, ap_admin: str | None = Cookie(default=None)) -> dict[str, Any]:
        if ap_admin:
            _admin_tokens.discard(ap_admin)
        response.delete_cookie(_COOKIE_NAME)
        return {"ok": True}

    @router.get("/status")
    async def status(ap_admin: str | None = Cookie(default=None)) -> dict[str, Any]:
        logged_in = bool(ap_admin and ap_admin in _admin_tokens)
        host_yaml_present = pathlib.Path(resolve_host_yaml_path(room.config)).is_file()
        result: dict[str, Any] = {"logged_in": logged_in, "host_yaml_present": host_yaml_present}
        if logged_in and not host_yaml_present:
            remote = room.config["server"]["remote"]
            # The stored password never round-trips back to the browser; the form
            # treats "left blank" as "keep the current one" (see reconfigure below).
            result["current"] = {
                "room_url": remote.get("room_url", ""),
                "ap_host": remote.get("host", ""),
                "ap_port": remote.get("port", 0),
                "ap_secure": bool(remote.get("tls", True)),
                "default_slot": room.config["server"].get("default_slot", ""),
                "hint_cost": room.config["server"].get("hint_cost_override"),
            }
        return result

    @router.post("/reconfigure")
    async def reconfigure(
        request: Request, archipelago_file: UploadFile, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        _require_admin(request.cookies.get(_COOKIE_NAME))

        form = await request.form()

        def field(name: str) -> str:
            v = form.get(name)
            return v.strip() if isinstance(v, str) else ""

        room_url = field("room_url")
        ap_host = field("ap_host")
        ap_port = field("ap_port")
        ap_password = field("ap_password")
        ap_secure = form.get("ap_secure") is not None
        hint_cost = field("hint_cost")
        default_slot = field("default_slot")

        host_yaml_present = pathlib.Path(resolve_host_yaml_path(room.config)).is_file()
        connection_fields_given = bool(room_url or ap_host or ap_port or ap_password)
        if host_yaml_present and connection_fields_given:
            raise HTTPException(
                400,
                "a local host.yaml is present, this dashboard already connects to your own AP "
                "server; connection fields (host/port/password/room URL) aren't editable here",
            )

        remote_host = ""
        remote_port = 0
        if not host_yaml_present:
            if room_url and (ap_host or ap_port):
                raise HTTPException(400, "enter either an archipelago.gg room URL or a server host and port, not both")
            if room_url:
                try:
                    hostname, room_id = await run_in_threadpool(_parse_room_url, room_url)
                    room_status = await run_in_threadpool(_fetch_room_status, hostname, room_id)
                except RuntimeError as e:
                    raise HTTPException(400, str(e)) from e
                remote_host = hostname
                remote_port = int(room_status["last_port"])
                ap_secure = True
            elif ap_host and ap_port:
                remote_host = ap_host
                try:
                    remote_port = int(ap_port)
                except ValueError:
                    raise HTTPException(400, "port must be a number") from None
            else:
                raise HTTPException(400, "enter either an archipelago.gg room URL or a server host and port")

        parsed_hint_cost: int | None = None
        if hint_cost:
            try:
                parsed_hint_cost = int(hint_cost)
            except ValueError:
                raise HTTPException(400, "hint cost must be a number") from None

        payload = await archipelago_file.read(MAX_ARCHIPELAGO_FILE_BYTES + 1)
        if len(payload) > MAX_ARCHIPELAGO_FILE_BYTES:
            raise HTTPException(400, f"file exceeds the {MAX_ARCHIPELAGO_FILE_BYTES} byte limit")

        filename = archipelago_file.filename or ""
        if filename.lower().endswith(".zip") or payload[:2] == b"PK":
            extracted = await run_in_threadpool(_extract_archipelago_from_zip, payload, MAX_ARCHIPELAGO_FILE_BYTES)
            if extracted is None:
                raise HTTPException(
                    400,
                    "couldn't find a single .archipelago file inside that .zip -- make sure it's "
                    "the generator's output zip with exactly one .archipelago file in it",
                )
            payload = extracted

        try:
            sanitized = await run_in_threadpool(parse_untrusted, payload)
            await run_in_threadpool(multidata_from_sanitized, sanitized)
        except (ValueError, KeyError, zlib.error, pickle.UnpicklingError, EOFError) as e:
            raise HTTPException(400, f"couldn't read that as a multidata file: {e}") from e

        ts = time.strftime("%Y%m%d-%H%M%S")

        multiworld = pathlib.Path(room.config["server"]["multiworld_dir"])
        if multiworld.is_dir():
            dest = multiworld / f"admin_upload_{ts}.archipelago"
        else:
            # Configured as a direct file path: that exact file is what gets loaded,
            # so this necessarily overwrites it (no folder to drop a new file into).
            dest = multiworld
            dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        log.info("admin reconfigure: wrote new multiworld to %s", dest)

        for f in (room.deaths_file, room.items_file, room.tags_file, room.hints_used_file):
            _archive_if_exists(f, ts)

        if room.config_path is not None:
            doc = tomlkit.parse(room.config_path.read_text(encoding="utf-8")) if room.config_path.is_file() else tomlkit.document()
            server = _ensure_table(doc, "server")
            server["default_slot"] = default_slot
            if parsed_hint_cost is not None:
                server["hint_cost_override"] = parsed_hint_cost
            if not host_yaml_present:
                remote = _ensure_table(server, "remote")
                if ap_password:  # blank means "keep the current one", never wipe it
                    remote["password"] = ap_password
                remote["tls"] = ap_secure
                if room_url:
                    remote["room_url"] = room_url
                    remote["host"] = ""
                else:
                    remote["host"] = remote_host
                    remote["port"] = remote_port
                    remote["room_url"] = ""
            room.config_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
            log.info("admin reconfigure: updated %s", room.config_path)

        # Background tasks run after the response is sent, so the client gets this reply first.
        background_tasks.add_task(_restart)
        return {"ok": True, "restarting": True}

    return router
