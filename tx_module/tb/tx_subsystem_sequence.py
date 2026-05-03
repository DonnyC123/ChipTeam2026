from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from tx_subsystem_sequence_item import TxSubsystemSequenceItem


class TxSubsystemSequence(GenericSequence):
    DMA_DATA_W = TxSubsystemSequenceItem.DMA_DATA_W
    DMA_KEEP_W = TxSubsystemSequenceItem.DMA_KEEP_W

    def _build_word_item(self, data: int, keep: int, last: int) -> TxSubsystemSequenceItem:
        return TxSubsystemSequenceItem(
            s_axis_dma_tdata_i=LogicArray.from_unsigned(data, self.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray.from_unsigned(keep, self.DMA_KEEP_W),
            s_axis_dma_tvalid_i=Logic(1),
            s_axis_dma_tlast_i=Logic(1 if last else 0),
        )

    async def add_dma_axis_word(
        self,
        data: int,
        keep: int = 0xFFFF_FFFF,
        last: int = 0,
        notify_expected: bool = True,
    ):
        item = self._build_word_item(data, keep, last)
        await self.add_transaction(item)
        if notify_expected:
            await self.notify_subscribers({"data": data, "keep": keep, "last": last})

    async def add_packet(self, words):
        for idx, word in enumerate(words):
            data, keep = word
            await self.add_dma_axis_word(
                data=data,
                keep=keep,
                last=(idx == len(words) - 1),
            )

    async def add_idle(self, cycles: int = 1):
        await self.driver.add_idle(cycles)
