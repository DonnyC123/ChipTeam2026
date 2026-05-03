from typing import List

from tb_utils.generic_checker import GenericChecker


class RXFifoChecker(GenericChecker):
    async def _drain_axi(self, actual_queue) -> List[dict]:
        items = []
        while not actual_queue.empty():
            items.append(await actual_queue.get())
        return items

    async def _drain_cancels(self, cancel_queue) -> int:
        count = 0
        while not cancel_queue.empty():
            await cancel_queue.get()
            count += 1
        return count

    async def check(self, expected_queue, actual_queue, cancel_queue=None):
        if cancel_queue is None:
            raise ValueError("RXFifoChecker.check requires a cancel_queue")
        axi_packets = await self._drain_axi(actual_queue)
        cancels_remaining = await self._drain_cancels(cancel_queue)

        axi_idx = 0
        idx = 0
        while not expected_queue.empty():
            model_pkt = await expected_queue.get()
            idx += 1

            if model_pkt["dropped"]:
                continue

            expected_beats = model_pkt["beats"]

            if (
                axi_idx < len(axi_packets)
                and axi_packets[axi_idx]["beats"] == expected_beats
            ):
                axi_idx += 1
                continue

            if cancels_remaining > 0:
                cancels_remaining -= 1
                continue

            # No AXI match and no cancel left to absorb the gap.
            if axi_idx < len(axi_packets):
                msg = (
                    f"Packet {idx} mismatch:\n"
                    f"  model = {expected_beats}\n"
                    f"  next axi = {axi_packets[axi_idx]['beats']}"
                )
            else:
                msg = (
                    f"Packet {idx} expected an output event but no AXI or "
                    f"cancel events remain: beats={expected_beats}"
                )
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
            return

        leftover_axi = len(axi_packets) - axi_idx
        if leftover_axi or cancels_remaining:
            msg = (
                f"Unconsumed events: axi_remaining={leftover_axi}, "
                f"cancels_remaining={cancels_remaining}"
            )
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
