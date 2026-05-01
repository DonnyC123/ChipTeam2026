from typing import List

from tb_utils.generic_checker import GenericChecker


class RXFifoChecker(GenericChecker):
    """Checker that walks the model queue alongside two monitor queues.

    Inputs:
      * ``expected_queue`` (model): ``{"beats": [...], "dropped": bool}`` per
        packet the input sequence committed (``send_i``) or aborted
        (``drop_i``).
      * ``axi_queue`` (event monitor): ``{"beats": [...]}`` per AXI-stream
        output packet the DUT actually emitted.
      * ``cancel_queue`` (event monitor): one entry per ``cancel_o`` revert.

    For each model packet, in order:
      * if ``dropped`` (drop_i): skip.
      * else: try to match the next AXI packet. If beats agree, consume it.
        Otherwise (or if the AXI queue is exhausted) consume one cancel
        entry to account for a fifo_full revert.
    """

    async def _drain_axi(self, axi_queue) -> List[dict]:
        items = []
        while not axi_queue.empty():
            items.append(await axi_queue.get())
        return items

    async def _drain_cancels(self, cancel_queue) -> int:
        count = 0
        while not cancel_queue.empty():
            await cancel_queue.get()
            count += 1
        return count

    async def check(self, expected_queue, axi_queue, cancel_queue):
        axi_packets = await self._drain_axi(axi_queue)
        cancels_remaining = await self._drain_cancels(cancel_queue)

        axi_idx = 0
        idx = 0
        while not expected_queue.empty():
            model_pkt = await expected_queue.get()
            idx += 1

            if model_pkt["dropped"]:
                continue

            expected_beats = model_pkt["beats"]

            # Prefer matching against the next AXI output.
            if (
                axi_idx < len(axi_packets)
                and axi_packets[axi_idx]["beats"] == expected_beats
            ):
                axi_idx += 1
                continue

            # Otherwise this packet must have been reverted (fifo_full) -
            # consume a cancel entry.
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
