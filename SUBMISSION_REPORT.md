# CIC-307 Computer Networks Mini-Project — Submission Report

**Project Title:** NetArchitect: Recommendation & Config Engine  
**GitHub Repository:** https://github.com/Nayan-dagur/netarchitect  
**Course Code:** CIC-307 (100 Points)  

---

## 1. Deliverables Checklist

| Deliverable | File / Location in Repository | Status |
| :--- | :--- | :--- |
| **1. Source Code Repository** (CLI + FastAPI Web API + Engines) | [`src/netarchitect/`](src/netarchitect/) | Complete |
| **2. Automated Unit & Integration Test Suite (`pytest`)** | [`tests/`](tests/) (`23/23` passing) | Verified |
| **3. Mandatory AI Code Audit & Defense Log** | [`ai_audit_log.md`](ai_audit_log.md) | Complete (3 audited cases + packet flow analysis) |
| **4. Verification Exports (3 Preset Profiles)** | [`exports/`](exports/) (`*.cfg` + `*_rationale.md`) | Generated & Verified |

---

## 2. Preset Profiles Summary & Verified Outputs

### Profile 1: Campus LAN (`campus_lan`)
- **Scale:** 3 Buildings (`<400m`), `1,670` endpoints (1,600 wired + 70 PoE APs)
- **L1/L2 Decisions:** Cat6a (`10GBASE-T`, 75m access) + OM4 MMF (`10GBASE-SR`, 195m/240m/360m backbones, `<=2.9 dB` passive channel limit), pruned 802.1Q trunks (`10,20,30,99`), blackhole Native VLAN `999`, Rapid-PVST+ (IEEE 802.1w), `2520W` IEEE 802.3at PoE+ budget.
- **L3 VLSM & Routing:** `10.10.0.0/16` -> 5 non-overlapping subnets (`10.10.0.0/21`, `10.10.8.0/23`, `10.10.10.0/24`, `10.10.11.0/26`, `10.10.11.64/30`), summary `10.10.0.0/20`, **Single-Area OSPFv2 (Area 0)**.
- **Exported Config & Rationale:** [`exports/profile1_campus_lan.cfg`](exports/profile1_campus_lan.cfg) | [`exports/profile1_campus_lan_rationale.md`](exports/profile1_campus_lan_rationale.md)

### Profile 2: Metro MAN (`metro_man`)
- **Scale:** HQ + 2 Remote Branches (`16.5–31.5 km`) + FinTech Colo (`514` total endpoints)
- **L1/L2 Decisions:** Cat6a access (60m) + OS2 SMF `10GBASE-ER` (1550nm, `9.03–13.07 dB` optical loss within `15.0 dB` budget), MEF EVPL, Sub-5ms LLQ Strict-Priority QoS (`DSCP EF 46 -> 30% PQ`, `AF41 -> 35% CBWFQ`).
- **L3 VLSM & Routing:** `10.20.0.0/16` -> 7 non-overlapping subnets (`88.89%` host-packing efficiency), summary `10.20.0.0/22`, **Multi-Area OSPFv2 + eBGP-4 (AS 65200)**.
- **Exported Config & Rationale:** [`exports/profile2_metro_man.cfg`](exports/profile2_metro_man.cfg) | [`exports/profile2_metro_man_rationale.md`](exports/profile2_metro_man_rationale.md)

### Profile 3: Global WAN (`global_wan`)
- **Scale:** 4 Cities + AWS Cloud VPC (`2,732` endpoints including 2,000 IoT/scanners)
- **L1/L2 Decisions:** Cat6a access (85m) + OM4 cross-connect (320m) + Carrier DWDM/IPsec over WAN (`450–10,200 km`), IoT Extended ACL isolation (`ACL-IOT-V50-IN`, `ACL-IOT-V51-IN`).
- **L3 VLSM & Routing:** `10.30.0.0/16` -> 8 non-overlapping subnets (`96.18%` host-packing efficiency), summary `10.30.0.0/20`, **Multi-Area OSPFv2 (Areas 0–3) + eBGP-4 (AS 65300) + IKEv2/IPsec AES-256-GCM VTI + CIDR Route Summarization**.
- **Exported Config & Rationale:** [`exports/profile3_global_wan.cfg`](exports/profile3_global_wan.cfg) | [`exports/profile3_global_wan_rationale.md`](exports/profile3_global_wan_rationale.md)

---

## 3. AI Code Audit Summary (`ai_audit_log.md`)
Three concrete AI networking misconfigurations were identified, analyzed via packet flow traces, and fixed:
1. **Bitwise VLSM Alignment & Signed Wildcard Mask Bug** — `math.log2(hosts)` off-by-two error, negative Python `~mask`, and unaligned cursor boundaries causing subnet overlap and broadcast misrouting.
2. **Unconstrained Switchport Trunk & Native VLAN 1** — Missing `switchport trunk allowed vlan`, `native vlan 999`, `nonegotiate`, and `bpduguard` allowing double-tagging VLAN hopping and STP root hijack.
3. **31.5 km Optical Link Budget Hallucination** — Selecting 1310nm `10GBASE-LR` (`16.23 dB` actual loss > `8.2 dB` budget) instead of 1550nm `10GBASE-ER` (`13.07 dB` <= `15.0 dB` budget).

---

## 4. Verification Commands
```bash
PYTHONPATH=src pytest -v
PYTHONPATH=src python3 -m netarchitect presets
PYTHONPATH=src python3 -m netarchitect plan --preset campus_lan
PYTHONPATH=src python3 -m netarchitect export-all --out-dir exports
PYTHONPATH=src python3 -m netarchitect serve --port 8000
```
