"""Top-level orchestration pipeline for NetArchitect."""

from netarchitect.engines.media_engine import evaluate_layer1_links, evaluate_layer2_design
from netarchitect.engines.routing_engine import select_routing_architecture
from netarchitect.engines.vlsm_engine import allocate_vlsm_subnets
from netarchitect.exporters.cisco_ios import generate_cisco_ios_configs
from netarchitect.models import ArchitecturePlan, NetworkSpecification


def generate_architecture_plan(spec: NetworkSpecification) -> ArchitecturePlan:
    """Execute Input -> L1/L2 Media -> L3 VLSM & Routing -> Explainable IOS Exporter."""
    media_recs = evaluate_layer1_links(spec)
    l2_design = evaluate_layer2_design(spec, media_recs)
    vlsm_plan = allocate_vlsm_subnets(spec)
    routing_rec = select_routing_architecture(spec, vlsm_plan)
    device_configs = generate_cisco_ios_configs(spec, l2_design, vlsm_plan, routing_rec)

    total_endpoints = sum(s.endpoints + s.poe_aps + s.iot_scanners for s in spec.sites)
    if total_endpoints == 0:
        total_endpoints = sum(s.requested_hosts for s in vlsm_plan.subnets)

    rationale_log: list[str] = []
    rationale_log.extend(m.justification for m in media_recs)
    rationale_log.extend(l2_design.justifications)
    rationale_log.append(vlsm_plan.justification)
    rationale_log.extend(routing_rec.justifications)

    return ArchitecturePlan(
        profile_name=spec.profile_name,
        topology_tier=spec.topology_tier,
        total_endpoints=total_endpoints,
        media_recommendations=media_recs,
        layer2_design=l2_design,
        vlsm_plan=vlsm_plan,
        routing_recommendation=routing_rec,
        device_configs=device_configs,
        architectural_rationale_log=rationale_log,
    )
