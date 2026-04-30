from cocotb.triggers import RisingEdge, Timer

from TX.tb.tx_sequence_item import TxSequenceItem


class TxAxisDriver:
    """Ready-aware DMA AXIS driver for the TX full-chain wrapper.

    This intentionally does not use tb_utils.GenericDriver's queued loop: AXIS
    sources must hold payload stable until tready is sampled high at a clock edge.
    The public methods mirror the generic driver shape used by tb_utils tests.
    """

    def __init__(self, dut, seq_item_type=TxSequenceItem):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.backpressure_wait_cycles = 0
        self.accepted_words = 0

    async def send(self, transaction: TxSequenceItem) -> int:
        if not transaction.valid:
            self._drive_item(transaction)
            await RisingEdge(self.dut.clk)
            return 0

        wait_cycles = 0
        self._drive_item(transaction)

        while True:
            ready_now = await self._sample_ready_before_edge()
            await RisingEdge(self.dut.clk)

            if ready_now:
                break
            wait_cycles += 1

        self.backpressure_wait_cycles += wait_cycles
        self.accepted_words += 1
        return wait_cycles

    async def add_idle(self, cycles: int = 1, tdest: int = 0):
        idle = self.seq_item_type.invalid_seq_item()
        idle.s_axis_dma_tdest_i = self.seq_item_type.tdest_value(tdest)
        for _ in range(cycles):
            await self.send(idle)

    async def busy(self) -> bool:
        return False

    async def wait_until_idle(self):
        return

    def _drive_item(self, item: TxSequenceItem):
        self.dut.s_axis_dma_tdata_i.value = item.s_axis_dma_tdata_i
        self.dut.s_axis_dma_tkeep_i.value = item.s_axis_dma_tkeep_i
        self.dut.s_axis_dma_tvalid_i.value = item.s_axis_dma_tvalid_i
        self.dut.s_axis_dma_tlast_i.value = item.s_axis_dma_tlast_i
        self.dut.s_axis_dma_tdest_i.value = item.s_axis_dma_tdest_i

    async def _sample_ready_before_edge(self) -> int:
        await Timer(1, unit="ns")
        try:
            return int(self.dut.s_axis_dma_tready_o.value)
        except (TypeError, ValueError):
            return 0
