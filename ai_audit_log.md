# AI Code Audit & Defense Log (`ai_audit_log.md`)

**Course:** CIC-307 • Computer Networks Mini-Project  
**Project:** NetArchitect: Recommendation & Config Engine  
**Role:** Lead Network Architect & Validator  

This audit log documents three concrete instances where generative AI produced flawed networking algorithms or Cisco IOS configurations during prototyping, along with **packet flow analysis**, root-cause diagnosis, and the verified remediation implemented in `netarchitect`.

---

## Audit Case 1: Bitwise VLSM Boundary Alignment & Signed Wildcard Mask Inversion

### 1.1 Prompt Used
> *"Write a Python function that takes a root CIDR and a list of host counts, allocates VLSM subnets using bitwise math, and computes the Cisco OSPF/ACL wildcard mask for each subnet."*

### 1.2 Buggy AI-Generated Code
```python
import math

def buggy_allocate_vlsm(root_net_int: int, host_counts: list[int]):
    cursor = root_net_int
    subnets = []
    for hosts in sorted(host_counts, reverse=True):
        # BUG 1: Forgot +2 for network ID and broadcast address
        host_bits = math.ceil(math.log2(hosts))
        block_size = 1 << host_bits
        mask = (0xFFFFFFFF << host_bits) & 0xFFFFFFFF

        # BUG 2: Python ~mask produces a negative signed integer (-256, etc.)
        wildcard = ~mask

        # BUG 3: Did not align `cursor` to a multiple of `block_size`
        net_int = cursor
        bcast_int = net_int + block_size - 1
        subnets.append((net_int, mask, wildcard, bcast_int))
        cursor = bcast_int + 1
    return subnets
```

### 1.3 Technical Analysis & Packet Flow Post-Mortem
Three critical defects occur simultaneously in the AI output:
1. **Off-by-Two Host Capacity (`math.log2(hosts)`):** Requesting `hosts = 254` or `hosts = 64` evaluates `ceil(log2(64)) = 6` (`/26`, 64 total addresses, only **62 usable hosts**). Hosts `.63` (broadcast) and `.64` (next network) are misassigned as valid endpoints.
2. **Signed Integer Bitwise Inversion (`~mask`):** In Python, integers have arbitrary precision with two's-complement semantics. Evaluating `~(0xFFFFFF00)` returns `-0xFFFFFF01` (`-4294967041`) instead of `0x000000FF` (`0.0.0.255`), crashing octet shifting or emitting invalid negative wildcard strings.
3. **Unaligned Block Allocation (Overlapping Subnets):** If a smaller block precedes a larger block—or if allocations are performed out of strict alignment order without `(cursor + block_size - 1) & ~(block_size - 1)`—the generated network address violates CIDR prefix boundary rules (`network & mask != network`).

**Packet Flow Impact Analysis:**
- Suppose `VLAN 10` requests `64` hosts and receives `10.10.0.0/26` (`.0`–`.63`), and host #63 is assigned `10.10.0.63`.
- **Packet Trace (ARP & ICMP Echo):** When `PC-63` (`10.10.0.63`) attempts to send an ICMP Echo Request to gateway `10.10.0.1`, any packet destined to `10.10.0.63` is treated by the Layer 3 SVI (`interface Vlan10`) as the **subnet-directed broadcast address**. Switches flood return ARP replies across all VLAN 10 ports, while `PC-63` drops unicast validation—resulting in 100% packet loss for the top two hosts.
- Simultaneously, if an unaligned `/24` starts at `10.10.0.64/24`, the router's Longest Prefix Match (LPM) normalizes `10.10.0.64 & 255.255.255.0 = 10.10.0.0/24`, causing **route overlap** with the first `/26` and blackholing return traffic.

### 1.4 Final Verified Fix
Implemented in [`src/netarchitect/engines/vlsm_engine.py`](src/netarchitect/engines/vlsm_engine.py):
- Enforce `needed = hosts + 2` and `max(2, math.ceil(math.log2(needed)))` (`_required_host_bits`).
- Align cursor strictly via bitwise mask: `aligned_net = (cursor + (block_size - 1)) & ~(block_size - 1)`.
- Mask wildcard to unsigned 32-bit: `wildcard_int = (~mask_int) & 0xFFFFFFFF`.
- Assert a post-allocation zero-overlap invariant (`curr_end < next_start`) across all blocks.
- Validated by `tests/test_vlsm_engine.py::test_exact_254_vs_255_host_boundary` and `test_bitwise_wildcard_masks_edge_cases`.

---

## Audit Case 2: Unconstrained Switchport Trunks, Native VLAN 1 & Missing RSTP Guardrails

### 2.1 Prompt Used
> *"Generate a Cisco IOS configuration template for a Core Layer 3 Switch and Access Layer 2 Switch connecting Corporate VLAN 10, Voice VLAN 30, and IoT VLAN 50."*

### 2.2 Buggy AI-Generated Code
```ios
interface GigabitEthernet0/1
 switchport mode trunk
 no shutdown
!
interface range FastEthernet0/1 - 24
 switchport mode access
 switchport access vlan 10
 no shutdown
```

### 2.3 Technical Analysis & Packet Flow Post-Mortem
The AI-generated IOS template omits four production security and Layer 2 stability controls:
1. **Unpruned Trunk (`switchport trunk allowed vlan` missing):** Every active VLAN (including Management VLAN 99 and IoT VLAN 50) is flooded across every access switch uplink, even on switches with zero IoT ports.
2. **Default Native VLAN (`VLAN 1` left implicit):** Untagged frames on trunks default to `VLAN 1`, which also carries CDP/VTP/DTP/STP control frames—creating a textbook **VLAN Hopping (Double-Tagging)** vector.
3. **Missing `switchport nonegotiate` & `spanning-tree guard root`:** Leaves Dynamic Trunking Protocol (DTP) active on links and permits a rogue access switch with a lower Bridge ID (`priority 0`) to hijack the RSTP Root Bridge.
4. **Missing `spanning-tree portfast` and `bpduguard enable` on access ports:** Access ports take 30 seconds in Listening/Learning if falling back to 802.1D timers, and can inject malicious BPDUs.

**Packet Flow Impact Analysis:**
- **Attack / Failure Flow (Double-Tagging VLAN Hopping + Root Hijack):**
  1. An attacker connected to `FastEthernet0/5` (Access VLAN 10) crafts an Ethernet frame with **outer 802.1Q tag = 1** (matching the default native VLAN) and **inner 802.1Q tag = 99** (Management SVI), destined for `10.10.x.1`.
  2. When the frame traverses `GigabitEthernet0/1` (`native vlan 1`, all VLANs allowed), the access switch strips the outer native tag (`VLAN 1`) and forwards the frame still bearing the **inner `VLAN 99` tag** onto the Core Switch!
  3. The Core Switch reads `VLAN 99` and delivers the frame directly into the Management plane—bypassing Layer 3 ACLs entirely.
  4. Concurrently, if the attacker transmits a forged RSTP BPDU with `Bridge Priority = 0`, the topology recalculates, hair-pinning campus traffic through the compromised access port.

### 2.4 Final Verified Fix
Implemented in [`src/netarchitect/exporters/cisco_ios.py`](src/netarchitect/exporters/cisco_ios.py):
- Created reserved unused blackhole native VLAN `999` (`BLACKHOLE_NATIVE`), never assigned to user ports.
- Enforced explicit trunk pruning (`switchport trunk allowed vlan <active_vlans>`), `switchport trunk native vlan 999`, `switchport nonegotiate`, and `spanning-tree guard root` on Core downlinks.
- Enforced `spanning-tree mode rapid-pvst`, `spanning-tree vlan <list> root primary`, plus `spanning-tree portfast` and `spanning-tree bpduguard enable` on all edge access ports.
- Validated by `tests/test_presets_and_configs.py::test_profile1_campus_lan_end_to_end`.

---

## Audit Case 3: Optical Link Budget Hallucination on 31.5 km Metro MAN Fiber

### 3.1 Prompt Used
> *"Select the optical transceiver for a 31.5 km single-mode fiber link in the Metro MAN profile and verify the optical power budget."*

### 3.2 Buggy AI-Generated Code
```python
def buggy_select_smf_transceiver(distance_km: float) -> str:
    # BUG: Assumed all 10G SMF links use 10GBASE-LR and ignored connector/margin loss
    loss_db = distance_km * 0.25
    if loss_db < 10.0:  # 31.5 * 0.25 = 7.875 dB
        return "10GBASE-LR (1310nm)"
    return "10GBASE-ER (1550nm)"
```

### 3.3 Technical Analysis & Packet Flow Post-Mortem
Two compounding physics hallucinations occur here:
1. **Wrong Wavelength Attenuation Coefficient:** `10GBASE-LR` operates at **1310 nm**, where OS2 SMF attenuation is **~0.35 dB/km** (not `0.25 dB/km`, which applies to 1550 nm). At `31.5 km`, 1310 nm fiber attenuation alone is `31.5 * 0.35 = 11.025 dB`.
2. **Omitted Passive Losses & Transceiver Budget Limit:** Real-world fiber channels include mated LC/UPC patch-panel connectors (`2 × 0.75 dB = 1.50 dB`), fusion splices (`~7 splices × 0.1 dB = 0.70 dB`), and a mandatory `3.0 dB` aging/repair margin—bringing total 1310 nm link loss to **`16.23 dB`**. However, IEEE 802.3ae `10GBASE-LR` only provides a **6.2–8.2 dB optical power budget** (10 km max reach)!

**Packet Flow Impact Analysis:**
- **Physical-Layer Frame Drop & OSPF/BGP Flap:**
  - Suppose `10GBASE-LR` (`Tx: -8.2 to +0.5 dBm`, `Rx sensitivity: -14.4 dBm`) is installed on the `31.5 km` HQ-to-BranchSouth EVPL link.
  - Under `16.23 dB` total channel attenuation, received optical power drops below `-16.7 dBm`—**2.3 dB below receiver sensitivity**.
  - On the wire, 64B/66B PCS synchronization collapses, Bit Error Rate (BER) degrades from `10^-12` to `>10^-4`, causing continuous **CRC / FCS errors** at Layer 2 (`show interfaces` input errors).
  - OSPF Hello packets (`224.0.0.5`, 10s interval) and BFD/BGP keepalives suffer silent drops, triggering **continuous adjacency flapping**, repeated SPF recalculations, and sub-5ms SLA failure.

### 3.4 Final Verified Fix
Implemented in [`src/netarchitect/engines/media_engine.py`](src/netarchitect/engines/media_engine.py):
- Enforced strict wavelength-specific attenuation (`0.35 dB/km` @ 1310nm for `LR <= 10 km`; `0.25 dB/km` @ 1550nm for `ER <= 40 km` and `ZR <= 80 km`), explicit connector (`2 × 0.75 dB`), splice (`0.1 dB` per 4 km reel), and `3.0 dB` safety margin calculations.
- For `31.5 km` (`Metro-Branch-South`), NetArchitect selects **`10GBASE-ER SFP+` (1550 nm)** with calculated loss `13.08 dB <= 15.0 dB` optical budget.
- Validated by `tests/test_media_engine.py::test_os2_smf_tiers_lr_er_zr_and_wan` and `tests/test_presets_and_configs.py::test_profile2_metro_man_end_to_end`.
