"""Custom domain exceptions for NetArchitect boundary and constraint checks."""


class NetArchitectError(Exception):
    """Base exception for all NetArchitect algorithmic and validation errors."""


class PhysicalDistanceViolationError(NetArchitectError):
    """Raised when a requested physical medium violates IEEE/TIA distance limits."""

    def __init__(
        self,
        link_name: str,
        requested_media: str,
        distance_m: float,
        max_distance_m: float,
        warning: str,
    ) -> None:
        self.link_name = link_name
        self.requested_media = requested_media
        self.distance_m = distance_m
        self.max_distance_m = max_distance_m
        self.warning = warning
        super().__init__(
            f"[{link_name}] PhysicalDistanceViolationError: {requested_media} requested for "
            f"{distance_m:.1f}m exceeds maximum supported limit of {max_distance_m:.1f}m. {warning}"
        )


class AddressSpaceExhaustionError(NetArchitectError):
    """Raised when requested VLSM subnets exceed the capacity of the root CIDR prefix."""

    def __init__(
        self,
        root_prefix: str,
        required_addresses: int,
        available_addresses: int,
        failed_subnet: str,
    ) -> None:
        self.root_prefix = root_prefix
        self.required_addresses = required_addresses
        self.available_addresses = available_addresses
        self.failed_subnet = failed_subnet
        super().__init__(
            f"AddressSpaceExhaustionError: Cannot allocate '{failed_subnet}' within {root_prefix}. "
            f"Cumulative aligned demand ({required_addresses} addresses) exceeds remaining/total "
            f"root capacity ({available_addresses} addresses)."
        )


class ParameterValidationError(NetArchitectError):
    """Raised when input network parameters fail schema or sanity bounds."""
