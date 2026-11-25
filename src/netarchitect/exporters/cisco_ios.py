"""Copy-paste ready Cisco IOS configuration generator (Switches, Routers, SVIs, ACLs)."""

from netarchitect.engines.vlsm_engine import int_to_ip, parse_cidr, prefix_to_mask_int
from netarchitect.models import (
    AllocatedSubnet,
    DeviceConfigBundle,
    Layer2Design,
    NetworkSpecification,
    RoutingRecommendation,
    VLSMPlan,
)


def _sanitized_hostname(name: str, suffix: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in name).strip("-")
    return f"{cleaned[:16].upper()}-{suffix}"


def _build_acls(subnets: list[AllocatedSubnet]) -> list[str]:
    """Generate Extended ACLs isolating IoT/DMZ zones from Corp and Management subnets."""
    lines: list[str] = ["! === Extended Security ACLs (Zero-Trust Zone Isolation) ==="]
    corp_or_mgmt = [s for s in subnets if s.security_zone in {"corp", "mgmt", "voice"}]
    restricted_zones = [s for s in subnets if s.security_zone in {"iot", "dmz"}]

    if not restricted_zones:
        lines.extend([
            "ip access-list extended ACL-MGMT-VTY",
            " remark Restrict SSH management to internal administrative subnets",
        ])
        mgmt_subnets = [s for s in subnets if s.security_zone == "mgmt"] or subnets[:1]
        for s in mgmt_subnets:
            lines.append(f" permit tcp {s.network_address} {s.wildcard_mask} any eq 22")
        lines.append(" deny ip any any log")
        lines.append("!")
        return lines

    for rz in restricted_zones:
        acl_name = f"ACL-{rz.security_zone.upper()}-V{rz.vlan_id or 0}-IN"
        lines.append(f"ip access-list extended {acl_name}")
        lines.append(f" remark Isolate {rz.name} ({rz.cidr}) from internal Corp/Mgmt planes")
        lines.append(f" permit udp {rz.network_address} {rz.wildcard_mask} any eq bootps")
        lines.append(f" permit udp {rz.network_address} {rz.wildcard_mask} any eq domain")
        for target in corp_or_mgmt:
            lines.append(
                f" deny ip {rz.network_address} {rz.wildcard_mask} "
                f"{target.network_address} {target.wildcard_mask} log"
            )
        lines.append(f" permit ip {rz.network_address} {rz.wildcard_mask} any")
        lines.append("!")
    return lines


def generate_cisco_ios_configs(
    spec: NetworkSpecification,
    l2: Layer2Design,
    vlsm: VLSMPlan,
    routing: RoutingRecommendation,
) -> DeviceConfigBundle:
    """Build copy-paste ready IOS configs for Core Switch, Access Switch, and Edge Router."""
    core_host = _sanitized_hostname(spec.profile_name, "CORE-SW1")
    acc_host = _sanitized_hostname(spec.profile_name, "ACC-SW1")
    rtr_host = _sanitized_hostname(spec.profile_name, "EDGE-RTR1")

    vlan_subnets = [s for s in vlsm.subnets if s.vlan_id is not None]
    p2p_subnets = [s for s in vlsm.subnets if s.vlan_id is None]
    allowed_vlan_csv = l2.root_bridge_vlan_scope

    # 1. Core L3 Switch (Catalyst 3560/3650 compatible)
    core_lines = [
        f"! ============================================================",
        f"! {core_host} - Layer 3 Core/Distribution Switch Config",
        f"! Profile: {spec.profile_name} | Root Prefix: {vlsm.root_prefix}",
        f"! ============================================================",
        "enable",
        "configure terminal",
        f"hostname {core_host}",
        "no ip domain-lookup",
        "service password-encryption",
        "ip routing",
        "!",
        "! --- IEEE 802.1Q VLAN Database & Blackhole Native VLAN ---",
        f"vlan {l2.native_vlan}",
        " name BLACKHOLE_NATIVE",
        " exit",
    ]
    for s in vlan_subnets:
        vname = "".join(c if c.isalnum() or c == "_" else "_" for c in s.name).upper()[:24]
        core_lines.extend([f"vlan {s.vlan_id}", f" name {vname}", " exit"])

    core_lines.extend([
        "!",
        "! --- IEEE 802.1w Rapid Spanning Tree (Root Primary) ---",
        "spanning-tree mode rapid-pvst",
        f"spanning-tree vlan {allowed_vlan_csv} root primary",
        "spanning-tree portfast bpduguard default",
        "!",
        "! --- Pruned 802.1Q Downlink Trunks ---",
        "interface GigabitEthernet0/1",
        f" description Trunk to {acc_host} (Pruned 802.1Q)",
        " switchport trunk encapsulation dot1q",
        " switchport mode trunk",
        f" switchport trunk native vlan {l2.native_vlan}",
        f" switchport trunk allowed vlan {allowed_vlan_csv}",
        " switchport nonegotiate",
        " spanning-tree guard root",
        " no shutdown",
        "!",
        "! --- Routed Uplinks & Switch Virtual Interfaces (SVIs) ---",
    ])

    for s in vlan_subnets:
        core_lines.extend([
            f"interface Vlan{s.vlan_id}",
            f" description {s.name} [{s.security_zone.upper()}] ({s.cidr})",
            f" ip address {s.gateway_ip} {s.subnet_mask}",
        ])
        if s.security_zone in {"iot", "dmz"}:
            core_lines.append(f" ip access-group ACL-{s.security_zone.upper()}-V{s.vlan_id}-IN in")
        core_lines.extend([" no shutdown", "!"])

    core_lines.extend(_build_acls(vlsm.subnets))

    # Core OSPF stanza
    core_lines.extend([
        "! --- Core Switch OSPFv2 Routing ---",
        "router ospf 1",
        " router-id 10.255.255.10",
        " passive-interface default",
        " no passive-interface GigabitEthernet0/24",
    ])
    for s in vlan_subnets:
        core_lines.append(f" network {s.network_address} {s.wildcard_mask} area {s.area}")
    core_lines.extend(["!", "end", "write memory", ""])

    # 2. Access L2 Switch (Catalyst 2960 compatible)
    corp_vlan = next((s.vlan_id for s in vlan_subnets if s.security_zone == "corp"), l2.allowed_vlans[0])
    mgmt_subnet = next((s for s in vlan_subnets if s.security_zone == "mgmt"), None)
    acc_lines = [
        f"! ============================================================",
        f"! {acc_host} - Layer 2 Access Switch Config",
        f"! Profile: {spec.profile_name} | PoE Budget: {l2.total_poe_budget_watts}W",
        f"! ============================================================",
        "enable",
        "configure terminal",
        f"hostname {acc_host}",
        "no ip domain-lookup",
        "service password-encryption",
        "!",
        f"vlan {l2.native_vlan}",
        " name BLACKHOLE_NATIVE",
        " exit",
    ]
    for s in vlan_subnets:
        vname = "".join(c if c.isalnum() or c == "_" else "_" for c in s.name).upper()[:24]
        acc_lines.extend([f"vlan {s.vlan_id}", f" name {vname}", " exit"])

    acc_lines.extend([
        "!",
        "spanning-tree mode rapid-pvst",
        "!",
        "! --- Uplink Trunk to Core Switch ---",
        "interface GigabitEthernet0/1",
        f" description Uplink to {core_host}",
        " switchport mode trunk",
        f" switchport trunk native vlan {l2.native_vlan}",
        f" switchport trunk allowed vlan {allowed_vlan_csv}",
        " switchport nonegotiate",
        " no shutdown",
        "!",
        "! --- Access Edge Ports (PortFast + BPDUGuard) ---",
        "interface range FastEthernet0/1 - 24",
        f" description Endpoint Access Ports (VLAN {corp_vlan})",
        " switchport mode access",
        f" switchport access vlan {corp_vlan}",
        " spanning-tree portfast",
        " spanning-tree bpduguard enable",
        " no shutdown",
        "!",
    ])
    if mgmt_subnet:
        acc_lines.extend([
            f"interface Vlan{mgmt_subnet.vlan_id}",
            f" description Management SVI ({mgmt_subnet.cidr})",
            f" ip address {mgmt_subnet.first_usable_ip} {mgmt_subnet.subnet_mask}",
            " no shutdown",
            "!",
            f"ip default-gateway {mgmt_subnet.gateway_ip}",
        ])
    acc_lines.extend(["end", "write memory", ""])

    # 3. Edge / WAN Router (ISR 2911/4331 compatible)
    rtr_lines = [
        f"! ============================================================",
        f"! {rtr_host} - Edge / WAN Router Config",
        f"! IGP: {routing.igp_protocol} | EGP: {routing.egp_protocol or 'None'}",
        f"! ============================================================",
        "enable",
        "configure terminal",
        f"hostname {rtr_host}",
        "no ip domain-lookup",
        "service password-encryption",
        "!",
        "interface Loopback0",
        " description OSPF/BGP Router-ID Loopback",
        " ip address 10.255.255.1 255.255.255.255",
        "!",
    ]

    if p2p_subnets:
        for idx, p2p in enumerate(p2p_subnets[:4]):
            rtr_lines.extend([
                f"interface GigabitEthernet0/{idx}",
                f" description {p2p.name} ({p2p.cidr})",
                f" ip address {p2p.gateway_ip} {p2p.subnet_mask}",
                " no shutdown",
                "!",
            ])
    else:
        first_sub = vlsm.subnets[0]
        rtr_lines.extend([
            "interface GigabitEthernet0/0",
            f" description Core Uplink ({first_sub.cidr})",
            f" ip address {first_sub.last_usable_ip} {first_sub.subnet_mask}",
            " no shutdown",
            "!",
        ])

    if l2.qos_profile:
        rtr_lines.extend([
            "! --- Sub-5ms Low-Latency Queuing (QoS RFC 4594) ---",
            "class-map match-any CM-REALTIME-EF",
            " match dscp ef",
            "class-map match-any CM-CRITICAL-AF41",
            " match dscp af41",
            "!",
            "policy-map PM-WAN-QOS",
            " class CM-REALTIME-EF",
            "  priority percent 30",
            " class CM-CRITICAL-AF41",
            "  bandwidth percent 35",
            " class class-default",
            "  fair-queue",
            "!",
            "interface GigabitEthernet0/0",
            " service-policy output PM-WAN-QOS",
            "!",
        ])

    if routing.ipsec_vpn_enabled:
        rtr_lines.extend([
            "! --- IKEv2 / IPsec AES-256-GCM Site-to-Site VTI (RFC 4301/7296) ---",
            "crypto ikev2 proposal IKEV2-PROP-NETARCH",
            " encryption aes-gcm-256",
            " prf sha256",
            " group 14",
            "!",
            "crypto ikev2 policy IKEV2-POL-NETARCH",
            " proposal IKEV2-PROP-NETARCH",
            "!",
            "crypto ipsec transform-set TS-AES256-GCM esp-gcm 256",
            " mode tunnel",
            "!",
            "crypto ipsec profile PROF-IPSEC-VTI",
            " set transform-set TS-AES256-GCM",
            "!",
            "interface Tunnel0",
            " description Encrypted WAN Overlay VTI",
            " ip address 172.31.255.1 255.255.255.252",
            " tunnel source GigabitEthernet0/0",
            " tunnel mode ipsec ipv4",
            " tunnel destination 203.0.113.2",
            " tunnel protection ipsec profile PROF-IPSEC-VTI",
            "!",
        ])

    rtr_lines.extend([
        "! --- OSPFv2 Process ---",
        "router ospf 1",
        " router-id 10.255.255.1",
        " passive-interface default",
        " no passive-interface GigabitEthernet0/0",
    ])
    if routing.ipsec_vpn_enabled:
        rtr_lines.append(" no passive-interface Tunnel0")
    for s in vlsm.subnets:
        rtr_lines.append(f" network {s.network_address} {s.wildcard_mask} area {s.area}")

    if routing.route_summarization_enabled and len(routing.ospf_areas) > 1:
        for area_id, sum_cidr in zip(routing.ospf_areas, routing.summary_routes):
            net_int, plen = parse_cidr(sum_cidr)
            mask_str = int_to_ip(prefix_to_mask_int(plen))
            rtr_lines.append(f" area {area_id} range {int_to_ip(net_int)} {mask_str}")
    rtr_lines.append("!")

    if routing.egp_protocol:
        asn = spec.autonomous_system or 65100
        sum_net, sum_plen = parse_cidr(vlsm.summary_route_cidr)
        sum_mask = int_to_ip(prefix_to_mask_int(sum_plen))
        rtr_lines.extend([
            f"! --- eBGP-4 WAN / Cloud Peering (AS {asn}) ---",
            f"router bgp {asn}",
            " bgp router-id 10.255.255.1",
            " bgp log-neighbor-changes",
            " neighbor 198.51.100.2 remote-as 64512",
            " neighbor 198.51.100.2 description Upstream WAN / Cloud Peering",
            f" network {int_to_ip(sum_net)} mask {sum_mask}",
            f" aggregate-address {int_to_ip(sum_net)} {sum_mask} summary-only",
            "!",
        ])

    rtr_lines.extend(["end", "write memory", ""])

    core_cfg = "\n".join(core_lines)
    acc_cfg = "\n".join(acc_lines)
    rtr_cfg = "\n".join(rtr_lines)
    combined = "\n".join([core_cfg, acc_cfg, rtr_cfg])

    return DeviceConfigBundle(
        core_switch_ios=core_cfg,
        access_switch_ios=acc_cfg,
        edge_router_ios=rtr_cfg,
        combined_ios_cfg=combined,
    )
