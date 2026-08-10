"""Engine-independent transactional history contract for a local Flypath draft.

The cooked implementation remains Blueprint-only.  This module defines the
value-snapshot semantics that the client director must match while authoring is
still backed by transitional parallel waypoint channels.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from flypath_document import RevisionDocument, validate_document


class DraftHistoryError(ValueError):
    """A draft or history operation would violate the authoring contract."""


@dataclass(frozen=True)
class DraftState:
    document: RevisionDocument
    selected_waypoint_index: int
    next_waypoint_id: int


def validate_state(state: DraftState) -> None:
    validate_document(state.document)
    count = len(state.document.waypoints)
    expected_selection = {-1} if count == 0 else set(range(count))
    if state.selected_waypoint_index not in expected_selection:
        raise DraftHistoryError(
            f"selection {state.selected_waypoint_index} is invalid for {count} waypoints"
        )
    maximum_id = max((waypoint.waypoint_id for waypoint in state.document.waypoints), default=0)
    if state.next_waypoint_id <= maximum_id:
        raise DraftHistoryError(
            f"next waypoint ID {state.next_waypoint_id} must exceed existing maximum {maximum_id}"
        )


def clone_state(state: DraftState) -> DraftState:
    validate_state(state)
    return deepcopy(state)


class DraftHistory:
    """Bounded full-state history for the current local-authoring milestone.

    A future command-based editor may store smaller deltas, but its externally
    observable transaction semantics must remain identical.
    """

    def __init__(self, limit: int = 64):
        if limit < 1:
            raise DraftHistoryError("history limit must be positive")
        self.limit = int(limit)
        self._undo: list[DraftState] = []
        self._redo: list[DraftState] = []

    @property
    def undo_count(self) -> int:
        return len(self._undo)

    @property
    def redo_count(self) -> int:
        return len(self._redo)

    def _push_bounded(self, stack: list[DraftState], state: DraftState) -> None:
        stack.append(clone_state(state))
        if len(stack) > self.limit:
            del stack[0]

    def record_before_edit(self, current: DraftState) -> None:
        """Begin one edit transaction and invalidate its former redo branch."""

        self._push_bounded(self._undo, current)
        self._redo.clear()

    def undo(self, current: DraftState) -> tuple[DraftState, bool]:
        validate_state(current)
        if not self._undo:
            return clone_state(current), False
        restored = self._undo.pop()
        self._push_bounded(self._redo, current)
        return clone_state(restored), True

    def redo(self, current: DraftState) -> tuple[DraftState, bool]:
        validate_state(current)
        if not self._redo:
            return clone_state(current), False
        restored = self._redo.pop()
        self._push_bounded(self._undo, current)
        return clone_state(restored), True

