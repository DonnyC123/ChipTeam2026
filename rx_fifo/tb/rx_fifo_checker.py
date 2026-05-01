from typing import List

from tb_utils.generic_checker import GenericChecker


class RXFifoChecker(GenericChecker):
    """Packet-aware checker.

    The model enqueues one entry per committed packet: ``{"beats": [d0, d1, ...]}``.
    The monitor enqueues one entry per output lane: ``{"data": d, "last": bool}``.
    Lanes are grouped into packets by the ``last`` flag, then each model packet
    is matched in order against the corresponding monitor packet.
    """

    async def _drain_monitor_packets(self, actual_queue) -> List[List[int]]:
        packets: List[List[int]] = []
        current: List[int] = []
        while not actual_queue.empty():
            entry = await actual_queue.get()
            current.append(entry["data"])
            if entry["last"]:
                packets.append(current)
                current = []
        if current:
            raise RuntimeError(
                f"Monitor produced trailing beats with no `last`: {current}"
            )
        return packets

    async def _drain_model_packets(self, expected_queue) -> List[List[int]]:
        packets: List[List[int]] = []
        while not expected_queue.empty():
            entry = await expected_queue.get()
            packets.append(list(entry["beats"]))
        return packets

    async def check(self, expected_queue, actual_queue):
        model_packets = await self._drain_model_packets(expected_queue)
        monitor_packets = await self._drain_monitor_packets(actual_queue)

        if len(model_packets) != len(monitor_packets):
            msg = (
                f"Packet count mismatch: "
                f"model={len(model_packets)}, monitor={len(monitor_packets)}"
            )
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
            return

        for idx, (mp, np_) in enumerate(zip(model_packets, monitor_packets)):
            if mp != np_:
                msg = (
                    f"Packet {idx} mismatch:\n"
                    f"  model   = {mp}\n"
                    f"  monitor = {np_}"
                )
                if self.fatal:
                    raise RuntimeError(msg)
                print(f"[WARNING] {msg}")
