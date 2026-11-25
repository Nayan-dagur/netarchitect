"""Unit tests for Bitwise VLSM Allocator, wildcard masks, and exhaustion boundaries."""

import pytest

from netarchitect.engines.vlsm_engine import (
    allocate_vlsm_subnets,
    compute_summary_cidr,
    int_to_ip,
    ip_to_int,
    parse_cidr,
    prefix_to_mask_int,
)
from netarchitect.exceptions import AddressSpaceExhaustionError, ParameterValidationError
from netarchitect.models import LinkSpec, NetworkSpecification, SubnetRequest


def _vlsm_spec(root_prefix: str, requests: list[tuple[str, int, str]]) -> NetworkSpecification:
    return NetworkSpecification(
        profile_name="VLSMTest",
        topology_tier="custom",
        links=[LinkSpec(name="L1", src="A", dst="B", distance_m=50.0)],
        root_prefix=root_prefix,
        subnet_requests=[
            SubnetRequest(name=name, hosts=hosts, vlan_id=(None if zone == "wan_p2p" else idx + 10), security_zone=zone)
            for idx, (name, hosts, zone) in enumerate(requests)
        ],
    )


def test_bitwise_wildcard_masks_edge_cases() -> None:
    # /32, /30, /29, /24, /22, /16 wildcard invariants
    expected = [
        (32, "255.255.255.255", "0.0.0.0"),
        (30, "255.255.255.252", "0.0.0.3"),
        (29, "255.255.255.248", "0.0.0.7"),
        (24, "255.255.255.0", "0.0.0.255"),
        (22, "255.255.252.0", "0.0.3.255"),
        (16, "255.255.0.0", "0.0.255.255"),
    ]
    for plen, mask_str, wildcard_str in expected:
        m = prefix_to_mask_int(plen)
        w = (~m) & 0xFFFFFFFF
        assert int_to_ip(m) == mask_str
        assert int_to_ip(w) == wildcard_str


def test_descending_allocation_and_zero_overlap() -> None:
    # Out-of-order inputs: /30, /24, /21, /26
    spec = _vlsm_spec(
        "10.50.0.0/16",
        [
            ("P2P-Link", 2, "wan_p2p"),
            ("Small-Mgmt", 50, "mgmt"),
            ("Large-Campus", 1500, "corp"),
            ("Voice-VLAN", 200, "voice"),
        ],
    )
    plan = allocate_vlsm_subnets(spec)
    # Must sort descending: 1500 (/21), 200 (/24), 50 (/26), 2 (/30)
    assert [s.name for s in plan.subnets] == ["Large-Campus", "Voice-VLAN", "Small-Mgmt", "P2P-Link"]
    assert plan.subnets[0].cidr == "10.50.0.0/21"
    assert plan.subnets[0].wildcard_mask == "0.0.7.255"
    assert plan.subnets[0].broadcast_address == "10.50.7.255"
    assert plan.subnets[0].gateway_ip == "10.50.0.1"

    assert plan.subnets[1].cidr == "10.50.8.0/24"
    assert plan.subnets[1].wildcard_mask == "0.0.0.255"

    assert plan.subnets[2].cidr == "10.50.9.0/26"
    assert plan.subnets[2].wildcard_mask == "0.0.0.63"

    assert plan.subnets[3].cidr == "10.50.9.64/30"
    assert plan.subnets[3].wildcard_mask == "0.0.0.3"
    assert plan.subnets[3].broadcast_address == "10.50.9.67"


def test_exact_254_vs_255_host_boundary() -> None:
    spec_254 = _vlsm_spec("192.168.0.0/23", [("Exact254", 254, "corp")])
    plan_254 = allocate_vlsm_subnets(spec_254)
    assert plan_254.subnets[0].prefix_length == 24
    assert plan_254.subnets[0].utilization_pct == 100.0

    spec_255 = _vlsm_spec("192.168.0.0/23", [("Need255", 255, "corp")])
    plan_255 = allocate_vlsm_subnets(spec_255)
    assert plan_255.subnets[0].prefix_length == 23
    assert plan_255.subnets[0].allocated_usable_hosts == 510


def test_address_space_exhaustion_raises_error() -> None:
    # A /24 (256 addrs) cannot hold 200 hosts (/24 = 256) + 2 hosts (/30 = 4)
    spec = _vlsm_spec(
        "10.99.1.0/24",
        [
            ("Main-LAN", 200, "corp"),
            ("Overflow-P2P", 2, "wan_p2p"),
        ],
    )
    with pytest.raises(AddressSpaceExhaustionError) as exc_info:
        allocate_vlsm_subnets(spec)
    assert "Overflow-P2P" in str(exc_info.value)


def test_single_subnet_larger_than_root_prefix_raises_exhaustion() -> None:
    spec = _vlsm_spec("10.99.1.0/24", [("TooBig", 300, "corp")])
    with pytest.raises(AddressSpaceExhaustionError):
        allocate_vlsm_subnets(spec)


def test_non_canonical_root_prefix_rejected() -> None:
    with pytest.raises(ParameterValidationError):
        parse_cidr("10.10.1.5/24")


def test_bitwise_summary_route_calculation() -> None:
    # 10.10.0.0/24 and 10.10.1.0/24 summarize to 10.10.0.0/23
    r1 = (ip_to_int("10.10.0.0"), ip_to_int("10.10.0.255"))
    r2 = (ip_to_int("10.10.1.0"), ip_to_int("10.10.1.255"))
    assert compute_summary_cidr([r1, r2]) == "10.10.0.0/23"
