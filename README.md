# NetArchitect: Algorithmic Network Planning & Self-Explaining Architecture Engine

**Course:** CIC-307 • Computer Networks Mini-Project  
**Stack:** Python 3.13 • Pydantic v2 • Typer + Rich CLI • FastAPI + Uvicorn • Pytest  

NetArchitect is an algorithmic network engineering utility that ingests preset or custom JSON enterprise network specifications, validates Layer 1–3 physical and addressing boundaries, executes deterministic rule engines, and exports **deployment-ready Cisco IOS configurations** paired with **dynamic mathematical & RFC architectural justifications**.

---

## System Architecture & Decision Flow

```
┌─────────────────────┐     ┌─────────────────────────┐     ┌──────────────────────────┐     ┌───────────────────────────┐
│  1. Input Ingestion │ ──▶ │  2. L1/L2 Media Engine  │ ──▶ │  3. L3 VLSM & Routing    │ ──▶ │  4. Explainable Exporter  │
│  Preset/Custom JSON │     │  Distance/Optical/PoE   │     │  Bitwise Alloc + OSPF/BGP│     │  Cisco IOS + Rationale    │
└─────────────────────┘     └─────────────────────────┘     └──────────────────────────┘     └───────────────────────────┘
```

### Implemented Modules
- `src/netarchitect/models.py` — Strict Pydantic schemas for sites, links, VLANs, security zones, and outputs.
- `src/netarchitect/exceptions.py` — Domain exceptions (`PhysicalDistanceViolationError`, `AddressSpaceExhaustionError`, `ParameterValidationError`).
- `src/netarchitect/engines/media_engine.py` — L1 physics (`Cat6a <=100m`, `OM4 MMF 101-400m`, `OS2 SMF LR/ER/ZR >400m`), wavelength optical link budgets, speed-of-light propagation delay, and L2 802.1Q/RSTP/PoE/EVPL/QoS design.
- `src/netarchitect/engines/vlsm_engine.py` — Pure 32-bit unsigned bitwise VLSM allocator (descending block packing, boundary alignment, wildcard masks, zero-overlap invariant, CIDR supernet summarization).
- `src/netarchitect/engines/routing_engine.py` — Single-Area OSPFv2 (`<50` subnets), Multi-Area OSPFv2, eBGP-4 domain isolation, route summarization, and IKEv2/IPsec VTI selection.
- `src/netarchitect/exporters/cisco_ios.py` — Copy-paste ready Cisco IOS configurations for Core L3 Switches, Access L2 Switches, and Edge/WAN Routers (SVIs, Extended ACLs, pruned trunks, RSTP, OSPF, BGP, QoS, IPsec).
- `src/netarchitect/cli.py` & `src/netarchitect/api.py` — Rich CLI + FastAPI REST server with interactive OpenAPI Swagger UI (`/docs`).

---

## Quick Start

### 1. Run the Automated Test Suite
```bash
PYTHONPATH=src pytest -v
```

### 2. Run the CLI
```bash
# List all 3 built-in enterprise profiles
PYTHONPATH=src python3 -m netarchitect presets

# Generate a full explainable plan in the terminal
PYTHONPATH=src python3 -m netarchitect plan --preset campus_lan
PYTHONPATH=src python3 -m netarchitect plan --preset metro_man
PYTHONPATH=src python3 -m netarchitect plan --preset global_wan

# Validate a custom JSON specification
PYTHONPATH=src python3 -m netarchitect validate presets/campus_lan.json

# Export all 3 verification configs + rationale logs into exports/
PYTHONPATH=src python3 -m netarchitect export-all --out-dir exports
```

### 3. Launch the Interactive Web API & Swagger Dashboard
```bash
PYTHONPATH=src python3 -m netarchitect serve --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000/docs in your browser
```

---

## Preset Scenarios & Verification Exports

| Profile | Scale | Key Technologies | Exported Config | Rationale Report |
| :--- | :--- | :--- | :--- | :--- |
| **Profile 1: Campus LAN** | 3 Buildings (`<400m`), 1,600 endpoints + PoE APs | Cat6a, OM4 MMF, 802.1Q, RSTP, Single-Area OSPF | `exports/profile1_campus_lan.cfg` | `exports/profile1_campus_lan_rationale.md` |
| **Profile 2: Metro MAN** | HQ + 2 Remote (`15–35 km`) + FinTech Colo, 450 users | OS2 SMF (10GBASE-ER), EVPL, Sub-5ms LLQ QoS, eBGP + OSPF | `exports/profile2_metro_man.cfg` | `exports/profile2_metro_man_rationale.md` |
| **Profile 3: Global WAN** | 4 Cities + Cloud VPC, 2,000 IoT/scanners | IKEv2/IPsec VTI, Multi-Area OSPF + eBGP, Route Summarization, IoT ACLs | `exports/profile3_global_wan.cfg` | `exports/profile3_global_wan_rationale.md` |

### Loading Exports into Cisco Packet Tracer / GNS3
Each `.cfg` file in `exports/` contains three clearly delimited device blocks (`CORE-SW1`, `ACC-SW1`, `EDGE-RTR1`):
1. In **Cisco Packet Tracer** (Catalyst 3560-24PS Core, Catalyst 2960-24TT Access, ISR 2911/4331 Router) or **GNS3** (IOSv / IOU), open each device CLI.
2. Paste the corresponding device configuration block starting from `enable` through `write memory`.
3. Verify convergence and addressing with:
   - `show vlan brief` and `show interfaces trunk` (confirms Native VLAN 999 + pruned allowed VLANs)
   - `show spanning-tree summary` (confirms Rapid-PVST Root Primary on Core)
   - `show ip ospf neighbor` / `show ip route` / `show ip bgp summary`
   - `show access-lists` (confirms IoT/DMZ zone isolation)

---

## AI Code Audit Deliverable
See [`ai_audit_log.md`](ai_audit_log.md) for three documented AI misconfigurations (bitwise VLSM alignment/wildcard bug, unconstrained trunk/native VLAN 1 bug, and 31.5 km optical link budget hallucination), complete with packet flow analysis and verified remediations.
