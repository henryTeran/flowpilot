"""Deterministic resource matching over complete, half-open service intervals."""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ResourceTimeline:
    resource_id: str
    kind: str
    capabilities: frozenset[str] = frozenset()
    reservations: tuple[tuple[datetime, datetime], ...] = ()
    active: bool = True
    capacity_known: bool = True


@dataclass(frozen=True)
class ResourceNeed:
    kind: str
    capability: str = ""
    quantity: int = 1


@dataclass(frozen=True)
class ResourceMatch:
    start: datetime
    end: datetime
    resource_ids: tuple[str, ...]


def match_resources(resources, needs, start: datetime, end: datetime) -> ResourceMatch | None:
    """Every unit consumes a distinct resource; touching reservations are legal.

    Augmenting paths prevent a generic requirement from stealing the only resource
    capable of satisfying a specialized requirement. Input order never decides
    which resource wins. Unknown occupancy cannot be treated as free capacity.
    """
    if end <= start:
        raise ValueError("Resource interval must be positive")
    inventory = sorted(resources, key=lambda resource: resource.resource_id)
    if len({resource.resource_id for resource in inventory}) != len(inventory):
        raise ValueError("Resource identifiers must be unique")
    slots = []
    for need in needs:
        if not 1 <= need.quantity <= 10:
            raise ValueError("Resource quantity must be between 1 and 10")
        candidates = tuple(resource.resource_id for resource in inventory
            if resource.active and resource.capacity_known and resource.kind == need.kind
            and (not need.capability or need.capability in resource.capabilities)
            and all(end <= booked_start or start >= booked_end
                    for booked_start, booked_end in resource.reservations))
        slots.extend([candidates] * need.quantity)
    slots.sort(key=lambda candidates: (len(candidates), candidates))

    owners = {}

    def assign(index, visited):
        for resource_id in slots[index]:
            if resource_id in visited:
                continue
            visited.add(resource_id)
            if resource_id not in owners or assign(owners[resource_id], visited):
                owners[resource_id] = index
                return True
        return False

    for index in range(len(slots)):
        if not assign(index, set()):
            return None
    return ResourceMatch(start, end, tuple(sorted(owners)))


def next_resource_window(resources, needs, earliest: datetime, duration_minutes: int,
                         latest_end: datetime | None = None) -> ResourceMatch | None:
    """Find the earliest complete window; only reservation ends can improve capacity."""
    if duration_minutes <= 0:
        raise ValueError("Resource duration must be positive")
    resources, needs = tuple(resources), tuple(needs)
    boundaries = {earliest}
    boundaries.update(end for resource in resources for _, end in resource.reservations if end > earliest)
    for start in sorted(boundaries):
        end = start + timedelta(minutes=duration_minutes)
        if latest_end is not None and end > latest_end:
            break
        matched = match_resources(resources, needs, start, end)
        if matched is not None:
            return matched
    return None
