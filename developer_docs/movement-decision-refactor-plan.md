# Movement Decision Pipeline Refactor Plan

## Goal

Use `MovementDecision` as the single internal representation of a cover action from decision calculation through execution. Remove the legacy `CoverMovementReason` adapter layer without changing cover movement, tilt, ownership, logbook, or manual-override behavior.

## Motivation

`_calculate_movement_decision()` produces a complete decision: desired position, direction, control reason, and lockout state. The preparation path immediately reduces it to `CoverMovementReason | None` via `_movement_decision_to_legacy_tuple()`.

That conversion is lossy. For example, a daytime `HOLD` decision at an already-matching target has a daytime control reason but becomes `None`. This makes downstream behavior depend on two overlapping models and obscures the difference between a no-op daytime decision and an unclassified hold.

## Scope

- Replace internal uses of `CoverMovementReason` with `MovementDecision`.
- Keep `MovementDecision` intact through cover execution, tilt selection, ownership updates, and logbook entry selection.
- Make queued execution identity derive from `MovementDecision`, not a legacy reason.
- Remove the legacy tuple wrapper and conversion helpers after all call sites have migrated.
- Preserve existing persisted state formats and Home Assistant-facing behavior.

## Non-Goals

- Change daytime, heat-protection, evening-closure, lock, or manual-override policies.
- Change service schemas, configuration, translations, or persisted automation-managed-state formats.
- Redesign the public integration API.

## Implementation Steps

1. Preserve existing behavior coverage and add only the gaps exposed by this refactor.
   - Migrate existing `_calculate_desired_position()` tests to `_calculate_movement_decision()` assertions instead of creating a second decision matrix.
   - Add one regression each for delayed-reopen tilt preparation, a passive daytime matching-target no-op, and queued plans whose decision or manual-override expiry context differs.
   - Retain the manual-override bypass test that distinguishes the initial evening-closure trigger from the overnight keep-closed period.
   - Retain the existing position, tilt, movement-dispatch, logbook, ownership, and manual-override tests as their method inputs migrate.

2. Make the execution plan carry `MovementDecision`.
   - Replace `desired_pos`, `movement_reason`, the optional `movement_decision`, and `effective_movement_decision` in `CoverExecutionPlan` with one required decision object.
   - Retain `manual_override_just_expired` as execution context for logbook selection; it is not a second movement representation.
   - Remove `manual_override_just_expired` from `_calculate_movement_decision()` because it does not affect decision semantics; pass it from evaluation directly into the execution plan and logbook selection.
   - Populate `CoverState.pos_target_desired` and `CoverState.lockout_protection` directly from that object.
   - Define `CoverExecutionPlan.signature` from the complete decision, manual-override expiry context, and planned tilt target so staggered execution deduplicates only equivalent actions.
   - Change `ScheduledCoverExecution.plan_signature` and its test fixtures to use the same signature type.
   - Add one `_requires_execution_plan()` predicate. It returns true for every opening or closing decision and for hold decisions whose control reason is `HEAT_PROTECTION` or `TILT_TO_COVER_OPEN_DELAY`; all other holds are observation-only no-ops.
   - Remove `_calculate_desired_position()` rather than adapting its legacy tuple return type.

3. Migrate tilt planning.
   - Change `_determine_target_tilt()`, `_apply_tilt()`, and their helpers to accept `MovementDecision` only.
   - Preserve special behavior for heat-protection reopening, evening closure, delayed tilt-to-cover reopening, and manual-override recovery.
   - Use one shared decision-based night-context predicate for the two tilt call sites; do not duplicate the control-reason mapping.

4. Migrate movement execution and logbook selection.
   - Remove the optional `movement_decision` parameter from `_move_cover_if_needed()` and make it its required semantic input.
   - Derive logbook verb and reason directly from `MovementDirection`, `MovementControlReason`, previous automation mode, and manual-override expiry.
   - Keep the existing no-movement and minimum-delta short-circuits, including cleanup for completed reopening decisions.

5. Migrate ownership and history handling.
   - Continue recording ownership only after successful physical movement.
   - Verify that true no-ops record observations without creating ownership.
   - Verify that actionable holds retain their current tilt preparation, cleanup, and history behavior without creating ownership solely because they are holds.
   - Retain the current cleanup behavior when reopening completes without movement because the cover is already at, or within the configured delta of, its target.

6. Delete the retired compatibility layer.
   - Remove `CoverMovementReason`, `_OPENING_REASONS`, `_calculate_desired_position()`, `_movement_control_reason_for_opening_reason()`, `_movement_decision_from_legacy_reason()`, `_legacy_reason_for_movement_decision()`, and `_movement_decision_to_legacy_tuple()` once no call sites remain.
   - Delete the duplicate evening-closure reason helper. Update `_should_ignore_manual_override()` to compare the existing evening-closure control-reason helper with `EVENING_CLOSURE`.
   - Make lockout evaluation accept `MovementDirection` directly because lockout is evaluated before a decision exists. Retain only shared decision-based predicates that prevent duplication, such as execution-plan eligibility and tilt night context.
   - Remove tests that only exercise conversion mechanics; retain or replace them with behavior-level decision pipeline tests.

## Validation

- Run focused cover-automation, tilt-control, and automation-engine tests while each migration step is in progress.
- Run `python3 -m pytest tests/cover_automation/test_cover_automation.py tests/cover_automation/test_tilt_control.py tests/automation_engine/test_automation_engine.py tests/integration/test_runtime_real_ha.py -q` after the complete pipeline migration.
- Run `./scripts/lint` and `./scripts/test` before merging.
- Review the diff for accidental changes to persistence keys, translations, service schemas, and logbook translation keys.

## Completion Criteria

- `CoverMovementReason` and all legacy conversion helpers are absent from production code.
- A single `MovementDecision` reaches every internal component that needs movement semantics.
- Queued execution compares the decision, manual-override expiry context, and tilt target, with tests proving that semantically distinct plans are not deduplicated.
- Existing behavioral tests pass, with targeted regressions for no-op, delayed-reopen, and queued-plan paths.
- No public configuration, service, entity, or persistence contract changes.