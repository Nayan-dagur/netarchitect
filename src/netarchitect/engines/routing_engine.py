"""L3 Routing Protocol & Domain Isolation Rationale Engine."""

from netarchitect.engines.vlsm_engine import compute_summary_cidr, ip_to_int, parse_cidr, prefix_to_mask_int
from netarchitect.models import NetworkSpecification, RoutingRecommendation, VLSMPlan


def select_routing_architecture(
    spec: NetworkSpecification,
    vlsm_plan: VLSMPlan,
) -> RoutingRecommendation:
    """Select Single-Area OSPF, Multi-Area OSPF, and/or eBGP with RFC & scaling justifications."""
    subnet_count = len(vlsm_plan.subnets)
    areas = sorted({s.area for s in vlsm_plan.subnets})
    ipsec_needed = any(link.require_ipsec for link in spec.links)
    justifications: list[str] = []

    is_multi_domain = spec.multi_cloud or spec.autonomous_system is not None
    is_large_or_multi_site = spec.multi_site or len(areas) > 1 or subnet_count >= 50

    if not is_multi_domain and not is_large_or_multi_site:
        igp = "Single-Area OSPFv2 (Area 0)"
        egp = None
        area_summaries = _compute_area_summaries(vlsm_plan)
        summary_routes = [vlsm_plan.summary_route_cidr]
        summarization = False
        justifications.append(
            f"Selected {igp} (RFC 2328) because the topology operates within a single autonomous "
            f"system with {subnet_count} subnets (<50-subnet single-area LSDB threshold) at a single site; "
            f"Dijkstra SPF (O(E log V)) guarantees sub-second link-state convergence without ABR complexity."
        )
    elif is_large_or_multi_site and not is_multi_domain:
        igp = "Multi-Area OSPFv2 (Backbone Area 0 + Regional Areas)"
        egp = None
        summarization = True
        area_summaries = _compute_area_summaries(vlsm_plan)
        summary_routes = list(area_summaries.values())
        justifications.append(
            f"Selected {igp} (RFC 2328) because the network spans multiple sites/areas ({areas}) "
            f"requiring hierarchical LSDB isolation so Type-1/Type-2 LSA flooding stays contained within "
            f"each regional area while ABRs inject Type-3 summary LSAs ({', '.join(summary_routes)})."
        )
    else:
        igp = (
            "Multi-Area OSPFv2 (Area 0 + Regional Areas)"
            if len(areas) > 1 or spec.multi_site
            else "Single-Area OSPFv2 (Area 0)"
        )
        egp = f"eBGP-4 (AS {spec.autonomous_system or 65100}, RFC 4271)"
        summarization = True
        area_summaries = _compute_area_summaries(vlsm_plan)
        summary_routes = list(area_summaries.values())
        if vlsm_plan.summary_route_cidr not in summary_routes:
            summary_routes.insert(0, vlsm_plan.summary_route_cidr)
        justifications.append(
            f"Selected {igp} internally paired with {egp} at the WAN/Colo/Cloud boundary because "
            f"multi-site / multi-cloud peering crosses administrative trust boundaries requiring "
            f"AS-PATH loop prevention, policy-based route filtering, and routing domain isolation "
            f"(preventing external WAN flaps from triggering internal OSPF SPF recalculations)."
        )
        justifications.append(
            f"Enabled CIDR route summarization ({', '.join(summary_routes)}) via BGP aggregate-address "
            f"and OSPF ABR 'area range' (RFC 4632) to minimize RIB/FIB table size across WAN edges."
        )

    if ipsec_needed:
        ipsec_links = [l.name for l in spec.links if l.require_ipsec]
        justifications.append(
            f"Enabled IKEv2 / IPsec ESP (AES-256-GCM + SHA-256, RFC 4301/7296) over VTI Tunnel interfaces "
            f"for WAN links ({', '.join(ipsec_links)}) to provide confidentiality, anti-replay protection, "
            f"and dynamic OSPF/BGP neighbor adjacency over untrusted Internet/cloud underlay paths."
        )

    return RoutingRecommendation(
        igp_protocol=igp,
        egp_protocol=egp,
        ospf_areas=areas if areas else [0],
        route_summarization_enabled=summarization,
        summary_routes=summary_routes,
        area_summary_routes=area_summaries,
        ipsec_vpn_enabled=ipsec_needed,
        justifications=justifications,
    )


def _compute_area_summaries(vlsm_plan: VLSMPlan) -> dict[int, str]:
    by_area: dict[int, list[tuple[int, int]]] = {}
    for subnet in vlsm_plan.subnets:
        net_int, prefix_len = parse_cidr(subnet.cidr)
        mask_int = prefix_to_mask_int(prefix_len)
        bcast_int = net_int | ((~mask_int) & 0xFFFFFFFF)
        by_area.setdefault(subnet.area, []).append((net_int, bcast_int))
    return {area_id: compute_summary_cidr(ranges) for area_id, ranges in sorted(by_area.items())}
