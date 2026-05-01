import cocotb
from cocotb.queue import Queue
from cocotb.triggers import ReadOnly, RisingEdge


class RXFifoEventMonitor:
    """Combined AXI-output / cancel-event monitor.

    Exposes a single queue, ``actual_queue``, that interleaves two kinds of
    entries in the order they occur in simulation time:

      * ``{"type": "axi_packet", "beats": [b0, b1, ...]}`` -- one entry per
        AXI-stream packet (i.e. when a 256-bit row with ``last=1`` finishes
        handshaking on ``m_axi``). The 256-bit row is split back into the
        per-input-beat 64-bit lanes that contributed to it (lanes whose mask
        byte is zero are stale buffer contents and are skipped).

      * ``{"type": "cancel"}`` -- one entry per ``send_i`` cycle on which the
        DUT reverts the would-be commit (``cancel_o`` high while
        ``send_i && valid_i && !drop_i``). Cancels caused by ``drop_i``
        mid-packet are *not* emitted here; the model already records those
        as dropped packets via its notification path.
    """

    DATA_IN_W = 64
    IN_MASK_W = 8
    OUT_BEATS = 4

    def __init__(self, dut, output_transaction=None):
        self.dut = dut
        self.actual_queue = Queue()
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
                await self.actual_queue.put(
                    {"type": "axi_packet", "beats": current_beats}
                )
                current_beats = []

    async def _cancel_observer(self):
        while True:
            await RisingEdge(self.dut.s_clk)
            await ReadOnly()

            send_i = bool(self._to_int(self.dut.send_i))
            valid_i = bool(self._to_int(self.dut.valid_i))
            drop_i = bool(self._to_int(self.dut.drop_i))
            cancel_o = bool(self._to_int(self.dut.cancel_o))

            if send_i and valid_i and not drop_i and cancel_o:
                await self.actual_queue.put({"type": "cancel"})
