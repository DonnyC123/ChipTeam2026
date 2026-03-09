from tb_utils.generic_model import GenericModel


class TxSchedulingModel(GenericModel):
    """N-queue round-robin scheduler reference model.

    Mirrors the RTL FSM with parameterized round-robin arbitration.
    Emits expected tuples: (queue_sel, dma_read_en).
    Each expected item corresponds to a cycle where fifo_req_o should be high.
    """

    def __init__(self, num_queues: int = 2):
        super().__init__()
        self.num_queues = num_queues
        self.state = "IDLE"
        self.last_served = num_queues - 1
        self.queue_sel = 0

    def _rr_next(self, q_valid: int):
        """Round-robin scan from last_served+1, return (found, queue_id)."""
        for i in range(self.num_queues):
            cand = (self.last_served + 1 + i) % self.num_queues
            if q_valid & (1 << cand):
                return True, cand
        return False, 0

    async def process_notification(self, notification):
        q_valid = notification.get("q_valid", 0)
        q_last = notification.get("q_last", 0)
        fifo_full = notification.get("fifo_full", False)
        fifo_grant = notification.get("fifo_grant", True)

        if self.state == "IDLE":
            if not fifo_full:
                found, nxt = self._rr_next(q_valid)
                if found:
                    read_en = 1 if fifo_grant else 0
                    await self.expected_queue.put((nxt, read_en))

                    if fifo_grant:
                        is_last = bool(q_last & (1 << nxt))
                        if is_last:
                            self.last_served = nxt
                        else:
                            self.queue_sel = nxt
                            self.state = "SERVING"

        elif self.state == "SERVING":
            q = self.queue_sel
            if not fifo_full and (q_valid & (1 << q)):
                read_en = 1 if fifo_grant else 0
                await self.expected_queue.put((q, read_en))

                if fifo_grant and (q_last & (1 << q)):
                    self.state = "IDLE"
                    self.last_served = q