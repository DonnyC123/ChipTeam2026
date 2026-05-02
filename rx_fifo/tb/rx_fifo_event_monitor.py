from typing import List

from tb_utils.generic_monitor import GenericMonitor, GenericValidMonitor

from rx_fifo.tb.rx_fifo_output_transaction import (
    RXFifoCancelEventTransaction,
    RXFifoOutputTransaction,
)


class _CancelEventObserver(GenericValidMonitor[RXFifoCancelEventTransaction]):
    def __init__(self, dut):
        super().__init__(dut, RXFifoCancelEventTransaction, clk=dut.s_clk)


class RXFifoEventMonitor(GenericMonitor[RXFifoOutputTransaction]):
    DATA_IN_W = 64
    IN_MASK_W = 8
    OUT_BEATS = 4

    def __init__(self, dut, output_transaction=RXFifoOutputTransaction):
        super().__init__(dut, output_transaction, clk=dut.m_clk)
        self._cancel_observer = _CancelEventObserver(dut)
        self.cancel_queue = self._cancel_observer.actual_queue

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    async def monitor_loop(self):
        data_lane_mask = (1 << self.DATA_IN_W) - 1
        mask_lane_mask = (1 << self.IN_MASK_W) - 1
        current_beats: List[int] = []

        while True:
            txn = await self.receive_transaction()

            valid = bool(self._to_int(txn.m_axi.valid))
            ready = bool(self._to_int(txn.m_axi.ready))
            if not (valid and ready):
                continue

            data = self._to_int(txn.m_axi.data)
            mask = self._to_int(txn.m_axi.mask)
            row_last = bool(self._to_int(txn.m_axi.last))

            for slot in range(self.OUT_BEATS):
                slot_mask = (mask >> (slot * self.IN_MASK_W)) & mask_lane_mask
                if slot_mask == 0:
                    continue
                slot_data = (data >> (slot * self.DATA_IN_W)) & data_lane_mask
                current_beats.append(slot_data)

            if row_last and current_beats:
                await self.actual_queue.put({"beats": current_beats})
                current_beats = []
