"""Unit tests for L3 Routing Protocol Selection & Domain Isolation Engine."""

from netarchitect.engines.routing_engine import select_routing_architecture
from netarchitect.engines.vlsm_engine import allocate_vlsm_subnets
from netarchitect.models import LinkSpec, NetworkSpecification, SubnetRequest


def test_single_as_under_50_subnets_selects_ospf_area_0() -> None:
    spec = NetworkSpecification(
        profile_name="SingleCampus",
        topology_tier="campus_lan",
        multi_site=False,
        multi_cloud=False,
        links=[LinkSpec(name="L1", src="A", dst="B", distance_m=150.0)],
        root_prefix="10.1.0.0/16",
        subnet_requests=[
            SubnetRequest(name=f"VLAN-{i}", hosts=30, vlan_id=10 + i, security_zone="corp", area=0)
            for i in range(10)
        ],
    )
    vlsm = allocate_vlsm_subnets(spec)
    routing = select_routing_architecture(spec, vlsm)
    assert routing.igp_protocol == "Single-Area OSPFv2 (Area 0)"
    assert routing.egp_protocol is None
    assert routing.ospf_areas == [0]


def test_50_or_more_subnets_triggers_multi_area_ospf() -> None:
    spec = NetworkSpecification(
        profile_name="LargeCampus",
        topology_tier="custom",
        multi_site=False,
        multi_cloud=False,
        links=[LinkSpec(name="L1", src="A", dst="B", distance_m=200.0)],
        root_prefix="10.2.0.0/16",
        subnet_requests=[
            SubnetRequest(name=f"Sub-{i}", hosts=14, vlan_id=100 + i, security_zone="corp", area=i % 3)
            for i in range(52)
        ],
    )
    vlsm = allocate_vlsm_subnets(spec)
    routing = select_routing_architecture(spec, vlsm)
    assert "Multi-Area OSPFv2" in routing.igp_protocol
    assert routing.route_summarization_enabled is True


def test_multi_site_multi_cloud_selects_ebgp_and_ipsec() -> None:
    spec = NetworkSpecification(
        profile_name="CloudWAN",
        topology_tier="global_wan",
        multi_site=True,
        multi_cloud=True,
        autonomous_system=65400,
        links=[
            LinkSpec(name="WAN-1", src="HQ", dst="VPC", distance_m=500_000.0, require_ipsec=True),
        ],
        root_prefix="10.3.0.0/16",
        subnet_requests=[
            SubnetRequest(name="HQ-Corp", hosts=100, vlan_id=10, security_zone="corp", area=0),
            SubnetRequest(name="VPC-App", hosts=100, vlan_id=20, security_zone="cloud", area=1),
        ],
    )
    vlsm = allocate_vlsm_subnets(spec)
    routing = select_routing_architecture(spec, vlsm)
    assert "Multi-Area OSPFv2" in routing.igp_protocol
    assert routing.egp_protocol is not None and "eBGP-4 (AS 65400" in routing.egp_protocol
    assert routing.ipsec_vpn_enabled is True
    assert routing.route_summarization_enabled is True
