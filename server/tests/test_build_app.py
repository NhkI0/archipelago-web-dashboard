"""Smoke tests for build_app(): the whole point of Phase 0 is that this no
longer needs a real .archipelago file or a reachable AP server to import."""

from __future__ import annotations

import pathlib
import pickle
import zlib

import pytest
from fastapi.testclient import TestClient

from server.config import RoomConfig, load_config
from server.main import build_app


def _write_fixture_multidata(path: pathlib.Path) -> None:
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
    payload = zlib.compress(pickle.dumps(data))
    path.write_bytes(b"\x03" + payload)


@pytest.fixture
def room(tmp_path: pathlib.Path) -> RoomConfig:
    ap_file = tmp_path / "test.archipelago"
    _write_fixture_multidata(ap_file)
    return RoomConfig(
        config=load_config(tmp_path / "does-not-exist.toml"),  # falls back to defaults
        ap_file=str(ap_file),
        ap_host="127.0.0.1",
        ap_port=1,  # nothing listens here; tracker/session connects fail harmlessly
        ap_password="",
        ap_secure=False,
        hint_cost=None,
        deaths_file=tmp_path / "deaths.json",
        items_file=tmp_path / "items.json",
        tags_file=tmp_path / "tags.json",
        assets_dir=tmp_path / "assets",
        hall_of_fame_dir=tmp_path / "hall-of-fame",
        static_dir=tmp_path / "dist",
    )


def test_build_app_serves_config_and_state(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        cfg_resp = client.get("/api/config")
        assert cfg_resp.status_code == 200
        assert "branding" in cfg_resp.json()

        state_resp = client.get("/api/state")
        assert state_resp.status_code == 200
        body = state_resp.json()
        assert body["seed_name"] == "test-seed"
        assert body["slots"][0]["name"] == "Alice"


def test_build_app_slot_endpoint(room: RoomConfig) -> None:
    app = build_app(room)
    with TestClient(app) as client:
        resp = client.get("/api/slot/Alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slot"]["name"] == "Alice"
        assert body["locations"][0]["name"] == "Chest"


def test_build_app_raises_on_bad_multidata(room: RoomConfig, tmp_path: pathlib.Path) -> None:
    bad_file = tmp_path / "corrupt.archipelago"
    bad_file.write_bytes(b"not a real multidata file")
    room.ap_file = str(bad_file)
    with pytest.raises(Exception):
        build_app(room)
