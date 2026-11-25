"""Integration tests for Typer CLI and FastAPI REST endpoints."""

import json
from pathlib import Path
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from netarchitect.api import app as fastapi_app
from netarchitect.cli import app as cli_app

runner = CliRunner()
client = TestClient(fastapi_app)


def test_cli_presets_and_plan_json() -> None:
    res_presets = runner.invoke(cli_app, ["presets"])
    assert res_presets.exit_code == 0
    assert "campus_lan" in res_presets.output
    assert "metro_man" in res_presets.output
    assert "global_wan" in res_presets.output

    res_plan = runner.invoke(cli_app, ["plan", "--preset", "campus_lan", "--json"])
    assert res_plan.exit_code == 0
    payload = json.loads(res_plan.output)
    assert payload["profile_name"] == "Campus LAN"
    assert len(payload["vlsm_plan"]["subnets"]) == 5


def test_cli_validate_rejects_copper_over_100m(tmp_path: Path) -> None:
    bad_spec = {
        "profile_name": "BadCopperCLI",
        "links": [
            {"name": "LongCopper", "src": "A", "dst": "B", "distance_m": 150, "requested_media": "copper"}
        ],
        "root_prefix": "10.0.0.0/24",
        "subnet_requests": [{"name": "LAN", "hosts": 20, "vlan_id": 10}],
    }
    bad_file = tmp_path / "bad_copper.json"
    bad_file.write_text(json.dumps(bad_spec), encoding="utf-8")

    res = runner.invoke(cli_app, ["validate", str(bad_file)])
    assert res.exit_code == 1
    assert "PhysicalDistanceViolationError" in res.output


def test_api_endpoints_and_error_handling() -> None:
    assert client.get("/health").status_code == 200
    assert "campus_lan" in client.get("/presets").json()

    plan_resp = client.get("/plan/metro_man")
    assert plan_resp.status_code == 200
    assert plan_resp.json()["layer2_design"]["evpl_enabled"] is True

    ios_resp = client.get("/export/global_wan/ios")
    assert ios_resp.status_code == 200
    assert "router bgp 65300" in ios_resp.text

    # Trigger 422 on copper > 100m
    bad_resp = client.post(
        "/plan",
        json={
            "profile_name": "BadAPI",
            "links": [{"name": "L1", "src": "A", "dst": "B", "distance_m": 120, "requested_media": "copper"}],
            "root_prefix": "10.0.0.0/24",
            "subnet_requests": [{"name": "LAN", "hosts": 10, "vlan_id": 10}],
        },
    )
    assert bad_resp.status_code == 422
    assert bad_resp.json()["detail"]["error_type"] == "PhysicalDistanceViolationError"
