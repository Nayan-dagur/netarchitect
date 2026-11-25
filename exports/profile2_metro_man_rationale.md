# Architectural Rationale Report: Metro MAN

- **Topology Tier:** `metro_man`
- **Total Endpoints:** `514`
- **IGP Routing:** `Multi-Area OSPFv2 (Area 0 + Regional Areas)`
- **EGP / WAN Routing:** `eBGP-4 (AS 65200, RFC 4271)`
- **Root Prefix & Summary Supernet:** `10.20.0.0/16` -> `10.20.0.0/22`
- **Overall VLSM Host Packing Efficiency:** `88.89%`

## 1. Layer 1 Physical Media & Optical Budget Decisions

| Link | Endpoints | Distance | Selected Media | Transceiver | Loss / Budget | Propagation |
| :--- | :--- | ---: | :--- | :--- | :--- | ---: |
| HQ-Access-LAN | HQ-Core <-> HQ-Trading-Desks | 60 m | Cat6a Twisted-Pair Copper | 10GBASE-T RJ-45 (Integrated PHY) | N/A (Copper) | 0.000 ms |
| HQ-to-BranchNorth-EVPL | Metro-HQ <-> Metro-Branch-North | 22.0 km | OS2 Single-Mode Fiber (9/125 um) | 10GBASE-ER SFP+ | 10.50 / 15.0 dB | 0.108 ms |
| HQ-to-BranchSouth-EVPL | Metro-HQ <-> Metro-Branch-South | 31.5 km | OS2 Single-Mode Fiber (9/125 um) | 10GBASE-ER SFP+ | 13.07 / 15.0 dB | 0.154 ms |
| HQ-to-FinTech-Colo | Metro-HQ <-> FinTech-Colo-DC | 16.5 km | OS2 Single-Mode Fiber (9/125 um) | 10GBASE-ER SFP+ | 9.03 / 15.0 dB | 0.081 ms |

### L1 Engineering Justifications

- **HQ-Access-LAN:** Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'HQ-Access-LAN' (HQ-Core <-> HQ-Trading-Desks) because run distance (60m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0003 ms).
- **HQ-to-BranchNorth-EVPL:** Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-BranchNorth-EVPL' (Metro-HQ <-> Metro-Branch-North) because link distance (22 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 10.50 dB (fiber + 2x0.75 dB connectors + 0.5 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.108 ms).
- **HQ-to-BranchSouth-EVPL:** Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-BranchSouth-EVPL' (Metro-HQ <-> Metro-Branch-South) because link distance (31.5 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 13.07 dB (fiber + 2x0.75 dB connectors + 0.7 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.154 ms).
- **HQ-to-FinTech-Colo:** Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-FinTech-Colo' (Metro-HQ <-> FinTech-Colo-DC) because link distance (16.5 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 9.03 dB (fiber + 2x0.75 dB connectors + 0.4 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.081 ms).

## 2. Layer 2 Switching, VLANs, RSTP & QoS

- Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,20,30,40,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
- Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,20,30,40,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
- Provisioned 864W IEEE 802.3at (PoE+) switch power budget across 24 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.
- Enabled MEF Carrier Ethernet EVPL (Ethernet Virtual Private Line) over dual-homed OS2 SMF links to multiplex isolated customer/colo VLANs via 802.1ad Q-in-Q with sub-50ms carrier ring protection.
- Applied 'LLQ-Sub5ms-Strict-Priority (DSCP EF 46 -> 30% PQ, AF41 -> 35% CBWFQ)' queuing because target SLA latency (4.5 ms) requires deterministic serialization delay bounds above the 0.154 ms physical fiber propagation floor (RFC 4594).

## 3. Layer 3 Bitwise VLSM Allocation Table

> Allocated 7 non-overlapping VLSM subnets from root block 10.20.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 592; allocated usable capacity: 666 (88.89% host-packing efficiency, consuming 680 addresses / 1.04% of root prefix). Tightest summary supernet: 10.20.0.0/22.

| Subnet | VLAN | Zone | CIDR | Subnet Mask | Wildcard Mask | Gateway | Broadcast | Req / Usable | Efficiency |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: |
| HQ-Trading-Users | 10 | corp | `10.20.0.0/24` | `255.255.255.0` | `0.0.0.255` | `10.20.0.1` | `10.20.0.255` | 250 / 254 | 98.4% |
| Remote-Branches-Corp | 20 | corp | `10.20.1.0/24` | `255.255.255.0` | `0.0.0.255` | `10.20.1.1` | `10.20.1.255` | 200 / 254 | 78.7% |
| FinTech-Colo-Compute | 40 | dmz | `10.20.2.0/26` | `255.255.255.192` | `0.0.0.63` | `10.20.2.1` | `10.20.2.63` | 60 / 62 | 96.8% |
| LowLatency-Voice-Trading | 30 | voice | `10.20.2.64/26` | `255.255.255.192` | `0.0.0.63` | `10.20.2.65` | `10.20.2.127` | 50 / 62 | 80.7% |
| Metro-OOB-Mgmt | 99 | mgmt | `10.20.2.128/27` | `255.255.255.224` | `0.0.0.31` | `10.20.2.129` | `10.20.2.159` | 28 / 30 | 93.3% |
| EVPL-Primary-P2P | P2P | wan_p2p | `10.20.2.160/30` | `255.255.255.252` | `0.0.0.3` | `10.20.2.161` | `10.20.2.163` | 2 / 2 | 100.0% |
| EVPL-Failover-P2P | P2P | wan_p2p | `10.20.2.164/30` | `255.255.255.252` | `0.0.0.3` | `10.20.2.165` | `10.20.2.167` | 2 / 2 | 100.0% |

## 4. Layer 3 Routing & Domain Isolation Decisions

- Selected Multi-Area OSPFv2 (Area 0 + Regional Areas) internally paired with eBGP-4 (AS 65200, RFC 4271) at the WAN/Colo/Cloud boundary because multi-site / multi-cloud peering crosses administrative trust boundaries requiring AS-PATH loop prevention, policy-based route filtering, and routing domain isolation (preventing external WAN flaps from triggering internal OSPF SPF recalculations).
- Enabled CIDR route summarization (10.20.0.0/22, 10.20.1.0/24, 10.20.2.0/26) via BGP aggregate-address and OSPF ABR 'area range' (RFC 4632) to minimize RIB/FIB table size across WAN edges.

## 5. Unified Explainable Decision Log

1. Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'HQ-Access-LAN' (HQ-Core <-> HQ-Trading-Desks) because run distance (60m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0003 ms).
2. Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-BranchNorth-EVPL' (Metro-HQ <-> Metro-Branch-North) because link distance (22 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 10.50 dB (fiber + 2x0.75 dB connectors + 0.5 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.108 ms).
3. Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-BranchSouth-EVPL' (Metro-HQ <-> Metro-Branch-South) because link distance (31.5 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 13.07 dB (fiber + 2x0.75 dB connectors + 0.7 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.154 ms).
4. Selected OS2 Single-Mode Fiber (9/125 um) (10GBASE-ER SFP+) for link 'HQ-to-FinTech-Colo' (Metro-HQ <-> FinTech-Colo-DC) because link distance (16.5 km) exceeds both the 400m limit of OM4 Multimode Fiber and the 10 km chromatic/attenuation reach of 10GBASE-LR, requiring 1550nm low-attenuation (0.25 dB/km) ER optics; calculated optical link loss is 9.03 dB (fiber + 2x0.75 dB connectors + 0.4 dB splices + 3.0 dB margin) within the 15.0 dB optical budget (one-way fiber propagation delay: 0.081 ms).
5. Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,20,30,40,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
6. Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,20,30,40,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
7. Provisioned 864W IEEE 802.3at (PoE+) switch power budget across 24 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.
8. Enabled MEF Carrier Ethernet EVPL (Ethernet Virtual Private Line) over dual-homed OS2 SMF links to multiplex isolated customer/colo VLANs via 802.1ad Q-in-Q with sub-50ms carrier ring protection.
9. Applied 'LLQ-Sub5ms-Strict-Priority (DSCP EF 46 -> 30% PQ, AF41 -> 35% CBWFQ)' queuing because target SLA latency (4.5 ms) requires deterministic serialization delay bounds above the 0.154 ms physical fiber propagation floor (RFC 4594).
10. Allocated 7 non-overlapping VLSM subnets from root block 10.20.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 592; allocated usable capacity: 666 (88.89% host-packing efficiency, consuming 680 addresses / 1.04% of root prefix). Tightest summary supernet: 10.20.0.0/22.
11. Selected Multi-Area OSPFv2 (Area 0 + Regional Areas) internally paired with eBGP-4 (AS 65200, RFC 4271) at the WAN/Colo/Cloud boundary because multi-site / multi-cloud peering crosses administrative trust boundaries requiring AS-PATH loop prevention, policy-based route filtering, and routing domain isolation (preventing external WAN flaps from triggering internal OSPF SPF recalculations).
12. Enabled CIDR route summarization (10.20.0.0/22, 10.20.1.0/24, 10.20.2.0/26) via BGP aggregate-address and OSPF ABR 'area range' (RFC 4632) to minimize RIB/FIB table size across WAN edges.
