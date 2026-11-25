"""Explainable Architecture Rationale Markdown & Log Exporter."""

from netarchitect.models import ArchitecturePlan


def format_rationale_markdown(plan: ArchitecturePlan) -> str:
    """Render a structured engineering rationale report for an ArchitecturePlan."""
    lines = [
        f"# Architectural Rationale Report: {plan.profile_name}",
        "",
        f"- **Topology Tier:** `{plan.topology_tier}`",
        f"- **Total Endpoints:** `{plan.total_endpoints:,}`",
        f"- **IGP Routing:** `{plan.routing_recommendation.igp_protocol}`",
        f"- **EGP / WAN Routing:** `{plan.routing_recommendation.egp_protocol or 'N/A (Single AS)'}`",
        f"- **Root Prefix & Summary Supernet:** `{plan.vlsm_plan.root_prefix}` -> `{plan.vlsm_plan.summary_route_cidr}`",
        f"- **Overall VLSM Host Packing Efficiency:** `{plan.vlsm_plan.overall_utilization_pct:.2f}%`",
        "",
        "## 1. Layer 1 Physical Media & Optical Budget Decisions",
        "",
        "| Link | Endpoints | Distance | Selected Media | Transceiver | Loss / Budget | Propagation |",
        "| :--- | :--- | ---: | :--- | :--- | :--- | ---: |",
    ]
    for m in plan.media_recommendations:
        dist = f"{m.distance_m / 1000:.1f} km" if m.distance_m >= 1000 else f"{m.distance_m:.0f} m"
        budget = (
            f"{m.estimated_optical_loss_db:.2f} / {m.optical_budget_db:.1f} dB"
            if m.estimated_optical_loss_db is not None and m.optical_budget_db is not None
            else (f"{m.estimated_optical_loss_db:.2f} dB (DWDM)" if m.estimated_optical_loss_db else "N/A (Copper)")
        )
        lines.append(
            f"| {m.link_name} | {m.src} <-> {m.dst} | {dist} | {m.selected_media} | "
            f"{m.transceiver} | {budget} | {m.estimated_propagation_ms:.3f} ms |"
        )

    lines.extend(["", "### L1 Engineering Justifications", ""])
    for m in plan.media_recommendations:
        lines.append(f"- **{m.link_name}:** {m.justification}")

    lines.extend(["", "## 2. Layer 2 Switching, VLANs, RSTP & QoS", ""])
    for j in plan.layer2_design.justifications:
        lines.append(f"- {j}")

    lines.extend([
        "",
        "## 3. Layer 3 Bitwise VLSM Allocation Table",
        "",
        f"> {plan.vlsm_plan.justification}",
        "",
        "| Subnet | VLAN | Zone | CIDR | Subnet Mask | Wildcard Mask | Gateway | Broadcast | Req / Usable | Efficiency |",
        "| :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: |",
    ])
    for s in plan.vlsm_plan.subnets:
        vlan_str = str(s.vlan_id) if s.vlan_id is not None else "P2P"
        lines.append(
            f"| {s.name} | {vlan_str} | {s.security_zone} | `{s.cidr}` | `{s.subnet_mask}` | "
            f"`{s.wildcard_mask}` | `{s.gateway_ip}` | `{s.broadcast_address}` | "
            f"{s.requested_hosts} / {s.allocated_usable_hosts} | {s.utilization_pct:.1f}% |"
        )

    lines.extend(["", "## 4. Layer 3 Routing & Domain Isolation Decisions", ""])
    for j in plan.routing_recommendation.justifications:
        lines.append(f"- {j}")

    lines.extend(["", "## 5. Unified Explainable Decision Log", ""])
    for idx, entry in enumerate(plan.architectural_rationale_log, start=1):
        lines.append(f"{idx}. {entry}")

    lines.append("")
    return "\n".join(lines)
