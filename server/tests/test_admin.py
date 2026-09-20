"""Tests for the self-hosted admin reconfigure panel (server/admin.py)."""

from __future__ import annotations

import pathlib
import pickle
import zlib

import pytest
import tomlkit
from fastapi.testclient import TestClient

from server import admin as admin_module
from server.config import RoomConfig, load_config
from server.main import build_app


def _fixture_multidata_bytes() -> bytes:
    data = {
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "TestGame", 1, ())},
        "locations": {1: {100: (5000, 1, 0)}},
        "datapackage": {
            "TestGame": {
                "item_name_to_id": {"Sword": 5000},
                "location_name_to_id": {"Chest": 100},
            }
        },
        "slot_data": {1: {}},
        "games": {1: "TestGame"},
    }
    return b"\x03" + zlib.compress(pickle.dumps(data))


def _write_fixture_multidata(path: pathlib.Path) -> None:
    path.write_bytes(_fixture_multidata_bytes())


@pytest.fixture(autouse=True)
def no_real_restart(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every reconfigure ends by re-execing the process; replace that with a
    recorder so tests don't actually blow away the test runner."""
    calls: list[str] = []
    monkeypatch.setattr(admin_module, "_restart", lambda: calls.append("restart"))
    return calls


def _config_path(tmp_path: pathlib.Path, *, admin_enabled: bool, password: str = "secret") -> pathlib.Path:
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
[server]
multiworld_dir = "{(tmp_path / 'multiworld').as_posix()}"

[admin]
enabled = {"true" if admin_enabled else "false"}
password = "{password}"
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def room(tmp_path: pathlib.Path) -> RoomConfig:
    ap_file = tmp_path / "test.archipelago"
    _write_fixture_multidata(ap_file)
    multiworld_dir = tmp_path / "multiworld"
    multiworld_dir.mkdir()
    config_path = _config_path(tmp_path, admin_enabled=True)
    return RoomConfig(
        config=load_config(config_path),
        ap_file=str(ap_file),
        ap_host="127.0.0.1",
        ap_port=1,
        ap_password="",
        ap_secure=False,
        hint_cost=None,
        deaths_file=tmp_path / "data" / "deaths.json",
        items_file=tmp_path / "data" / "items.json",
        tags_file=tmp_path / "data" / "tags.json",
        hints_used_file=tmp_path / "data" / "hints_used.json",
        assets_dir=tmp_path / "assets",
        hall_of_fame_dir=tmp_path / "hall-of-fame",
        static_dir=tmp_path / "dist",
        config_path=config_path,
    )


def test_admin_routes_absent_when_disabled(tmp_path: pathlib.Path) -> None:
    ap_file = tmp_path / "test.archipelago"
    _write_fixture_multidata(ap_file)
    config_path = _config_path(tmp_path, admin_enabled=False)
    room = RoomConfig(
        config=load_config(config_path),
        ap_file=str(ap_file),
        ap_host="127.0.0.1",
        ap_port=1,
        ap_password="",
        ap_secure=False,
        hint_cost=None,
        deaths_file=tmp_path / "deaths.json",
        items_file=tmp_path / "items.json",
        tags_file=tmp_path / "tags.json",
        assets_dir=tmp_path / "assets",
        hall_of_fame_dir=tmp_path / "hall-of-fame",
        static_dir=tmp_path / "dist",
        config_path=config_path,
    )
    app = build_app(room)
    with TestClient(app) as client:
        assert client.get("/api/admin/status").status_code == 404
        assert client.post("/api/admin/login", json={"password": "secret"}).status_code == 404


def test_login_wrong_password_rejected(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        resp = client.post("/api/admin/login", json={"password": "nope"})
        assert resp.status_code == 401
        assert client.get("/api/admin/status").json() == {"logged_in": False, "host_yaml_present": False}


def test_login_success_sets_cookie_and_status_reflects_it(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        resp = client.post("/api/admin/login", json={"password": "secret"})
        assert resp.status_code == 200
        assert "ap_admin" in resp.cookies
        assert client.get("/api/admin/status").json()["logged_in"] is True


def test_reconfigure_requires_login(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        resp = client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={"ap_host": "example.com", "ap_port": "38281"},
        )
        assert resp.status_code == 401


def test_reconfigure_swaps_multiworld_and_updates_config(
    room: RoomConfig, no_real_restart: list[str]
) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        client.post("/api/admin/login", json={"password": "secret"})

        # Pre-existing runtime data that should be archived, not destroyed.
        room.deaths_file.parent.mkdir(parents=True, exist_ok=True)
        room.deaths_file.write_text("{}", encoding="utf-8")

        resp = client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={
                "ap_host": "example.com",
                "ap_port": "38281",
                "ap_password": "hunter2",
                "ap_secure": "true",
                "default_slot": "Alice",
                "hint_cost": "10",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "restarting": True}
        assert no_real_restart == ["restart"]

        multiworld_dir = pathlib.Path(room.config["server"]["multiworld_dir"])
        uploaded = list(multiworld_dir.glob("admin_upload_*.archipelago"))
        assert len(uploaded) == 1

        assert not room.deaths_file.exists()
        archived = list(room.deaths_file.parent.glob("deaths.*.bak.json"))
        assert len(archived) == 1

        doc = tomlkit.parse(room.config_path.read_text(encoding="utf-8"))
        assert doc["server"]["default_slot"] == "Alice"
        assert doc["server"]["hint_cost_override"] == 10
        assert doc["server"]["remote"]["host"] == "example.com"
        assert doc["server"]["remote"]["port"] == 38281
        assert doc["server"]["remote"]["password"] == "hunter2"
        assert doc["server"]["remote"]["tls"] is True


def test_status_reports_current_values_when_logged_in(tmp_path: pathlib.Path) -> None:
    """The frontend uses this to pre-select the URL vs. host/port tab on load,
    reflecting whatever's already configured rather than always defaulting."""
    ap_file = tmp_path / "test.archipelago"
    _write_fixture_multidata(ap_file)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[server]
multiworld_dir = "%s"
default_slot = "Alice"

[server.remote]
room_url = "https://archipelago.gg/room/AbCdEfGhIjKl"
password = "hunter2"

[admin]
enabled = true
password = "secret"
"""
        % (tmp_path / "multiworld").as_posix(),
        encoding="utf-8",
    )
    (tmp_path / "multiworld").mkdir()
    room = RoomConfig(
        config=load_config(config_path),
        ap_file=str(ap_file),
        ap_host="127.0.0.1",
        ap_port=1,
        ap_password="",
        ap_secure=False,
        hint_cost=None,
        deaths_file=tmp_path / "deaths.json",
        items_file=tmp_path / "items.json",
        tags_file=tmp_path / "tags.json",
        assets_dir=tmp_path / "assets",
        hall_of_fame_dir=tmp_path / "hall-of-fame",
        static_dir=tmp_path / "dist",
        config_path=config_path,
    )
    app = build_app(room)
    with TestClient(app) as client:
        assert "current" not in client.get("/api/admin/status").json()

        client.post("/api/admin/login", json={"password": "secret"})
        current = client.get("/api/admin/status").json()["current"]
        assert current["room_url"] == "https://archipelago.gg/room/AbCdEfGhIjKl"
        assert current["ap_host"] == ""
        assert current["default_slot"] == "Alice"
        assert "password" not in current


def test_reconfigure_blank_password_keeps_existing_one(room: RoomConfig, no_real_restart: list[str]) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        client.post("/api/admin/login", json={"password": "secret"})
        client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={"ap_host": "example.com", "ap_port": "38281", "ap_password": "hunter2"},
        )
        # Second submission leaves the password field blank; it must not be wiped.
        client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={"ap_host": "example.com", "ap_port": "38281"},
        )
        doc = tomlkit.parse(room.config_path.read_text(encoding="utf-8"))
        assert doc["server"]["remote"]["password"] == "hunter2"


def test_reconfigure_rejects_bad_multidata(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        client.post("/api/admin/login", json={"password": "secret"})
        resp = client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", b"not a real multidata file")},
            data={"ap_host": "example.com", "ap_port": "38281"},
        )
        assert resp.status_code == 400


def test_reconfigure_rejects_connection_fields_when_host_yaml_present(
    room: RoomConfig, tmp_path: pathlib.Path
) -> None:
    multiworld_dir = pathlib.Path(room.config["server"]["multiworld_dir"])
    (multiworld_dir / "host.yaml").write_text("server_options:\n  port: 38281\n", encoding="utf-8")

    app = build_app(room)
    with TestClient(app) as client:
        client.post("/api/admin/login", json={"password": "secret"})
        resp = client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={"ap_host": "example.com", "ap_port": "38281"},
        )
        assert resp.status_code == 400


def test_reconfigure_allows_default_slot_only_when_host_yaml_present(
    room: RoomConfig, no_real_restart: list[str]
) -> None:
    multiworld_dir = pathlib.Path(room.config["server"]["multiworld_dir"])
    (multiworld_dir / "host.yaml").write_text("server_options:\n  port: 38281\n", encoding="utf-8")

    app = build_app(room)
    with TestClient(app) as client:
        client.post("/api/admin/login", json={"password": "secret"})
        resp = client.post(
            "/api/admin/reconfigure",
            files={"archipelago_file": ("game.archipelago", _fixture_multidata_bytes())},
            data={"default_slot": "Alice"},
        )
        assert resp.status_code == 200
        assert no_real_restart == ["restart"]
        doc = tomlkit.parse(room.config_path.read_text(encoding="utf-8"))
        assert doc["server"]["default_slot"] == "Alice"
