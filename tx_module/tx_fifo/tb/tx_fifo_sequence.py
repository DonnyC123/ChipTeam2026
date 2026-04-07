from cocotb.types import Logic, LogicArray

from tx_fifo.tb.tx_fifo_sequence_item import TxFifoSequenceItem
from tb_utils.generic_sequence import GenericSequence

DMA_DATA_W = TxFifoSequenceItem.DMA_DATA_W
DMA_VALID_W = TxFifoSequenceItem.DMA_VALID_W


class TxFifoSequence(GenericSequence):

    async def add_cycle(
        self,
        write_en: bool = False,
        data: int = 0,
        valid_mask: int = 0,
        last: int = 0,
        read_en: bool = False,
        sched_req: bool | None = None,
    ):
        """Drive one FIFO cycle with optional write/read and notify model."""
        if sched_req is None:
            sched_req = write_en

        await self.notify_subscribers(
            {
                "op": "cycle",
                "write_en": bool(write_en),
                "data": data,
                "valid": valid_mask,
                "last": int(last),
                "read_en": bool(read_en),
            }
        )
        await self.add_transaction(
            TxFifoSequenceItem(
                dma_data_i=LogicArray.from_unsigned(data if write_en else 0, DMA_DATA_W),
                dma_valid_i=LogicArray.from_unsigned(valid_mask if write_en else 0, DMA_VALID_W),
                dma_last_i=Logic("1" if (write_en and last) else "0"),
                dma_wr_en_i=Logic("1" if write_en else "0"),
                pcs_read_i=Logic("1" if read_en else "0"),
                sched_req_i=Logic("1" if sched_req else "0"),
            )
        )

    async def add_write(self, data: int, valid_mask: int = 0xFFFF_FFFF, last: int = 0):
        """Write one 256-bit word into the FIFO and notify model."""
        await self.add_cycle(
            write_en=True,
            data=data,
            valid_mask=valid_mask,
            last=last,
            read_en=False,
            sched_req=True,
        )

    async def add_read(self):
        """Read one 64-bit beat from the FIFO and notify model."""
        await self.add_cycle(write_en=False, read_en=True, sched_req=False)

    async def add_idle(self):
        """Drive one idle cycle (no write, no read)."""
        await self.add_cycle(write_en=False, read_en=False, sched_req=False)

    async def add_write_and_readout(
        self, data: int, valid_mask: int = 0xFFFF_FFFF, last: int = 0
    ):
        """Write one 256-bit word, then read all 4 PCS beats."""
        await self.add_write(data, valid_mask, last)
        for _ in range(4):
            await self.add_read()

    async def add_burst_write_then_read(
        self, words: list[int], valid_mask: int = 0xFFFF_FFFF, last_idx: int | None = None
    ):
        """Write multiple 256-bit words, then read all beats out."""
        for idx, w in enumerate(words):
            is_last = int(last_idx is not None and idx == last_idx)
            await self.add_write(w, valid_mask, is_last)
        for _ in range(len(words) * 4):
            await self.add_read()
