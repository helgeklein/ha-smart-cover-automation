"""Movement and automation-ownership domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MovementDirection(StrEnum):
    """Physical direction of a cover move."""

    OPENING = "opening"
    CLOSING = "closing"
    HOLD = "hold"


class MovementControlReason(StrEnum):
    """Semantic reason for the current movement decision."""

    HEAT_PROTECTION = "heat_protection"
    EVENING_CLOSURE = "evening_closure"
    EVENING_CLOSURE_HOLD = "evening_closure_hold"
    MORNING_OPENING = "morning_opening"
    LET_LIGHT_IN = "let_light_in"
    TILT_TO_COVER_OPEN_DELAY = "tilt_to_cover_open_delay"


class AutomationMode(StrEnum):
    """Durable automation-owned regimes that may survive restart."""

    HEAT_PROTECTION = "heat_protection"
    EVENING_CLOSURE = "evening_closure"


@dataclass(slots=True, frozen=True)
class MovementDecision:
    """Resolved movement decision for one evaluation cycle."""

    desired_position: int
    direction: MovementDirection
    control_reason: MovementControlReason | None
    lockout_protection_active: bool


@dataclass(slots=True, frozen=True)
class AutomationManagedState:
    """Automation-owned cover state that may drive follow-up transitions."""

    position: int
    automation_mode: AutomationMode
