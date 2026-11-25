"""End-to-end tests for all 3 preset profiles, Cisco IOS configs, and rationale outputs."""

from netarchitect.exporters.explainable import format_rationale_markdown
from netarchitect.planner import generate_architecture_plan
from netarchitect.presets import load_preset


def test_profile1_campus_lan_end_to_end() -> None:
    spec = load_preset("campus_lan")
    plan = generate_architecture_plan(spec)

    assert plan.total_endpoints >= 1600
    assert plan.routing_recommendation.igp_protocol == "Single-Area OSPFv2 (Area 0)"
    assert plan.routing_recommendation.egp_protocol is None
    assert any("Cat6a" in m.selected_media for m in plan.media_recommendations)
    assert any("OM4" in m.selected_media for m in plan.media_recommendations)

    cfg = plan.device_configs.combined_ios_cfg
    assert "spanning-tree mode rapid-pvst" in cfg
    assert "switchport trunk native vlan 999" in cfg
    assert "switchport trunk allowed vlan 10,20,30,99" in cfg
    assert "interface Vlan10" in cfg
    assert "router ospf 1" in cfg
    assert "passive-interface default" in cfg


def test_profile2_metro_man_end_to_end() -> None:
    spec = load_preset("metro_man")
    plan = generate_architecture_plan(spec)

    assert plan.layer2_design.evpl_enabled is True
    assert plan.layer2_design.qos_profile is not None
    assert any("10GBASE-ER" in m.transceiver for m in plan.media_recommendations)
    assert "eBGP-4" in (plan.routing_recommendation.egp_protocol or "")

    cfg = plan.device_configs.edge_router_ios
    assert "policy-map PM-WAN-QOS" in cfg
    assert "priority percent 30" in cfg
    assert "router bgp 65200" in cfg


def test_profile3_global_wan_end_to_end() -> None:
    spec = load_preset("global_wan")
    plan = generate_architecture_plan(spec)

    assert plan.routing_recommendation.ipsec_vpn_enabled is True
    assert plan.routing_recommendation.route_summarization_enabled is True
    assert "Multi-Area OSPFv2" in plan.routing_recommendation.igp_protocol
    assert "eBGP-4 (AS 65300" in (plan.routing_recommendation.egp_protocol or "")

    cfg = plan.device_configs.combined_ios_cfg
    assert "crypto ikev2 proposal" in cfg
    assert "tunnel mode ipsec ipv4" in cfg
    assert "aggregate-address" in cfg
    assert "ACL-IOT-V50-IN" in cfg
    assert "area 1 range 10.30.4.0 255.255.252.0" in cfg
    assert "area 2 range 10.30.0.0 255.255.252.0" in cfg
    assert "area 3 range 10.30.10.0 255.255.255.0" in cfg

    md = format_rationale_markdown(plan)
    assert "# Architectural Rationale Report: Global WAN" in md
    assert "Layer 3 Bitwise VLSM Allocation Table" in md
