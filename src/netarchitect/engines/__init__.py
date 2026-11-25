"""Algorithmic rule engines for L1/L2 physics, L3 VLSM, and routing selection."""

from netarchitect.engines.media_engine import evaluate_layer1_links, evaluate_layer2_design
from netarchitect.engines.routing_engine import select_routing_architecture
from netarchitect.engines.vlsm_engine import allocate_vlsm_subnets

__all__ = [
    "evaluate_layer1_links",
    "evaluate_layer2_design",
    "allocate_vlsm_subnets",
    "select_routing_architecture",
]
