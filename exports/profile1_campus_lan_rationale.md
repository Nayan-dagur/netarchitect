# Architectural Rationale Report: Campus LAN

- **Topology Tier:** `campus_lan`
- **Total Endpoints:** `1,670`
- **IGP Routing:** `Single-Area OSPFv2 (Area 0)`
- **EGP / WAN Routing:** `N/A (Single AS)`
- **Root Prefix & Summary Supernet:** `10.10.0.0/16` -> `10.10.0.0/20`
- **Overall VLSM Host Packing Efficiency:** `66.53%`

## 1. Layer 1 Physical Media & Optical Budget Decisions

| Link | Endpoints | Distance | Selected Media | Transceiver | Loss / Budget | Propagation |
| :--- | :--- | ---: | :--- | :--- | :--- | ---: |
| BldgA-Access-Drop | BldgA-IDF1 <-> BldgA-Endpoints | 75 m | Cat6a Twisted-Pair Copper | 10GBASE-T RJ-45 (Integrated PHY) | N/A (Copper) | 0.000 ms |
| BldgA-to-BldgB-Backbone | Building-A-Core <-> Building-B-Eng | 240 m | OM4 Multimode Fiber (50/125 um) | 10GBASE-SR SFP+ | 2.22 / 2.9 dB | 0.001 ms |
| BldgA-to-BldgC-Backbone | Building-A-Core <-> Building-C-Lab | 360 m | OM4 Multimode Fiber (50/125 um) | 10GBASE-SR SFP+ | 2.58 / 2.9 dB | 0.002 ms |
| BldgB-to-BldgC-Ring | Building-B-Eng <-> Building-C-Lab | 195 m | OM4 Multimode Fiber (50/125 um) | 10GBASE-SR SFP+ | 2.08 / 2.9 dB | 0.001 ms |

### L1 Engineering Justifications

- **BldgA-Access-Drop:** Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'BldgA-Access-Drop' (BldgA-IDF1 <-> BldgA-Endpoints) because run distance (75m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0004 ms).
- **BldgA-to-BldgB-Backbone:** Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgA-to-BldgB-Backbone' (Building-A-Core <-> Building-B-Eng) because run distance (240m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.22 dB <= 2.9 dB limit, propagation delay: 0.0012 ms).
- **BldgA-to-BldgC-Backbone:** Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgA-to-BldgC-Backbone' (Building-A-Core <-> Building-C-Lab) because run distance (360m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.58 dB <= 2.9 dB limit, propagation delay: 0.0018 ms).
- **BldgB-to-BldgC-Ring:** Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgB-to-BldgC-Ring' (Building-B-Eng <-> Building-C-Lab) because run distance (195m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.08 dB <= 2.9 dB limit, propagation delay: 0.0010 ms).

## 2. Layer 2 Switching, VLANs, RSTP & QoS

- Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,20,30,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
- Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,20,30,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
- Provisioned 2520W IEEE 802.3at (PoE+) switch power budget across 70 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.
- Applied 'Enterprise-Voice-Priority (DSCP EF 46 PQ, CS3 Call-Signaling)' queuing because target SLA latency (10.0 ms) requires deterministic serialization delay bounds above the 0.002 ms physical fiber propagation floor (RFC 4594).

## 3. Layer 3 Bitwise VLSM Allocation Table

> Allocated 5 non-overlapping VLSM subnets from root block 10.10.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 1,912; allocated usable capacity: 2,874 (66.53% host-packing efficiency, consuming 2,884 addresses / 4.40% of root prefix). Tightest summary supernet: 10.10.0.0/20.

| Subnet | VLAN | Zone | CIDR | Subnet Mask | Wildcard Mask | Gateway | Broadcast | Req / Usable | Efficiency |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: |
| Campus-Workstations | 10 | corp | `10.10.0.0/21` | `255.255.248.0` | `0.0.7.255` | `10.10.0.1` | `10.10.7.255` | 1200 / 2046 | 58.6% |
| Campus-Wireless-PoE | 20 | corp | `10.10.8.0/23` | `255.255.254.0` | `0.0.1.255` | `10.10.8.1` | `10.10.9.255` | 400 / 510 | 78.4% |
| Campus-VoIP | 30 | voice | `10.10.10.0/24` | `255.255.255.0` | `0.0.0.255` | `10.10.10.1` | `10.10.10.255` | 250 / 254 | 98.4% |
| Campus-NetMgmt | 99 | mgmt | `10.10.11.0/26` | `255.255.255.192` | `0.0.0.63` | `10.10.11.1` | `10.10.11.63` | 60 / 62 | 96.8% |
| Core-to-Edge-P2P | P2P | wan_p2p | `10.10.11.64/30` | `255.255.255.252` | `0.0.0.3` | `10.10.11.65` | `10.10.11.67` | 2 / 2 | 100.0% |

## 4. Layer 3 Routing & Domain Isolation Decisions

- Selected Single-Area OSPFv2 (Area 0) (RFC 2328) because the topology operates within a single autonomous system with 5 subnets (<50-subnet single-area LSDB threshold) at a single site; Dijkstra SPF (O(E log V)) guarantees sub-second link-state convergence without ABR complexity.

## 5. Unified Explainable Decision Log

1. Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'BldgA-Access-Drop' (BldgA-IDF1 <-> BldgA-Endpoints) because run distance (75m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0004 ms).
2. Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgA-to-BldgB-Backbone' (Building-A-Core <-> Building-B-Eng) because run distance (240m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.22 dB <= 2.9 dB limit, propagation delay: 0.0012 ms).
3. Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgA-to-BldgC-Backbone' (Building-A-Core <-> Building-C-Lab) because run distance (360m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.58 dB <= 2.9 dB limit, propagation delay: 0.0018 ms).
4. Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'BldgB-to-BldgC-Ring' (Building-B-Eng <-> Building-C-Lab) because run distance (195m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.08 dB <= 2.9 dB limit, propagation delay: 0.0010 ms).
5. Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,20,30,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
6. Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,20,30,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
7. Provisioned 2520W IEEE 802.3at (PoE+) switch power budget across 70 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.
8. Applied 'Enterprise-Voice-Priority (DSCP EF 46 PQ, CS3 Call-Signaling)' queuing because target SLA latency (10.0 ms) requires deterministic serialization delay bounds above the 0.002 ms physical fiber propagation floor (RFC 4594).
9. Allocated 5 non-overlapping VLSM subnets from root block 10.10.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 1,912; allocated usable capacity: 2,874 (66.53% host-packing efficiency, consuming 2,884 addresses / 4.40% of root prefix). Tightest summary supernet: 10.10.0.0/20.
10. Selected Single-Area OSPFv2 (Area 0) (RFC 2328) because the topology operates within a single autonomous system with 5 subnets (<50-subnet single-area LSDB threshold) at a single site; Dijkstra SPF (O(E log V)) guarantees sub-second link-state convergence without ABR complexity.
