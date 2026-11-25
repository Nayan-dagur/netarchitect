"""Unit tests for L1 Physical Media Physics & L2 Design Engine."""

import pytest

from netarchitect.engines.media_engine import evaluate_layer1_links, evaluate_layer2_design
from netarchitect.exceptions import ParameterValidationError, PhysicalDistanceViolationError
from netarchitect.models import LinkSpec, NetworkSpecification, SiteSpec, SubnetRequest


def _make_spec(links: list[LinkSpec], target_latency_ms: float | None = None) -> NetworkSpecification:
    return NetworkSpecification(
        profile_name="MediaTest",
        topology_tier="custom",
        target_latency_ms=target_latency_ms,
        sites=[SiteSpec(name="HQ", role="hq", endpoints=100, poe_aps=10)],
        links=links,
        root_prefix="10.0.0.0/24",
        subnet_requests=[SubnetRequest(name="Corp", hosts=50, vlan_id=10, security_zone="corp")],
    )


def test_copper_boundary_100m_allowed() -> None:
    spec = _make_spec([LinkSpec(name="L1", src="A", dst="B", distance_m=100.0, requested_media="auto")])
    recs = evaluate_layer1_links(spec)
    assert len(recs) == 1
    assert "Cat6a" in recs[0].selected_media
    assert "10GBASE-T" in recs[0].transceiver
    assert "802.3an" in recs[0].justification


def test_copper_over_100m_raises_physical_distance_violation() -> None:
    spec = _make_spec([LinkSpec(name="BadCopper", src="A", dst="B", distance_m=100.1, requested_media="copper")])
    with pytest.raises(PhysicalDistanceViolationError) as exc_info:
        evaluate_layer1_links(spec)
    assert "attenuation" in str(exc_info.value).lower()
    assert exc_info.value.max_distance_m == 100.0


def test_om4_mmf_boundaries_101m_to_400m() -> None:
    spec = _make_spec([
        LinkSpec(name="L101", src="A", dst="B", distance_m=101.0),
        LinkSpec(name="L400", src="A", dst="C", distance_m=400.0),
    ])
    recs = evaluate_layer1_links(spec)
    assert all("OM4" in r.selected_media for r in recs)
    assert all("10GBASE-SR" in r.transceiver for r in recs)
    assert all("850nm" in r.wavelength_or_standard for r in recs)


def test_mmf_over_400m_raises_physical_distance_violation() -> None:
    spec = _make_spec([LinkSpec(name="BadMMF", src="A", dst="B", distance_m=401.0, requested_media="mmf")])
    with pytest.raises(PhysicalDistanceViolationError):
        evaluate_layer1_links(spec)


def test_os2_smf_tiers_lr_er_zr_and_wan() -> None:
    spec = _make_spec([
        LinkSpec(name="Link-5km", src="A", dst="B", distance_m=5_000.0),
        LinkSpec(name="Link-22km", src="A", dst="C", distance_m=22_000.0),
        LinkSpec(name="Link-60km", src="A", dst="D", distance_m=60_000.0),
        LinkSpec(name="Link-500km", src="A", dst="E", distance_m=500_000.0),
    ])
    recs = evaluate_layer1_links(spec)
    assert "10GBASE-LR" in recs[0].transceiver
    assert "10GBASE-ER" in recs[1].transceiver
    assert "22 km" in recs[1].justification
    assert "400m" in recs[1].justification
    assert recs[1].estimated_optical_loss_db is not None
    assert recs[1].optical_budget_db is not None
    assert recs[1].estimated_optical_loss_db <= recs[1].optical_budget_db
    assert "10GBASE-ZR" in recs[2].transceiver
    assert "DWDM" in recs[3].transceiver


def test_speed_of_light_latency_violation() -> None:
    # 50 km in fiber takes ~0.245 ms; requesting 0.1 ms must fail physics check
    spec = _make_spec([
        LinkSpec(name="TooFast", src="A", dst="B", distance_m=50_000.0, max_latency_ms=0.1)
    ])
    with pytest.raises(ParameterValidationError):
        evaluate_layer1_links(spec)


def test_layer2_poe_and_sub5ms_qos() -> None:
    spec = _make_spec(
        [LinkSpec(name="MAN", src="HQ", dst="Remote", distance_m=22_000.0, role="man", dual_homed=True)],
        target_latency_ms=4.5,
    )
    recs = evaluate_layer1_links(spec)
    l2 = evaluate_layer2_design(spec, recs)
    assert l2.native_vlan == 999
    assert 1 not in l2.allowed_vlans
    assert l2.total_poe_budget_watts == 360  # 10 APs * 30W * 1.2
    assert l2.evpl_enabled is True
    assert l2.qos_profile is not None and "LLQ" in l2.qos_profile
