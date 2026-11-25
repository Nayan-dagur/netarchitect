"""Bitwise L3 VLSM Subnet Allocator & CIDR Summarization Engine."""

import math
from netarchitect.exceptions import AddressSpaceExhaustionError, ParameterValidationError
from netarchitect.models import AllocatedSubnet, NetworkSpecification, VLSMPlan


def ip_to_int(ip_str: str) -> int:
    """Convert dotted-quad IPv4 string to unsigned 32-bit integer."""
    parts = ip_str.strip().split(".")
    if len(parts) != 4:
        raise ParameterValidationError(f"Invalid IPv4 address '{ip_str}': expected 4 octets.")
    value = 0
    for part in parts:
        if not part.isdigit():
            raise ParameterValidationError(f"Invalid IPv4 octet '{part}' in '{ip_str}'.")
        octet = int(part)
        if octet < 0 or octet > 255:
            raise ParameterValidationError(f"IPv4 octet {octet} out of 0-255 range in '{ip_str}'.")
        value = (value << 8) | octet
    return value


def int_to_ip(value: int) -> str:
    """Convert unsigned 32-bit integer to dotted-quad IPv4 string."""
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError(f"32-bit IPv4 integer out of range: {value}")
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def prefix_to_mask_int(prefix_len: int) -> int:
    """Compute unsigned 32-bit subnet mask from CIDR prefix length (0-32)."""
    if prefix_len < 0 or prefix_len > 32:
        raise ParameterValidationError(f"Invalid CIDR prefix length /{prefix_len}; must be 0..32.")
    if prefix_len == 0:
        return 0
    return (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF


def parse_cidr(cidr_str: str) -> tuple[int, int]:
    """Parse 'A.B.C.D/P' and validate that host bits are zero."""
    if "/" not in cidr_str:
        raise ParameterValidationError(f"Invalid CIDR '{cidr_str}': missing '/prefix'.")
    ip_part, prefix_part = cidr_str.strip().split("/", 1)
    if not prefix_part.isdigit():
        raise ParameterValidationError(f"Invalid CIDR prefix '{prefix_part}' in '{cidr_str}'.")
    prefix_len = int(prefix_part)
    ip_int = ip_to_int(ip_part)
    mask_int = prefix_to_mask_int(prefix_len)
    if (ip_int & mask_int) != ip_int:
        canonical = f"{int_to_ip(ip_int & mask_int)}/{prefix_len}"
        raise ParameterValidationError(
            f"Root prefix '{cidr_str}' has non-zero host bits; expected canonical network '{canonical}'."
        )
    return ip_int, prefix_len


def compute_summary_cidr(ranges: list[tuple[int, int]]) -> str:
    """Compute the tightest contiguous CIDR supernet covering all (net_int, bcast_int) ranges."""
    if not ranges:
        return "0.0.0.0/0"
    min_net = min(r[0] for r in ranges)
    max_bcast = max(r[1] for r in ranges)
    diff = min_net ^ max_bcast
    host_bits = diff.bit_length()
    prefix_len = 32 - host_bits
    mask_int = prefix_to_mask_int(prefix_len)
    summary_net = min_net & mask_int
    return f"{int_to_ip(summary_net)}/{prefix_len}"


def _required_host_bits(hosts: int) -> int:
    """Return smallest power-of-two host bit width fitting `hosts + 2` (min 2 bits -> /30)."""
    if hosts < 1:
        raise ParameterValidationError(f"Subnet host count must be >= 1, got {hosts}.")
    needed = hosts + 2  # Reserve network ID and broadcast address (RFC 950 / RFC 4632)
    bits = math.ceil(math.log2(needed))
    return max(2, bits)


def allocate_vlsm_subnets(spec: NetworkSpecification) -> VLSMPlan:
    """Perform descending-order bitwise VLSM allocation with zero-overlap verification."""
    root_net_int, root_prefix_len = parse_cidr(spec.root_prefix)
    root_mask_int = prefix_to_mask_int(root_prefix_len)
    root_wildcard_int = (~root_mask_int) & 0xFFFFFFFF
    root_broadcast_int = root_net_int | root_wildcard_int
    root_capacity = 1 << (32 - root_prefix_len)

    # Sort descending by block size / requested hosts per RFC 4632 VLSM packing rules
    sorted_requests = sorted(
        spec.subnet_requests,
        key=lambda req: (_required_host_bits(req.hosts), req.hosts, req.name),
        reverse=True,
    )

    allocated: list[AllocatedSubnet] = []
    allocated_ranges: list[tuple[int, int]] = []
    cursor = root_net_int

    for req in sorted_requests:
        host_bits = _required_host_bits(req.hosts)
        block_size = 1 << host_bits
        prefix_len = 32 - host_bits
        if prefix_len < root_prefix_len:
            raise AddressSpaceExhaustionError(
                root_prefix=spec.root_prefix,
                required_addresses=block_size,
                available_addresses=root_capacity,
                failed_subnet=req.name,
            )

        # Bitwise boundary alignment: round cursor up to multiple of block_size
        align_mask = block_size - 1
        aligned_net = (cursor + align_mask) & ~align_mask
        mask_int = prefix_to_mask_int(prefix_len)
        wildcard_int = (~mask_int) & 0xFFFFFFFF
        broadcast_int = aligned_net | wildcard_int

        if broadcast_int > root_broadcast_int:
            remaining = max(0, (root_broadcast_int - cursor) + 1)
            raise AddressSpaceExhaustionError(
                root_prefix=spec.root_prefix,
                required_addresses=block_size,
                available_addresses=remaining,
                failed_subnet=req.name,
            )

        usable_hosts = block_size - 2
        gateway_int = aligned_net + 1
        first_usable_int = aligned_net + 1 if req.security_zone == "wan_p2p" else aligned_net + 2
        last_usable_int = broadcast_int - 1
        if first_usable_int > last_usable_int:
            first_usable_int = gateway_int

        utilization_pct = round((req.hosts / usable_hosts) * 100.0, 2)
        wasted = usable_hosts - req.hosts

        allocated.append(
            AllocatedSubnet(
                name=req.name,
                vlan_id=req.vlan_id,
                security_zone=req.security_zone,
                area=req.area if req.area is not None else 0,
                requested_hosts=req.hosts,
                allocated_usable_hosts=usable_hosts,
                block_size=block_size,
                network_address=int_to_ip(aligned_net),
                prefix_length=prefix_len,
                cidr=f"{int_to_ip(aligned_net)}/{prefix_len}",
                subnet_mask=int_to_ip(mask_int),
                wildcard_mask=int_to_ip(wildcard_int),
                gateway_ip=int_to_ip(gateway_int),
                first_usable_ip=int_to_ip(first_usable_int),
                last_usable_ip=int_to_ip(last_usable_int),
                broadcast_address=int_to_ip(broadcast_int),
                utilization_pct=utilization_pct,
                wasted_addresses=wasted,
            )
        )
        allocated_ranges.append((aligned_net, broadcast_int))
        cursor = broadcast_int + 1

    # Explicit zero-overlap invariant check across all allocated blocks
    sorted_ranges = sorted(allocated_ranges, key=lambda r: r[0])
    for idx in range(len(sorted_ranges) - 1):
        curr_end = sorted_ranges[idx][1]
        next_start = sorted_ranges[idx + 1][0]
        if curr_end >= next_start:
            raise AssertionError(
                f"VLSM overlap invariant violated between {int_to_ip(curr_end)} and {int_to_ip(next_start)}"
            )

    total_requested = sum(s.requested_hosts for s in allocated)
    total_block_addrs = sum(s.block_size for s in allocated)
    total_usable = sum(s.allocated_usable_hosts for s in allocated)
    overall_util = round((total_requested / total_usable) * 100.0, 2) if total_usable else 0.0
    block_consumption_pct = round((total_block_addrs / root_capacity) * 100.0, 2)
    summary_cidr = compute_summary_cidr(allocated_ranges)

    justification = (
        f"Allocated {len(allocated)} non-overlapping VLSM subnets from root block {spec.root_prefix} "
        f"({root_capacity:,} total addresses) sorted descending by host demand per RFC 4632 to eliminate "
        f"internal fragmentation. Total requested hosts: {total_requested:,}; allocated usable capacity: "
        f"{total_usable:,} ({overall_util:.2f}% host-packing efficiency, consuming {total_block_addrs:,} "
        f"addresses / {block_consumption_pct:.2f}% of root prefix). Tightest summary supernet: {summary_cidr}."
    )

    return VLSMPlan(
        root_prefix=spec.root_prefix,
        root_capacity_addresses=root_capacity,
        total_requested_hosts=total_requested,
        total_allocated_addresses=total_block_addrs,
        total_usable_allocated=total_usable,
        overall_utilization_pct=overall_util,
        summary_route_cidr=summary_cidr,
        subnets=allocated,
        justification=justification,
    )
