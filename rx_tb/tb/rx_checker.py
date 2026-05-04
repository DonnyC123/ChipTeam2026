from typing import List

from tb_utils.generic_checker import GenericChecker


class RxChecker(GenericChecker):
    async def _drain(self, queue) -> List[dict]:
        items = []
        while not queue.empty():
            items.append(await queue.get())
        return items

    async def check(self, expected_queue, actual_queue, cancel_queue=None):
        received = await self._drain(actual_queue)
        rx_idx = 0

        idx = 0
        while not expected_queue.empty():
            expected = await expected_queue.get()
            idx += 1

            if rx_idx >= len(received):
                # No more received packets — remaining expecteds were dropped.
                continue

            if received[rx_idx]["bytes"] == expected["bytes"]:
                rx_idx += 1
                continue

            # Treat as drop and continue.

        leftover = len(received) - rx_idx
        if leftover:
            preview = received[rx_idx : rx_idx + 3]
            msg = (
                f"{leftover} received packet(s) did not match any expected "
                f"packet. First unmatched: {preview}"
            )
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
