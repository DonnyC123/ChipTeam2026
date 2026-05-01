from collections import deque
from typing import Any, Deque, Dict

from tb_utils.generic_checker import GenericChecker


class RXFifoChecker(GenericChecker):
    """Checker that walks the model queue alongside a combined event queue.

    Model queue entries: ``{"beats": [...], "dropped": bool}`` -- one per
    packet the input sequence committed (``send_i``) or aborted (``drop_i``).

    Event queue entries (from ``RXFifoEventMonitor``):
      * ``{"type": "axi_packet", "beats": [...]}``
      * ``{"type": "cancel"}``

    Algorithm: for each model packet, in order,
      * if ``dropped`` (test-side ``drop_i``): skip; no event consumed.
      * else: pop one event:
          - ``cancel`` -> DUT reverted this commit (fifo_full); skip.
          - ``axi_packet`` -> beats must match.
    Any leftover events after the model queue is drained are an error.
    """

    async def check(self, expected_queue, actual_queue):
        events: Deque[Dict[str, Any]] = deque()
        while not actual_queue.empty():
            events.append(await actual_queue.get())

        idx = 0
        while not expected_queue.empty():
            model_pkt = await expected_queue.get()
            idx += 1

            if model_pkt["dropped"]:
                # Aborted by drop_i; nothing should appear on either AXI or
                # cancel-event side for this packet.
                continue

            if not events:
                msg = (
                    f"Model packet {idx} expected an output event but the "
                    f"event queue is empty: beats={model_pkt['beats']}"
                )
                if self.fatal:
                    raise RuntimeError(msg)
                print(f"[WARNING] {msg}")
                return

            event = events.popleft()
            event_type = event.get("type")

            if event_type == "cancel":
                # DUT reverted this commit. No data check possible.
                continue

            if event_type == "axi_packet":
                if event["beats"] != model_pkt["beats"]:
                    msg = (
                        f"Packet {idx} mismatch:\n"
                        f"  model   = {model_pkt['beats']}\n"
                        f"  monitor = {event['beats']}"
                    )
                    if self.fatal:
                        raise RuntimeError(msg)
                    print(f"[WARNING] {msg}")
                continue

            msg = f"Unknown event type at packet {idx}: {event}"
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")

        if events:
            msg = f"Unconsumed events after model drained: {list(events)}"
            if self.fatal:
                raise RuntimeError(msg)
            print(f"[WARNING] {msg}")
