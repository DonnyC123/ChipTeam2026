from cocotb.types import Logic, LogicArray

from tb.tx_subsystem_sequence_item import TxSubsystemSequenceItem
from tb_utils.generic_sequence import GenericSequence


class TxSubsystemSequence(GenericSequence):
    DMA_DATA_W = TxSubsystemSequenceItem.DMA_DATA_W
    DMA_VALID_W = TxSubsystemSequenceItem.DMA_VALID_W
    NUM_QUEUES = TxSubsystemSequenceItem.NUM_QUEUES
    QID_W = TxSubsystemSequenceItem.QID_W

    async def add_dma_axis_word(
        self,
        data: int,
        keep: int = 0xFFFF_FFFF,
        last: int = 0,
        tdest: int = 0,
        m_axis_tready: int = 1,
        notify_expected: bool = True,
    ):
        if notify_expected:
            await self.notify_subscribers(
                {
                    "data": data,
                    "keep": keep,
                    "last": last,
                    "tdest": tdest,
                }
            )
        await self.add_transaction(
            TxSubsystemSequenceItem(
                s_axis_dma_tdata_i=LogicArray.from_unsigned(data, self.DMA_DATA_W),
                s_axis_dma_tkeep_i=LogicArray.from_unsigned(keep, self.DMA_VALID_W),
                s_axis_dma_tvalid_i=Logic("1"),
                s_axis_dma_tlast_i=Logic("1" if last else "0"),
                s_axis_dma_tdest_i=LogicArray.from_unsigned(tdest, self.QID_W),
                m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
            )
        )

    async def add_idle(
        self,
        cycles: int = 1,
        tdest: int = 0,
        m_axis_tready: int = 1,
    ):
        for _ in range(cycles):
            await self.add_transaction(
                TxSubsystemSequenceItem(
                    s_axis_dma_tdata_i=LogicArray(0, self.DMA_DATA_W),
                    s_axis_dma_tkeep_i=LogicArray(0, self.DMA_VALID_W),
                    s_axis_dma_tvalid_i=Logic("0"),
                    s_axis_dma_tlast_i=Logic("0"),
                    s_axis_dma_tdest_i=LogicArray.from_unsigned(tdest, self.QID_W),
                    m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
                )
            )
