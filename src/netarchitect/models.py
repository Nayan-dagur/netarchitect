"""Pydantic models for NetArchitect inputs, algorithmic outputs, and rationale logs."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


MediaChoice = Literal["auto", "copper", "mmf", "smf"]
LinkRole = Literal["access", "backbone", "man", "wan"]
SecurityZone = Literal["corp", "voice", "iot", "mgmt", "dmz", "wan_p2p", "cloud"]
TopologyTier = Literal["campus_lan", "metro_man", "global_wan", "custom"]
RedundancyMode = Literal["single", "rstp_redundant", "dual_homed", "multi_homed_bgp"]


class SiteSpec(BaseModel):
    name: str = Field(..., min_length=1)
    role: Literal["hq", "building", "remote", "colo", "cloud_vpc", "branch"] = "building"
    endpoints: int = Field(default=0, ge=0)
    poe_aps: int = Field(default=0, ge=0)
    iot_scanners: int = Field(default=0, ge=0)


class LinkSpec(BaseModel):
    name: str = Field(..., min_length=1)
    src: str = Field(..., min_length=1)
    dst: str = Field(..., min_length=1)
    distance_m: float = Field(..., gt=0, description="Physical cable/fiber distance in meters")
    bandwidth_gbps: float = Field(default=10.0, gt=0)
    requested_media: MediaChoice = "auto"
    role: LinkRole = "backbone"
    dual_homed: bool = False
    max_latency_ms: Optional[float] = Field(default=None, gt=0)
    require_ipsec: bool = False


class SubnetRequest(BaseModel):
    name: str = Field(..., min_length=1)
    hosts: int = Field(..., ge=1, description="Number of usable host IPs required")
    vlan_id: Optional[int] = Field(default=None, ge=2, le=4094)
    security_zone: SecurityZone = "corp"
    area: Optional[int] = Field(default=None, ge=0)


class NetworkSpecification(BaseModel):
    profile_name: str = Field(..., min_length=1)
    description: str = ""
    topology_tier: TopologyTier = "custom"
    sites: list[SiteSpec] = Field(default_factory=list)
    links: list[LinkSpec] = Field(..., min_length=1)
    root_prefix: str = Field(..., description="Root IPv4 CIDR block, e.g., 10.10.0.0/16")
    subnet_requests: list[SubnetRequest] = Field(..., min_length=1)
    autonomous_system: Optional[int] = Field(default=None, ge=1, le=4294967295)
    multi_site: bool = False
    multi_cloud: bool = False
    target_latency_ms: Optional[float] = Field(default=None, gt=0)
    redundancy_mode: RedundancyMode = "rstp_redundant"

    @field_validator("subnet_requests")
    @classmethod
    def check_unique_vlan_and_names(cls, v: list[SubnetRequest]) -> list[SubnetRequest]:
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("Subnet request names must be unique.")
        vlans = [s.vlan_id for s in v if s.vlan_id is not None]
        if len(vlans) != len(set(vlans)):
            raise ValueError("Assigned VLAN IDs must be unique.")
        if 1 in vlans or 999 in vlans:
            raise ValueError("VLAN 1 (default) and VLAN 999 (reserved blackhole native) cannot be assigned to user subnets.")
        return v


class MediaRecommendation(BaseModel):
    link_name: str
    src: str
    dst: str
    distance_m: float
    bandwidth_gbps: float
    selected_media: str
    transceiver: str
    wavelength_or_standard: str
    estimated_optical_loss_db: Optional[float] = None
    optical_budget_db: Optional[float] = None
    estimated_propagation_ms: float
    justification: str


class Layer2Design(BaseModel):
    spanning_tree_mode: str
    root_bridge_vlan_scope: str
    native_vlan: int = 999
    allowed_vlans: list[int]
    total_poe_budget_watts: int
    qos_profile: Optional[str] = None
    evpl_enabled: bool = False
    justifications: list[str]


class AllocatedSubnet(BaseModel):
    name: str
    vlan_id: Optional[int] = None
    security_zone: SecurityZone
    area: int = 0
    requested_hosts: int
    allocated_usable_hosts: int
    block_size: int
    network_address: str
    prefix_length: int
    cidr: str
    subnet_mask: str
    wildcard_mask: str
    gateway_ip: str
    first_usable_ip: str
    last_usable_ip: str
    broadcast_address: str
    utilization_pct: float
    wasted_addresses: int


class VLSMPlan(BaseModel):
    root_prefix: str
    root_capacity_addresses: int
    total_requested_hosts: int
    total_allocated_addresses: int
    total_usable_allocated: int
    overall_utilization_pct: float
    summary_route_cidr: str
    subnets: list[AllocatedSubnet]
    justification: str


class RoutingRecommendation(BaseModel):
    igp_protocol: str
    egp_protocol: Optional[str] = None
    ospf_areas: list[int]
    route_summarization_enabled: bool
    summary_routes: list[str]
    area_summary_routes: dict[int, str] = Field(default_factory=dict)
    ipsec_vpn_enabled: bool
    justifications: list[str]


class DeviceConfigBundle(BaseModel):
    core_switch_ios: str
    access_switch_ios: str
    edge_router_ios: str
    combined_ios_cfg: str


class ArchitecturePlan(BaseModel):
    profile_name: str
    topology_tier: TopologyTier
    total_endpoints: int
    media_recommendations: list[MediaRecommendation]
    layer2_design: Layer2Design
    vlsm_plan: VLSMPlan
    routing_recommendation: RoutingRecommendation
    device_configs: DeviceConfigBundle
    architectural_rationale_log: list[str]
