"""Tests for the runtime feature controls in CoverAutomation.

Each runtime control (evening closure, morning opening, tilt angle control) gates one automation feature at runtime. These
tests use a real ResolvedConfig so the gates are evaluated exactly as in
production.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys, ResolvedConfig, resolve
from custom_components.smart_cover_automation.cover_automation import CoverAutomation, SensorData
from custom_components.smart_cover_automation.movement import (
    AutomationManagedState,
    AutomationMode,
    MovementControlReason,
    MovementDirection,
)

COVER = "cover.test"


def _make_resolved(overrides: dict[ConfKeys, Any] | None = None) -> ResolvedConfig:
    """Resolve a config for one cover with evening closure configured, plus overrides."""

    options: dict[str, Any] = {
        ConfKeys.COVERS.value: [COVER],
        ConfKeys.AUTOMATIC_REOPENING_MODE.value: const.ReopeningMode.ACTIVE.value,
        ConfKeys.EVENING_CLOSURE.value: const.EveningClosureControl.CLOSE_ONCE.value,
        ConfKeys.EVENING_CLOSURE_COVER_LIST.value: [COVER],
    }
    options.update({key.value: value for key, value in (overrides or {}).items()})
    return resolve(options)


def _make_automation(resolved: ResolvedConfig, managed_state: AutomationManagedState | None = None) -> CoverAutomation:
    """Create a CoverAutomation with mocked collaborators."""

    history = MagicMock()
    history.get_automation_managed_state = MagicMock(return_value=managed_state)
    history.get_automation_owned_position = MagicMock(return_value=None if managed_state is None else managed_state.position)
    history.get_closed_by_automation_reason = MagicMock(
        return_value=const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET if managed_state is not None else None
    )
    history.get_delayed_reopen_action = MagicMock(return_value=None)
    history.get_latest_entry = MagicMock(return_value=None)
    return CoverAutomation(
        entity_id=COVER,
        resolved=resolved,
        config={f"{COVER}_{const.COVER_SFX_AZIMUTH}": 180.0},
        cover_pos_history_mgr=history,
        ha_interface=MagicMock(),
        logger=MagicMock(),
    )


def _sensor_data(**overrides: Any) -> SensorData:
    """Create daytime sensor data with hot and sunny weather by default."""

    values: dict[str, Any] = {
        "sun_azimuth": 180.0,
        "sun_elevation": 45.0,
        "temp_max": 30.0,
        "temp_min": 18.0,
        "temp_hot": True,
        "weather_condition": "sunny",
        "weather_sunny": True,
        "evening_closure": False,
        "post_evening_closure": False,
    }
    values.update(overrides)
    return SensorData(**values)


class TestEveningClosureSetting:
    """Evening closure setting."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (const.EveningClosureControl.CLOSE_ONCE, MovementControlReason.EVENING_CLOSURE),
            (const.EveningClosureControl.CLOSE_AND_KEEP_CLOSED, MovementControlReason.EVENING_CLOSURE),
            (const.EveningClosureControl.OFF, None),
        ],
    )
    def test_evening_closure_cause(self, value: str, expected: MovementControlReason | None) -> None:
        """Evening closure only triggers when it is on."""

        automation = _make_automation(_make_resolved({ConfKeys.EVENING_CLOSURE: value}))

        assert automation._get_evening_closure_cause(_sensor_data(evening_closure=True)) == expected

    def test_off_ignores_missing_external_time(self) -> None:
        """A missing external evening closure time is irrelevant while evening closure is off."""

        automation = _make_automation(
            _make_resolved(
                {
                    ConfKeys.EVENING_CLOSURE: const.EveningClosureControl.OFF,
                    ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.EXTERNAL.value,
                }
            )
        )

        assert automation._has_missing_external_evening_closure_time(_sensor_data(has_valid_external_evening_closure_time=False)) is False


class TestMorningOpeningSwitch:
    """Morning opening switch."""

    @staticmethod
    def _evening_closed_state() -> AutomationManagedState:
        """Return a managed state as left behind by evening closure."""

        return AutomationManagedState(position=const.COVER_POS_FULLY_CLOSED, automation_mode=AutomationMode.EVENING_CLOSURE)

    def test_on_reopens_after_evening_closure(self) -> None:
        """With the switch on, a cover closed by evening closure reopens in the morning."""

        automation = _make_automation(_make_resolved(), managed_state=self._evening_closed_state())

        decision = automation._calculate_movement_decision(
            _sensor_data(temp_hot=False, weather_sunny=False), sun_hitting=False, current_pos=0
        )

        assert decision.direction == MovementDirection.OPENING
        assert decision.desired_position == const.COVER_POS_FULLY_OPEN

    def test_off_keeps_cover_closed_after_evening_closure(self) -> None:
        """With the switch off, a cover closed by evening closure stays closed."""

        automation = _make_automation(
            _make_resolved({ConfKeys.MORNING_OPENING_ENABLED: False}),
            managed_state=self._evening_closed_state(),
        )

        decision = automation._calculate_movement_decision(
            _sensor_data(temp_hot=False, weather_sunny=False), sun_hitting=False, current_pos=0
        )

        assert decision.direction == MovementDirection.HOLD
        assert decision.desired_position == 0

    def test_off_prevents_partial_reopen_by_heat_protection(self) -> None:
        """Heat protection must not open a cover the morning opening switch keeps closed."""

        automation = _make_automation(
            _make_resolved(
                {
                    ConfKeys.MORNING_OPENING_ENABLED: False,
                    ConfKeys.COVERS_MAX_CLOSURE: 20,
                }
            ),
            managed_state=self._evening_closed_state(),
        )

        decision = automation._calculate_movement_decision(_sensor_data(), sun_hitting=True, current_pos=0)

        assert decision.direction == MovementDirection.HOLD
        assert decision.desired_position == 0

    def test_off_resumes_after_manual_move(self) -> None:
        """Once the user has moved the cover away from the closed position, normal automation resumes."""

        automation = _make_automation(
            _make_resolved({ConfKeys.MORNING_OPENING_ENABLED: False}),
            managed_state=self._evening_closed_state(),
        )

        assert automation._is_morning_opening_suppressed(current_pos=60) is False

    def test_off_without_evening_closure_ownership_does_nothing(self) -> None:
        """Covers not closed by evening closure are unaffected by the switch."""

        heat_state = AutomationManagedState(position=const.COVER_POS_FULLY_CLOSED, automation_mode=AutomationMode.HEAT_PROTECTION)
        automation = _make_automation(
            _make_resolved({ConfKeys.MORNING_OPENING_ENABLED: False}),
            managed_state=heat_state,
        )

        assert automation._is_morning_opening_suppressed(current_pos=0) is False

    def test_off_without_evening_closure_configured_does_nothing(self) -> None:
        """Without evening closure, the morning opening setting has no effect."""

        automation = _make_automation(
            _make_resolved(
                {
                    ConfKeys.MORNING_OPENING_ENABLED: False,
                    ConfKeys.EVENING_CLOSURE: const.EveningClosureControl.OFF,
                }
            ),
            managed_state=self._evening_closed_state(),
        )

        assert automation._is_morning_opening_suppressed(current_pos=0) is False


class TestTiltControl:
    """Tilt angle control select."""

    @pytest.mark.parametrize(
        ("tilt_control", "is_night", "expected"),
        [
            (const.TiltControl.DAY_AND_NIGHT, False, const.TiltMode.OPEN),
            (const.TiltControl.DAY_AND_NIGHT, True, const.TiltMode.CLOSED),
            (const.TiltControl.DAY_ONLY, False, const.TiltMode.OPEN),
            (const.TiltControl.DAY_ONLY, True, None),
            (const.TiltControl.NIGHT_ONLY, False, None),
            (const.TiltControl.NIGHT_ONLY, True, const.TiltMode.CLOSED),
            (const.TiltControl.OFF, False, None),
            (const.TiltControl.OFF, True, None),
        ],
    )
    def test_tilt_mode_respects_tilt_control(
        self, tilt_control: const.TiltControl, is_night: bool, expected: const.TiltMode | None
    ) -> None:
        """The configured tilt mode is only returned for the times of day the control allows."""

        automation = _make_automation(
            _make_resolved(
                {
                    ConfKeys.TILT_CONTROL: tilt_control.value,
                    ConfKeys.TILT_MODE_DAY: const.TiltMode.OPEN.value,
                    ConfKeys.TILT_MODE_NIGHT: const.TiltMode.CLOSED.value,
                }
            )
        )
        automation._cover_supports_tilt = True

        assert automation._get_effective_tilt_mode(is_night=is_night) == expected
