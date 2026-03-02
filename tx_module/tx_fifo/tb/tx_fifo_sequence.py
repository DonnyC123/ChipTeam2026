from cocotb.types import Logic, LogicArray

from tx_fifo.tb.tx_fifo_sequence_item import TxFifoSequenceItem
from tb_utils.generic_sequence import GenericSequence

DMA_DATA_W = TxFifoSequenceItem.DMA_DATA_W
DMA_VALID_W = TxFifoSequenceItem.DMA_VALID_W


class TxFifoSequence(GenericSequence):

    async def add_write(self, data: int, valid_mask: int = 0xFFFF_FFFF):
        """Write one 256-bit word into the FIFO and notify model."""
        await self.notify_subscribers({"data": data, "valid": valid_mask})
        await self.add_transaction(
            TxFifoSequenceItem(
                dma_data_i=LogicArray.from_unsigned(data, DMA_DATA_W),
                dma_valid_i=LogicArray.from_unsigned(valid_mask, DMA_VALID_W),
                dma_wr_en_i=Logic("1"),
                pcs_read_i=Logic("0"),
                sched_req_i=Logic("1"),
            )
        )

    async def add_read(self):
        """Read one 64-bit beat from the FIFO (no model notification)."""
        await self.add_transaction(
            TxFifoSequenceItem(
                dma_data_i=LogicArray(0, DMA_DATA_W),
                dma_valid_i=LogicArray(0, DMA_VALID_W),
                dma_wr_en_i=Logic("0"),
                pcs_read_i=Logic("1"),
                sched_req_i=Logic("0"),
            )
        )

    async def add_idle(self):
        """Drive one idle cycle (no write, no read)."""
        await self.add_transaction(TxFifoSequenceItem.invalid_seq_item())

    async def add_write_and_readout(self, data: int, valid_mask: int = 0xFFFF_FFFF):
        """Write one 256-bit word, then read all 4 PCS beats."""
        await self.add_write(data, valid_mask)
        for _ in range(4):
            await self.add_read()

    async def add_burst_write_then_read(
        self, words: list[int], valid_mask: int = 0xFFFF_FFFF
    ):
        """Write multiple 256-bit words, then read all beats out."""
        for w in words:
            await self.add_write(w, valid_mask)
        for _ in range(len(words) * 4):
            await self.add_read()
