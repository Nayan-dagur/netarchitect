# Architectural Rationale Report: Global WAN

- **Topology Tier:** `global_wan`
- **Total Endpoints:** `2,732`
- **IGP Routing:** `Multi-Area OSPFv2 (Area 0 + Regional Areas)`
- **EGP / WAN Routing:** `eBGP-4 (AS 65300, RFC 4271)`
- **Root Prefix & Summary Supernet:** `10.30.0.0/16` -> `10.30.0.0/20`
- **Overall VLSM Host Packing Efficiency:** `96.18%`

## 1. Layer 1 Physical Media & Optical Budget Decisions

| Link | Endpoints | Distance | Selected Media | Transceiver | Loss / Budget | Propagation |
| :--- | :--- | ---: | :--- | :--- | :--- | ---: |
| NYC-Campus-Access | NYC-Core <-> NYC-Scanners | 85 m | Cat6a Twisted-Pair Copper | 10GBASE-T RJ-45 (Integrated PHY) | N/A (Copper) | 0.000 ms |
| NYC-DC-CrossConnect | NYC-Core <-> NYC-ISP-POP | 320 m | OM4 Multimode Fiber (50/125 um) | 10GBASE-SR SFP+ | 2.46 / 2.9 dB | 0.002 ms |
| NYC-to-LON-IPsec-WAN | City-NYC-Hub <-> City-LON-Hub | 5570.0 km | Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) | 10GBASE-LR Access + Carrier DWDM/MPLS Transport | 1536.20 dB (DWDM) | 27.275 ms |
| LON-to-FRA-Metro-WAN | City-LON-Hub <-> City-FRA-Hub | 640.0 km | Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) | 10GBASE-LR Access + Carrier DWDM/MPLS Transport | 180.50 dB (DWDM) | 3.134 ms |
| FRA-to-SIN-IPsec-WAN | City-FRA-Hub <-> City-SIN-Hub | 10200.0 km | Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) | 10GBASE-LR Access + Carrier DWDM/MPLS Transport | 2809.50 dB (DWDM) | 49.947 ms |
| NYC-to-CloudVPC-Tunnel | City-NYC-Hub <-> AWS-Cloud-VPC | 450.0 km | Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) | 10GBASE-LR Access + Carrier DWDM/MPLS Transport | 128.20 dB (DWDM) | 2.204 ms |

### L1 Engineering Justifications

- **NYC-Campus-Access:** Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'NYC-Campus-Access' (NYC-Core <-> NYC-Scanners) because run distance (85m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0004 ms).
- **NYC-DC-CrossConnect:** Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'NYC-DC-CrossConnect' (NYC-Core <-> NYC-ISP-POP) because run distance (320m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.46 dB <= 2.9 dB limit, propagation delay: 0.0016 ms).
- **NYC-to-LON-IPsec-WAN:** Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'NYC-to-LON-IPsec-WAN' (City-NYC-Hub <-> City-LON-Hub) because link distance (5570 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (1536.20 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 27.275 ms).
- **LON-to-FRA-Metro-WAN:** Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'LON-to-FRA-Metro-WAN' (City-LON-Hub <-> City-FRA-Hub) because link distance (640 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (180.50 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 3.134 ms).
- **FRA-to-SIN-IPsec-WAN:** Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'FRA-to-SIN-IPsec-WAN' (City-FRA-Hub <-> City-SIN-Hub) because link distance (10200 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (2809.50 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 49.947 ms).
- **NYC-to-CloudVPC-Tunnel:** Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'NYC-to-CloudVPC-Tunnel' (City-NYC-Hub <-> AWS-Cloud-VPC) because link distance (450 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (128.20 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 2.204 ms).

## 2. Layer 2 Switching, VLANs, RSTP & QoS

- Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,50,51,60,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
- Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,50,51,60,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
- Provisioned 1152W IEEE 802.3at (PoE+) switch power budget across 32 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.

## 3. Layer 3 Bitwise VLSM Allocation Table

> Allocated 8 non-overlapping VLSM subnets from root block 10.30.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 2,766; allocated usable capacity: 2,876 (96.18% host-packing efficiency, consuming 2,892 addresses / 4.41% of root prefix). Tightest summary supernet: 10.30.0.0/20.

| Subnet | VLAN | Zone | CIDR | Subnet Mask | Wildcard Mask | Gateway | Broadcast | Req / Usable | Efficiency |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: |
| Global-IoT-Scanners-EMEA-APAC | 51 | iot | `10.30.0.0/22` | `255.255.252.0` | `0.0.3.255` | `10.30.0.1` | `10.30.3.255` | 1000 / 1022 | 97.8% |
| Global-IoT-Scanners-Americas | 50 | iot | `10.30.4.0/22` | `255.255.252.0` | `0.0.3.255` | `10.30.4.1` | `10.30.7.255` | 1000 / 1022 | 97.8% |
| Global-Corp-Operations | 10 | corp | `10.30.8.0/23` | `255.255.254.0` | `0.0.1.255` | `10.30.8.1` | `10.30.9.255` | 500 / 510 | 98.0% |
| Cloud-VPC-Workloads | 60 | cloud | `10.30.10.0/24` | `255.255.255.0` | `0.0.0.255` | `10.30.10.1` | `10.30.10.255` | 200 / 254 | 78.7% |
| Global-SecOps-Mgmt | 99 | mgmt | `10.30.11.0/26` | `255.255.255.192` | `0.0.0.63` | `10.30.11.1` | `10.30.11.63` | 60 / 62 | 96.8% |
| WAN-IPsec-VTI-NYC-VPC | P2P | wan_p2p | `10.30.11.64/30` | `255.255.255.252` | `0.0.0.3` | `10.30.11.65` | `10.30.11.67` | 2 / 2 | 100.0% |
| WAN-IPsec-VTI-NYC-LON | P2P | wan_p2p | `10.30.11.68/30` | `255.255.255.252` | `0.0.0.3` | `10.30.11.69` | `10.30.11.71` | 2 / 2 | 100.0% |
| WAN-IPsec-VTI-LON-FRA | P2P | wan_p2p | `10.30.11.72/30` | `255.255.255.252` | `0.0.0.3` | `10.30.11.73` | `10.30.11.75` | 2 / 2 | 100.0% |

## 4. Layer 3 Routing & Domain Isolation Decisions

- Selected Multi-Area OSPFv2 (Area 0 + Regional Areas) internally paired with eBGP-4 (AS 65300, RFC 4271) at the WAN/Colo/Cloud boundary because multi-site / multi-cloud peering crosses administrative trust boundaries requiring AS-PATH loop prevention, policy-based route filtering, and routing domain isolation (preventing external WAN flaps from triggering internal OSPF SPF recalculations).
- Enabled CIDR route summarization (10.30.0.0/20, 10.30.8.0/22, 10.30.4.0/22, 10.30.0.0/22, 10.30.10.0/24) via BGP aggregate-address and OSPF ABR 'area range' (RFC 4632) to minimize RIB/FIB table size across WAN edges.
- Enabled IKEv2 / IPsec ESP (AES-256-GCM + SHA-256, RFC 4301/7296) over VTI Tunnel interfaces for WAN links (NYC-to-LON-IPsec-WAN, LON-to-FRA-Metro-WAN, FRA-to-SIN-IPsec-WAN, NYC-to-CloudVPC-Tunnel) to provide confidentiality, anti-replay protection, and dynamic OSPF/BGP neighbor adjacency over untrusted Internet/cloud underlay paths.

## 5. Unified Explainable Decision Log

1. Selected Cat6a Twisted-Pair Copper (10GBASE-T RJ-45 (Integrated PHY)) for link 'NYC-Campus-Access' (NYC-Core <-> NYC-Scanners) because run distance (85m) is within the 100m IEEE 802.3an channel limit for 10 Gbps, eliminating SFP+ optical transceiver cost while supporting PoE++ power delivery (estimated propagation delay: 0.0004 ms).
2. Selected OM4 Multimode Fiber (50/125 um) (10GBASE-SR SFP+) for link 'NYC-DC-CrossConnect' (NYC-Core <-> NYC-ISP-POP) because run distance (320m) exceeds the 100m IEEE 802.3an copper limit yet stays within the 400m 850nm modal dispersion reach of OM4 (4700 MHz*km EMB; passive channel loss 2.46 dB <= 2.9 dB limit, propagation delay: 0.0016 ms).
3. Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'NYC-to-LON-IPsec-WAN' (City-NYC-Hub <-> City-LON-Hub) because link distance (5570 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (1536.20 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 27.275 ms).
4. Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'LON-to-FRA-Metro-WAN' (City-LON-Hub <-> City-FRA-Hub) because link distance (640 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (180.50 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 3.134 ms).
5. Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'FRA-to-SIN-IPsec-WAN' (City-FRA-Hub <-> City-SIN-Hub) because link distance (10200 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (2809.50 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 49.947 ms).
6. Selected Carrier Leased Wavelength / IPsec Over WAN (OS2 Access Drop) (10GBASE-LR Access + Carrier DWDM/MPLS Transport) for link 'NYC-to-CloudVPC-Tunnel' (City-NYC-Hub <-> AWS-Cloud-VPC) because link distance (450 km) exceeds the 80 km unamplified reach of 10GBASE-ZR passive OS2 fiber, necessitating carrier-amplified DWDM/WAN transport with local OS2 access handoff; unamplified attenuation (128.20 dB) exceeds passive transceiver budgets; carrier EDFA/regen required (one-way fiber propagation delay: 2.204 ms).
7. Configured IEEE 802.1Q trunk pruning (allowed VLANs: 10,50,51,60,99) with unused native VLAN 999 (BLACKHOLE_NATIVE) instead of default VLAN 1 to eliminate double-tagged VLAN hopping and broadcast leakage.
8. Enabled Rapid PVST+ / RSTP (IEEE 802.1w) with core root-bridge priority 4096 across VLANs 10,50,51,60,99 plus PortFast/BPDUGuard on edge access ports, reducing failover convergence from 30-50s (802.1D) to <1s.
9. Provisioned 1152W IEEE 802.3at (PoE+) switch power budget across 32 wireless APs (30W/AP + 20% thermal/inrush headroom) over Cat6a horizontal drops.
10. Allocated 8 non-overlapping VLSM subnets from root block 10.30.0.0/16 (65,536 total addresses) sorted descending by host demand per RFC 4632 to eliminate internal fragmentation. Total requested hosts: 2,766; allocated usable capacity: 2,876 (96.18% host-packing efficiency, consuming 2,892 addresses / 4.41% of root prefix). Tightest summary supernet: 10.30.0.0/20.
11. Selected Multi-Area OSPFv2 (Area 0 + Regional Areas) internally paired with eBGP-4 (AS 65300, RFC 4271) at the WAN/Colo/Cloud boundary because multi-site / multi-cloud peering crosses administrative trust boundaries requiring AS-PATH loop prevention, policy-based route filtering, and routing domain isolation (preventing external WAN flaps from triggering internal OSPF SPF recalculations).
12. Enabled CIDR route summarization (10.30.0.0/20, 10.30.8.0/22, 10.30.4.0/22, 10.30.0.0/22, 10.30.10.0/24) via BGP aggregate-address and OSPF ABR 'area range' (RFC 4632) to minimize RIB/FIB table size across WAN edges.
13. Enabled IKEv2 / IPsec ESP (AES-256-GCM + SHA-256, RFC 4301/7296) over VTI Tunnel interfaces for WAN links (NYC-to-LON-IPsec-WAN, LON-to-FRA-Metro-WAN, FRA-to-SIN-IPsec-WAN, NYC-to-CloudVPC-Tunnel) to provide confidentiality, anti-replay protection, and dynamic OSPF/BGP neighbor adjacency over untrusted Internet/cloud underlay paths.
