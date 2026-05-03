from tb_utils.generic_monitor import GenericMonitor

from rx_fifo.tb.rx_fifo_output_transaction import RXFifoOutputTransaction


class RxEventMonitor(GenericMonitor[RXFifoOutputTransaction]):
    """Sample the rx_top_wrapper's `m_axi` interface on m_clk.

    For each accepted beat (valid && ready), use the byte mask to extract the
    valid bytes from data. On `last`, emit one packet `{"bytes": [...]}` to
    actual_queue."""

    DATA_W = 256
    MASK_W = DATA_W // 8

    def __init__(self, dut, output_transaction=RXFifoOutputTransaction):
        super().__init__(dut, output_transaction, clk=dut.m_clk)

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    async def monitor_loop(self):
        current_bytes: list[int] = []

        while True:
            txn = await self.receive_transaction()

            valid = bool(self._to_int(txn.m_axi.valid))
            ready = bool(self._to_int(txn.m_axi.ready))
            if not (valid and ready):
                continue

            data = self._to_int(txn.m_axi.data)
            mask = self._to_int(txn.m_axi.mask)
            last = bool(self._to_int(txn.m_axi.last))

            for byte_idx in range(self.MASK_W):
                if (mask >> byte_idx) & 1:
                    current_bytes.append((data >> (byte_idx * 8)) & 0xFF)

            if last and current_bytes:
                await self.actual_queue.put({"bytes": current_bytes})
                current_bytes = []
