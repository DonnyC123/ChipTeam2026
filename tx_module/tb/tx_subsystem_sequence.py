from cocotb.triggers import RisingEdge
from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from tx_subsystem_sequence_item import TxSubsystemSequenceItem


class TxSubsystemSequence(GenericSequence):
    DMA_DATA_W = TxSubsystemSequenceItem.DMA_DATA_W
    DMA_VALID_W = TxSubsystemSequenceItem.DMA_VALID_W
    NUM_QUEUES = TxSubsystemSequenceItem.NUM_QUEUES
    QID_W = TxSubsystemSequenceItem.QID_W

    def _build_word_item(
        self,
        data: int,
        keep: int,
        last: int,
        tdest: int,
        m_axis_tready: int,
    ) -> TxSubsystemSequenceItem:
        return TxSubsystemSequenceItem(
            s_axis_dma_tdata_i=LogicArray.from_unsigned(data, self.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray.from_unsigned(keep, self.DMA_VALID_W),
            s_axis_dma_tvalid_i=Logic("1"),
            s_axis_dma_tlast_i=Logic("1" if last else "0"),
            s_axis_dma_tdest_i=LogicArray.from_unsigned(tdest, self.QID_W),
            m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
        )

    def _build_idle_item(self, tdest: int, m_axis_tready: int) -> TxSubsystemSequenceItem:
        return TxSubsystemSequenceItem(
            s_axis_dma_tdata_i=LogicArray(0, self.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, self.DMA_VALID_W),
            s_axis_dma_tvalid_i=Logic("0"),
            s_axis_dma_tlast_i=Logic("0"),
            s_axis_dma_tdest_i=LogicArray.from_unsigned(tdest, self.QID_W),
            m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
        )

    async def add_dma_axis_word(
        self,
        data: int,
        keep: int = 0xFFFF_FFFF,
        last: int = 0,
        tdest: int = 0,
        m_axis_tready: int = 1,
        notify_expected: bool = True,
    ):
        tx = self._build_word_item(data, keep, last, tdest, m_axis_tready)

        # For scoreboard-driven traffic, wait until ingress is ready, then send one beat.
        # This keeps AXIS semantics clean and avoids optimistic model accounting.
        if notify_expected:
            while True:
                try:
                    ready_now = int(self.driver.dut.s_axis_dma_tready_o.value)
                except (TypeError, ValueError):
                    ready_now = 0
                if ready_now:
                    break
                await self.add_transaction(self._build_idle_item(tdest, m_axis_tready))
                await RisingEdge(self.driver.dut.clk)

            await self.add_transaction(tx)
            await RisingEdge(self.driver.dut.clk)

            # We only launch when ingress tready is observed high.
            # Under this sequence contract, the launched beat is counted as accepted.
            await self.notify_subscribers(
                {
                    "data": data,
                    "keep": keep,
                    "last": last,
                    "tdest": tdest,
                }
            )
            return

        # Fire-and-forget mode for stress/backpressure tests that intentionally overdrive ingress.
        await self.add_transaction(tx)

    async def add_idle(
        self,
        cycles: int = 1,
        tdest: int = 0,
        m_axis_tready: int = 1,
    ):
        for _ in range(cycles):
            await self.add_transaction(self._build_idle_item(tdest, m_axis_tready))
