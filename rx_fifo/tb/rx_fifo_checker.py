from typing import List

from tb_utils.generic_checker import GenericChecker


class RXFifoChecker(GenericChecker):
    """Packet-aware checker that tolerates dropped packets.

    The model enqueues one entry per packet committed *attempt* with a
    ``status`` field set to either ``"valid"`` (DUT actually output it) or
    ``"dropped"`` (DUT reverted it via cancel_o, e.g. due to fifo_full or a
    drop_i). The monitor only sees what was actually transmitted on the AXI
    stream, so its entries correspond one-to-one with the model's "valid"
    entries.

    Walking the model queue in order:
      * dropped entries are skipped (no monitor entry expected),
      * valid entries are matched against the next monitor packet.
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

    async def check(self, expected_queue, actual_queue):
        monitor_packets = await self._drain_monitor_packets(actual_queue)
        monitor_idx = 0

        while not expected_queue.empty():
            model_pkt = await expected_queue.get()
            if model_pkt.get("status") == "dropped":
                continue

            if monitor_idx >= len(monitor_packets):
                msg = (
                    "Model expected a valid packet but no more monitor "
                    f"packets remain: {model_pkt['beats']}"
                )
                if self.fatal:
                    raise RuntimeError(msg)
                print(f"[WARNING] {msg}")
                return

            expected_beats = model_pkt["beats"]
            observed_beats = monitor_packets[monitor_idx]
            if expected_beats != observed_beats:
                msg = (
                    f"Packet {monitor_idx} mismatch:\n"
                    f"  model   = {expected_beats}\n"
                    f"  monitor = {observed_beats}"
                )
                if self.fatal:
                    raise RuntimeError(msg)
                print(f"[WARNING] {msg}")
            monitor_idx += 1

        if monitor_idx < len(monitor_packets):
            extras = monitor_packets[monitor_idx:]
            msg = f"Monitor produced {len(extras)} unexpected packet(s): {extras}"
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
