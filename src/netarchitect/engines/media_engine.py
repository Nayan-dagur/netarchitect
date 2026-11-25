"""L1 Physical Media & L2 Switching/QoS Physics Engine."""

from netarchitect.exceptions import ParameterValidationError, PhysicalDistanceViolationError
from netarchitect.models import (
    Layer2Design,
    LinkSpec,
    MediaRecommendation,
    NetworkSpecification,
)

# Physical constants (IEEE 802.3 & optical fiber standards)
COPPER_MAX_M = 100.0
OM4_MMF_10G_MAX_M = 400.0
OS2_LR_MAX_M = 10_000.0
OS2_ER_MAX_M = 40_000.0
OS2_ZR_MAX_M = 80_000.0

# Optical budget parameters
CONNECTOR_LOSS_DB = 0.75  # Per mated LC/UPC connector pair (2 pairs per link = 1.50 dB)
SAFETY_MARGIN_DB = 3.0    # Aging, bend, and repair splice margin
ATTENUATION_1310NM_DB_PER_KM = 0.35
ATTENUATION_1550NM_DB_PER_KM = 0.25
LR_OPTICAL_BUDGET_DB = 8.2
ER_OPTICAL_BUDGET_DB = 15.0
ZR_OPTICAL_BUDGET_DB = 23.0

# Signal propagation speeds
COPPER_VELOCITY_FACTOR = 0.68  # ~68% speed of light (~4.9 ns/m)
FIBER_REFRACTIVE_INDEX = 1.468  # SMF-28 silica core (~4.9 us/km)
SPEED_OF_LIGHT_M_PER_S = 299_792_458.0


def _propagation_delay_ms(distance_m: float, is_copper: bool) -> float:
    speed = (
        SPEED_OF_LIGHT_M_PER_S * COPPER_VELOCITY_FACTOR
        if is_copper
        else SPEED_OF_LIGHT_M_PER_S / FIBER_REFRACTIVE_INDEX
    )
    return round((distance_m / speed) * 1000.0, 4)


def _format_distance(distance_m: float) -> str:
    if distance_m >= 1000.0:
        km = distance_m / 1000.0
        return f"{km:.1f} km" if km % 1 else f"{int(km)} km"
    return f"{distance_m:.0f}m" if distance_m.is_integer() else f"{distance_m:.1f}m"


def _evaluate_single_link(link: LinkSpec) -> MediaRecommendation:
    d = link.distance_m
    dist_label = _format_distance(d)
    req = link.requested_media

    # Boundary enforcement: explicit copper request > 100m
    if req == "copper" and d > COPPER_MAX_M:
        raise PhysicalDistanceViolationError(
            link_name=link.name,
            requested_media="Cat6a Copper (10GBASE-T)",
            distance_m=d,
            max_distance_m=COPPER_MAX_M,
            warning=(
                f"Signal attenuation warning: Cat6a insertion loss (>20.9 dB @ 500 MHz), "
                f"alien crosstalk (ANEXT), and propagation delay skew violate IEEE 802.3an / "
                f"ANSI/TIA-568-D 100m horizontal channel limits at {dist_label}. "
                f"Use OM4 MMF (<=400m) or OS2 SMF (>400m)."
            ),
        )

    # Boundary enforcement: explicit MMF request > 400m
    if req == "mmf" and d > OM4_MMF_10G_MAX_M:
        raise PhysicalDistanceViolationError(
            link_name=link.name,
            requested_media="OM4 Multimode Fiber (10GBASE-SR)",
            distance_m=d,
            max_distance_m=OM4_MMF_10G_MAX_M,
            warning=(
                f"Modal dispersion warning: 850nm VCSEL differential mode delay (DMD) exceeds "
                f"OM4 4700 MHz*km effective modal bandwidth limit (400m for 10GBASE-SR per IEEE 802.3ae) "
                f"at {dist_label}. Upgrade to OS2 Single-Mode Fiber."
            ),
        )

    # Select medium when auto or valid explicit choice
    if req == "copper" or (req == "auto" and d <= COPPER_MAX_M):
        prop_ms = _propagation_delay_ms(d, is_copper=True)
        media = "Cat6a Twisted-Pair Copper"
        transceiver = "10GBASE-T RJ-45 (Integrated PHY)"
        std = "IEEE 802.3an (500 MHz, <=100m)"
        loss_db = None
        budget_db = None
        justification = (
            f"Selected {media} ({transceiver}) for link '{link.name}' ({link.src} <-> {link.dst}) "
            f"because run distance ({dist_label}) is within the {int(COPPER_MAX_M)}m IEEE 802.3an "
            f"channel limit for {link.bandwidth_gbps:g} Gbps, eliminating SFP+ optical transceiver cost "
            f"while supporting PoE++ power delivery (estimated propagation delay: {prop_ms:.4f} ms)."
        )
    elif req == "mmf" or (req == "auto" and COPPER_MAX_M < d <= OM4_MMF_10G_MAX_M):
        prop_ms = _propagation_delay_ms(d, is_copper=False)
        splices = 0
        fiber_loss = (d / 1000.0) * 3.0  # ~3.0 dB/km @ 850nm for OM4
        total_loss = round(fiber_loss + (2 * CONNECTOR_LOSS_DB) + SAFETY_MARGIN_DB, 2)
        budget = 7.3  # IEEE 802.3ae 10GBASE-SR OM4 channel insertion loss budget (~2.6-2.9 dB passive + margin)
        media = "OM4 Multimode Fiber (50/125 um)"
        transceiver = "10GBASE-SR SFP+"
        std = "850nm VCSEL / IEEE 802.3ae (4700 MHz*km EMB)"
        loss_db = round(fiber_loss + (2 * CONNECTOR_LOSS_DB), 2)
        budget_db = 2.9  # Passive channel insertion loss limit for 400m OM4
        justification = (
            f"Selected {media} ({transceiver}) for link '{link.name}' ({link.src} <-> {link.dst}) "
            f"because run distance ({dist_label}) exceeds the {int(COPPER_MAX_M)}m IEEE 802.3an copper "
            f"limit yet stays within the {int(OM4_MMF_10G_MAX_M)}m 850nm modal dispersion reach of OM4 "
            f"(4700 MHz*km EMB; passive channel loss {loss_db:.2f} dB <= {budget_db:.1f} dB limit, "
            f"propagation delay: {prop_ms:.4f} ms)."
        )
    else:
        # OS2 Single-Mode Fiber (>400m or explicit smf)
        prop_ms = _propagation_delay_ms(d, is_copper=False)
        km = d / 1000.0
        splices = max(0, int(km // 4))  # Assume 1 fusion splice per 4 km reel
        splice_loss = splices * 0.1

        if d <= OS2_LR_MAX_M:
            fiber_loss = km * ATTENUATION_1310NM_DB_PER_KM
            loss_db = round(fiber_loss + (2 * CONNECTOR_LOSS_DB) + splice_loss + SAFETY_MARGIN_DB, 2)
            budget_db = LR_OPTICAL_BUDGET_DB
            media = "OS2 Single-Mode Fiber (9/125 um)"
            transceiver = "10GBASE-LR SFP+"
            std = "1310nm Fabry-Perot/DFB / IEEE 802.3ae (<=10 km)"
            tier_reason = (
                f"exceeds the {int(OM4_MMF_10G_MAX_M)}m attenuation/dispersion limit of OM4 Multimode Fiber "
                f"and fits within the 10 km reach of 1310nm 10GBASE-LR"
            )
        elif d <= OS2_ER_MAX_M:
            fiber_loss = km * ATTENUATION_1550NM_DB_PER_KM
            loss_db = round(fiber_loss + (2 * CONNECTOR_LOSS_DB) + splice_loss + SAFETY_MARGIN_DB, 2)
            budget_db = ER_OPTICAL_BUDGET_DB
            media = "OS2 Single-Mode Fiber (9/125 um)"
            transceiver = "10GBASE-ER SFP+"
            std = "1550nm EML / IEEE 802.3ae (<=40 km)"
            tier_reason = (
                f"exceeds both the {int(OM4_MMF_10G_MAX_M)}m limit of OM4 Multimode Fiber and the 10 km "
                f"chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation ({ATTENUATION_1550NM_DB_PER_KM} dB/km) ER optics"
            )
        elif d <= OS2_ZR_MAX_M:
            fiber_loss = km * ATTENUATION_1550NM_DB_PER_KM
            loss_db = round(fiber_loss + (2 * CONNECTOR_LOSS_DB) + splice_loss + SAFETY_MARGIN_DB, 2)
            budget_db = ZR_OPTICAL_BUDGET_DB
            media = "OS2 Single-Mode Fiber (9/125 um)"
            transceiver = "10GBASE-ZR SFP+"
            std = "1550nm DWDM/ZR (<=80 km)"
            tier_reason = (
                f"exceeds the 40 km reach of 10GBASE-ER and requires high-sensitivity APD receiver 1550nm ZR optics"
            )
        else:
            # Long-haul WAN (>80 km): Carrier DWDM / MPLS / IPsec underlay
            fiber_loss = km * ATTENUATION_1550NM_DB_PER_KM
            loss_db = round(fiber_loss + (2 * CONNECTOR_LOSS_DB) + splice_loss + SAFETY_MARGIN_DB, 2)
            budget_db = None
            media = "Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop)"
            transceiver = "10GBASE-LR Access + Carrier DWDM/MPLS Transport"
            std = "ITU-T G.652.D / RFC 4301 IPsec Overlay"
            tier_reason = (
                f"exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating "
                f"carrier-amplified DWDM/WAN transport with local OS2 access handoff"
            )

        budget_clause = (
            f"calculated optical link loss is {loss_db:.2f} dB (fiber + 2x{CONNECTOR_LOSS_DB} dB connectors + "
            f"{splice_loss:.1f} dB splices + {SAFETY_MARGIN_DB:.1f} dB margin) within the {budget_db:.1f} dB optical budget"
            if budget_db is not None
            else f"unamplified attenuation ({loss_db:.2f} dB) exceeds passive transceiver budgets; carrier EDFA/regen required"
        )
        justification = (
            f"Selected {media} ({transceiver}) for link '{link.name}' ({link.src} <-> {link.dst}) "
            f"because link distance ({dist_label}) {tier_reason}; {budget_clause} "
            f"(one-way fiber propagation delay: {prop_ms:.3f} ms)."
        )

    if link.max_latency_ms is not None and prop_ms > link.max_latency_ms:
        raise ParameterValidationError(
            f"Link '{link.name}' physical speed-of-light propagation delay ({prop_ms:.3f} ms) "
            f"exceeds requested max_latency_ms ({link.max_latency_ms:.3f} ms)."
        )

    return MediaRecommendation(
        link_name=link.name,
        src=link.src,
        dst=link.dst,
        distance_m=d,
        bandwidth_gbps=link.bandwidth_gbps,
        selected_media=media,
        transceiver=transceiver,
        wavelength_or_standard=std,
        estimated_optical_loss_db=loss_db,
        optical_budget_db=budget_db,
        estimated_propagation_ms=prop_ms,
        justification=justification,
    )


def evaluate_layer1_links(spec: NetworkSpecification) -> list[MediaRecommendation]:
    """Evaluate all physical links against IEEE 802.3 and optical budget constraints."""
    return [_evaluate_single_link(link) for link in spec.links]


def evaluate_layer2_design(
    spec: NetworkSpecification,
    media_recs: list[MediaRecommendation],
) -> Layer2Design:
    """Derive L2 switching, 802.1Q VLAN pruning, RSTP, PoE, EVPL, and QoS rules."""
    vlans = sorted(s.vlan_id for s in spec.subnet_requests if s.vlan_id is not None)
    if not vlans:
        vlans = [10, 20, 99]

    total_poe_aps = sum(site.poe_aps for site in spec.sites)
    # 30W per IEEE 802.3at PoE+ AP + 20% headroom -> rounded up, or 60W for Wi-Fi 6E/7
    total_poe_watts = int(total_poe_aps * 30 * 1.2)

    evpl_enabled = spec.topology_tier == "metro_man" or any(
        l.role == "man" and l.dual_homed for l in spec.links
    )
    qos_profile: str | None = None
    if spec.target_latency_ms is not None and spec.target_latency_ms <= 5.0:
        qos_profile = "LLQ-Sub5ms-Strict-Priority (DSCP EF 46 -> 30% PQ, AF41 -> 35% CBWFQ)"
    elif any(s.security_zone == "voice" for s in spec.subnet_requests):
        qos_profile = "Enterprise-Voice-Priority (DSCP EF 46 PQ, CS3 Call-Signaling)"

    vlan_list_str = ",".join(str(v) for v in vlans)
    justifications = [
        f"Configured IEEE 802.1Q trunk pruning (allowed VLANs: {vlan_list_str}) with unused native VLAN 999 "
        f"(BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.",
        f"Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs {vlan_list_str} "
        f"plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.",
    ]

    if total_poe_aps > 0:
        justifications.append(
            f"Provisioned {total_poe_watts}W IEEE 802.3at (PoE+) switch power budget across {total_poe_aps} "
            f"wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops."
        )

    if evpl_enabled:
        justifications.append(
            "Enabled MEF Carrier Ethernet EVPL (Ethernet Virtual Private Line) over dual-homed OS2 SMF links "
            "to multiplex isolated customer/colo VLANs via 802.1ad Q-in-Q with sub-50ms carrier ring protection."
        )

    if qos_profile:
        max_prop = max(m.estimated_propagation_ms for m in media_recs)
        justifications.append(
            f"Applied '{qos_profile}' queuing because target SLA latency ({spec.target_latency_ms or 10.0} ms) "
            f"requires deterministic serialization delay bounds above the {max_prop:.3f} ms physical fiber propagation floor (RFC 4594)."
        )

    return Layer2Design(
        spanning_tree_mode="rapid-pvst (IEEE 802.1w)",
        root_bridge_vlan_scope=vlan_list_str,
        native_vlan=999,
        allowed_vlans=vlans,
        total_poe_budget_watts=total_poe_watts,
        qos_profile=qos_profile,
        evpl_enabled=evpl_enabled,
        justifications=justifications,
    )
