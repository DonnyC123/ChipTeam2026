from cocotb.types import Logic, LogicArray

from tb.tx_subsystem_sequence_item import TxSubsystemSequenceItem
from tb_utils.generic_sequence import GenericSequence


class TxSubsystemSequence(GenericSequence):
    DMA_DATA_W = TxSubsystemSequenceItem.DMA_DATA_W
    DMA_VALID_W = TxSubsystemSequenceItem.DMA_VALID_W
    NUM_QUEUES = TxSubsystemSequenceItem.NUM_QUEUES

    async def add_dma_axis_word(
        self,
        data: int,
        keep: int = 0xFFFF_FFFF,
        last: int = 0,
        q_valid: int = 0,
        q_last: int = 0,
        dma_req_ready: int = 1,
        m_axis_tready: int = 1,
    ):
        await self.notify_subscribers(
            {
                "op": "axis_write",
                "data": data,
                "keep": keep,
                "last": last,
            }
        )
        await self.add_transaction(
            TxSubsystemSequenceItem(
                q_valid_i=LogicArray.from_unsigned(q_valid, self.NUM_QUEUES),
                q_last_i=LogicArray.from_unsigned(q_last, self.NUM_QUEUES),
                s_axis_dma_tdata_i=LogicArray.from_unsigned(data, self.DMA_DATA_W),
                s_axis_dma_tkeep_i=LogicArray.from_unsigned(keep, self.DMA_VALID_W),
                s_axis_dma_tvalid_i=Logic("1"),
                s_axis_dma_tlast_i=Logic("1" if last else "0"),
                dma_req_ready_i=Logic("1" if dma_req_ready else "0"),
                m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
            )
        )

    async def add_idle(
        self,
        cycles: int = 1,
        q_valid: int = 0,
        q_last: int = 0,
        dma_req_ready: int = 1,
        m_axis_tready: int = 1,
    ):
        for _ in range(cycles):
            await self.add_transaction(
                TxSubsystemSequenceItem(
                    q_valid_i=LogicArray.from_unsigned(q_valid, self.NUM_QUEUES),
                    q_last_i=LogicArray.from_unsigned(q_last, self.NUM_QUEUES),
                    s_axis_dma_tdata_i=LogicArray(0, self.DMA_DATA_W),
                    s_axis_dma_tkeep_i=LogicArray(0, self.DMA_VALID_W),
                    s_axis_dma_tvalid_i=Logic("0"),
                    s_axis_dma_tlast_i=Logic("0"),
                    dma_req_ready_i=Logic("1" if dma_req_ready else "0"),
                    m_axis_tready_i=Logic("1" if m_axis_tready else "0"),
                )
            )
