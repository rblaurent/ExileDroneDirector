"""Executable contracts for local Flypath draft undo and redo."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest


DOCUMENT_DIR = Path(__file__).resolve().parents[1] / "document"
sys.path.insert(0, str(DOCUMENT_DIR))

from draft_history import DraftHistory, DraftHistoryError, DraftState, validate_state
from flypath_document import LensState, RevisionDocument, Segment, Waypoint


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def waypoint(value: int) -> Waypoint:
    return Waypoint(
        waypoint_id=value,
        position=(float(value * 100), float(value * 10), 500.0),
        body_rotation=IDENTITY,
        gimbal_rotation=IDENTITY,
        lens=LensState(35.0 + value, 2.8, 1000.0),
    )


def state(ids: tuple[int, ...], selected: int | None = None, next_id: int | None = None) -> DraftState:
    points = tuple(waypoint(value) for value in ids)
    segments = tuple(
        Segment(index + 1, points[index].waypoint_id, points[index + 1].waypoint_id)
        for index in range(max(0, len(points) - 1))
    )
    document = RevisionDocument(
        revision_number=1,
        region_id="ExiledLands",
        waypoints=points,
        segments=segments,
        duration_seconds=sum(segment.duration_seconds for segment in segments),
    )
    return DraftState(
        document=document,
        selected_waypoint_index=(-1 if not points else len(points) - 1) if selected is None else selected,
        next_waypoint_id=(max(ids, default=0) + 1) if next_id is None else next_id,
    )


class DraftHistoryContracts(unittest.TestCase):
    def test_empty_history_is_a_no_op(self) -> None:
        history = DraftHistory()
        current = state((1, 2))
        self.assertEqual(history.undo(current), (current, False))
        self.assertEqual(history.redo(current), (current, False))

    def test_capture_replace_delete_chain_round_trips_exactly(self) -> None:
        history = DraftHistory()
        empty = state(())
        first = state((1,))
        second = state((1, 2))
        replaced_document = replace(
            second.document,
            waypoints=(second.document.waypoints[0], replace(second.document.waypoints[1], position=(9.0, 8.0, 7.0))),
        )
        replaced = replace(second, document=replaced_document)
        deleted = state((1,), selected=0, next_id=3)

        current = empty
        for edited in (first, second, replaced, deleted):
            history.record_before_edit(current)
            current = edited

        for expected in (replaced, second, first, empty):
            current, changed = history.undo(current)
            self.assertTrue(changed)
            self.assertEqual(current, expected)
        self.assertEqual(history.undo(current), (empty, False))

        for expected in (first, second, replaced, deleted):
            current, changed = history.redo(current)
            self.assertTrue(changed)
            self.assertEqual(current, expected)
        self.assertEqual(history.redo(current), (deleted, False))

    def test_new_edit_after_undo_clears_redo_branch(self) -> None:
        history = DraftHistory()
        empty = state(())
        first = state((1,))
        second = state((1, 2))
        history.record_before_edit(empty)
        history.record_before_edit(first)
        current, changed = history.undo(second)
        self.assertTrue(changed)
        self.assertEqual(current, first)
        history.record_before_edit(current)
        branched = state((1, 5), next_id=6)
        self.assertEqual(history.redo(branched), (branched, False))

    def test_history_limit_discards_only_the_oldest_transaction(self) -> None:
        history = DraftHistory(limit=2)
        empty = state(())
        first = state((1,))
        second = state((1, 2))
        third = state((1, 2, 3))
        history.record_before_edit(empty)
        history.record_before_edit(first)
        history.record_before_edit(second)
        self.assertEqual(history.undo_count, 2)
        current, _ = history.undo(third)
        self.assertEqual(current, second)
        current, _ = history.undo(current)
        self.assertEqual(current, first)
        self.assertEqual(history.undo(current), (first, False))

    def test_snapshots_are_deeply_independent(self) -> None:
        history = DraftHistory()
        original = state((1, 2))
        history.record_before_edit(original)
        current = state((1, 2, 3))
        restored, changed = history.undo(current)
        self.assertTrue(changed)
        self.assertIsNot(restored, original)
        self.assertIsNot(restored.document, original.document)

    def test_invalid_selection_or_next_id_is_rejected_before_history_mutates(self) -> None:
        history = DraftHistory()
        invalid_selection = replace(state((1,)), selected_waypoint_index=4)
        with self.assertRaisesRegex(DraftHistoryError, "selection"):
            history.record_before_edit(invalid_selection)
        invalid_next = replace(state((1, 7)), next_waypoint_id=7)
        with self.assertRaisesRegex(DraftHistoryError, "must exceed"):
            validate_state(invalid_next)
        self.assertEqual(history.undo_count, 0)
        self.assertEqual(history.redo_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
