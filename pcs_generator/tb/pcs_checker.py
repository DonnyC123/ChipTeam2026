from __future__ import annotations

from typing import Sequence

from pcs_generator.tb.pcs_debug import (
    ActualFrameRecord,
    ExpectedFrameRecord,
    format_extra_frames,
    format_frame_mismatch,
)
from tb_utils.generic_checker import GenericChecker


class PCSChecker(GenericChecker):
    def _raise_or_warn(self, message: str) -> None:
        if self.fatal:
            raise RuntimeError(message)
        print(f"[WARNING] {message}")

    @staticmethod
    async def _drain_remaining(queue) -> list:
        items = []
        while not queue.empty():
            items.append(await queue.get())
        return items

    @staticmethod
    def _assert_frame_record_type(record, expected_type, queue_name: str) -> None:
        if not isinstance(record, expected_type):
            raise TypeError(
                f"{queue_name} queue must contain {expected_type.__name__}, "
                f"got {type(record).__name__}"
            )

    def _report_extra_frames(
        self,
        *,
        expected_frames: Sequence[ExpectedFrameRecord],
        actual_frames: Sequence[ActualFrameRecord],
        model,
        monitor,
    ) -> None:
        message = format_extra_frames(
            expected_frames=expected_frames,
            actual_frames=actual_frames,
            recent_expected_activity=model.recent_activity,
            recent_actual_blocks=monitor.recent_blocks,
        )
        self._raise_or_warn(message)

    async def check(self, model, monitor):
        expected_queue = model.expected_queue
        actual_queue = monitor.actual_queue

        while (not expected_queue.empty()) and (not actual_queue.empty()):
            actual_frame = await actual_queue.get()
            expected_frame = await expected_queue.get()
            self._assert_frame_record_type(expected_frame, ExpectedFrameRecord, "expected")
            self._assert_frame_record_type(actual_frame, ActualFrameRecord, "actual")

            if expected_frame.payload != actual_frame.payload:
                self._raise_or_warn(format_frame_mismatch(expected_frame, actual_frame))
                return

        if expected_queue.empty() and actual_queue.empty():
            return

        expected_frames = await self._drain_remaining(expected_queue)
        actual_frames = await self._drain_remaining(actual_queue)
        for frame in expected_frames:
            self._assert_frame_record_type(frame, ExpectedFrameRecord, "expected")
        for frame in actual_frames:
            self._assert_frame_record_type(frame, ActualFrameRecord, "actual")

        self._report_extra_frames(
            expected_frames=expected_frames,
            actual_frames=actual_frames,
            model=model,
            monitor=monitor,
        )
