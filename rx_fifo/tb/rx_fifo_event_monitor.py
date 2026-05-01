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

      * ``{"type": "cancel"}`` -- one entry per packet-level revert. A
        revert fires whenever ``valid_i && !drop_i && cancel_o`` -- i.e.
        ``fifo_full`` is asserted on any beat of a packet (not only on the
        ``send_i`` beat). Once that happens the driver suppresses ``valid_i``
        for the remainder of the packet, so ``cancel_o`` cannot reassert
        until a fresh packet starts; we therefore get one cancel per dropped
        packet. Cancels caused by ``drop_i`` mid-packet are *not* emitted
        here; the model already records those as dropped packets via its
        notification path.
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
        handshake_count = 0
        packet_count = 0

        while True:
            await RisingEdge(self.dut.m_clk)
            await ReadOnly()

            valid = bool(self._to_int(self.dut.m_axi.valid))
            ready = bool(self._to_int(self.dut.m_axi.ready))
            if not (valid and ready):
                continue

            handshake_count += 1
            data = self._to_int(self.dut.m_axi.data)
            mask = self._to_int(self.dut.m_axi.mask)
            row_last = bool(self._to_int(self.dut.m_axi.last))
            self.dut._log.info(
                f"[event_mon AXI] handshake#{handshake_count} mask=0x{mask:08x} last={row_last}"
            )

            for slot in range(self.OUT_BEATS):
                slot_mask = (mask >> (slot * self.IN_MASK_W)) & mask_lane_mask
                if slot_mask == 0:
                    continue
                slot_data = (data >> (slot * self.DATA_IN_W)) & data_lane_mask
                current_beats.append(slot_data)

            if row_last and current_beats:
                packet_count += 1
                self.dut._log.info(
                    f"[event_mon AXI] packet#{packet_count} beats={len(current_beats)}"
                )
                await self.actual_queue.put(
                    {"type": "axi_packet", "beats": current_beats}
                )
                current_beats = []

    async def _cancel_observer(self):
        cancel_o_high_cycles = 0
        cancel_emit_count = 0
        while True:
            await RisingEdge(self.dut.s_clk)
            await ReadOnly()

            valid_i = bool(self._to_int(self.dut.valid_i))
            drop_i = bool(self._to_int(self.dut.drop_i))
            send_i = bool(self._to_int(self.dut.send_i))
            cancel_o = bool(self._to_int(self.dut.cancel_o))

            if cancel_o:
                cancel_o_high_cycles += 1
                self.dut._log.info(
                    f"[event_mon CANCEL] cancel_o high cycle#{cancel_o_high_cycles} "
                    f"valid_i={valid_i} drop_i={drop_i} send_i={send_i}"
                )

            if valid_i and not drop_i and cancel_o:
                cancel_emit_count += 1
                self.dut._log.info(
                    f"[event_mon CANCEL] EMIT cancel#{cancel_emit_count}"
                )
                await self.actual_queue.put({"type": "cancel"})
