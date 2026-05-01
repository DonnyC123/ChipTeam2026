import cocotb
from cocotb.queue import Queue
from cocotb.triggers import ReadOnly, RisingEdge


class RXFifoEventMonitor:
    """Two queues: ``actual_queue`` for AXI output packets,
    ``cancel_queue`` for ``cancel_o`` events.

    AXI queue entries: ``{"beats": [d0, d1, ...]}`` -- the per-input-beat
    64-bit values reconstructed from each 256-bit row that handshakes on
    ``m_axi`` with ``last=1`` (lanes whose mask byte is zero are skipped as
    stale buffer contents).

    Cancel queue entries: ``{}`` -- one entry per ``s_clk`` cycle on which
    ``cancel_o`` pulses high while ``valid_i && !drop_i``. Once the driver
    enters dropping mode it suppresses ``valid_i`` for the rest of the
    packet, so this gives one entry per packet-level revert. Cancels caused
    by ``drop_i`` are not emitted here -- the model already records those
    as dropped packets via its notification path.
    """

    DATA_IN_W = 64
    IN_MASK_W = 8
    OUT_BEATS = 4

    def __init__(self, dut, output_transaction=None):
        self.dut = dut
        self.actual_queue = Queue()
        self.cancel_queue = Queue()
        cocotb.start_soon(self._axi_observer())
        cocotb.start_soon(self._cancel_observer())

    @staticmethod
    def _to_int(signal, default: int = 0) -> int:
        try:
            return int(signal.value)
        except (ValueError, AttributeError, TypeError):
            return default

    async def _axi_observer(self):
        data_lane_mask = (1 << self.DATA_IN_W) - 1
        mask_lane_mask = (1 << self.IN_MASK_W) - 1
        current_beats = []

        while True:
            await RisingEdge(self.dut.m_clk)
            await ReadOnly()

            valid = bool(self._to_int(self.dut.m_axi.valid))
            ready = bool(self._to_int(self.dut.m_axi.ready))
            if not (valid and ready):
                continue

            data = self._to_int(self.dut.m_axi.data)
            mask = self._to_int(self.dut.m_axi.mask)
            row_last = bool(self._to_int(self.dut.m_axi.last))

            for slot in range(self.OUT_BEATS):
                slot_mask = (mask >> (slot * self.IN_MASK_W)) & mask_lane_mask
                if slot_mask == 0:
                    continue
                slot_data = (data >> (slot * self.DATA_IN_W)) & data_lane_mask
                current_beats.append(slot_data)

            if row_last and current_beats:
                await self.actual_queue.put({"beats": current_beats})
                current_beats = []

    async def _cancel_observer(self):
        while True:
            await RisingEdge(self.dut.s_clk)
            await ReadOnly()

            valid_i = bool(self._to_int(self.dut.valid_i))
            drop_i = bool(self._to_int(self.dut.drop_i))
            cancel_o = bool(self._to_int(self.dut.cancel_o))

            if valid_i and not drop_i and cancel_o:
                await self.cancel_queue.put({})
