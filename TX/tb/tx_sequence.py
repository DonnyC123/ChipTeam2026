from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from TX.tb.tx_axis_driver import TxAxisDriver
from TX.tb.tx_sequence_item import TxSequenceItem


class TxSequence(GenericSequence[TxSequenceItem]):
    DMA_DATA_W = TxSequenceItem.DMA_DATA_W
    DMA_KEEP_W = TxSequenceItem.DMA_KEEP_W
    QID_W = TxSequenceItem.QID_W

    def __init__(self, dut=None, driver: TxAxisDriver | None = None):
        if driver is None:
            if dut is None:
                raise ValueError("TxSequence requires either a dut or a driver")
            driver = TxAxisDriver(dut, TxSequenceItem)

        self.dut = dut if dut is not None else driver.dut
        super().__init__(driver)

    @property
    def backpressure_wait_cycles(self) -> int:
        return self.driver.backpressure_wait_cycles

    async def add_transaction(self, transaction: TxSequenceItem) -> int:
        await self.notify_subscribers(transaction)
        return await self.driver.send(transaction)

    @staticmethod
    def frame_to_dma_words(frame: list[int]) -> list[tuple[int, int, int]]:
        if not frame:
            raise ValueError("TX frame must contain at least one byte")

        words = []
        for offset in range(0, len(frame), 32):
            chunk = frame[offset : offset + 32]
            is_last = offset + 32 >= len(frame)
            data = int.from_bytes(bytes(chunk + [0] * (32 - len(chunk))), "little")
            keep = (1 << len(chunk)) - 1
            words.append((data, keep, 1 if is_last else 0))
        return words

    def _build_word_item(self, data: int, keep: int, last: int, tdest: int) -> TxSequenceItem:
        return TxSequenceItem(
            s_axis_dma_tdata_i=LogicArray.from_unsigned(data, self.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray.from_unsigned(keep, self.DMA_KEEP_W),
            s_axis_dma_tvalid_i=Logic(1),
            s_axis_dma_tlast_i=Logic(1 if last else 0),
            s_axis_dma_tdest_i=TxSequenceItem.tdest_value(tdest),
        )

    def _build_idle_item(self, tdest: int = 0) -> TxSequenceItem:
        return TxSequenceItem(
            s_axis_dma_tdata_i=LogicArray(0, self.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, self.DMA_KEEP_W),
            s_axis_dma_tvalid_i=Logic(0),
            s_axis_dma_tlast_i=Logic(0),
            s_axis_dma_tdest_i=TxSequenceItem.tdest_value(tdest),
        )

    async def add_idle(self, cycles: int = 1, tdest: int = 0):
        await self.driver.add_idle(cycles, tdest=tdest)

    async def add_dma_axis_word(self, data: int, keep: int, last: int, tdest: int = 0) -> int:
        tx = self._build_word_item(data, keep, last, tdest)
        return await self.add_transaction(tx)

    async def send_frame(self, frame: list[int], tdest: int = 0, inter_word_gap: int = 0) -> int:
        wait_cycles = 0
        for data, keep, last in self.frame_to_dma_words(frame):
            wait_cycles += await self.add_dma_axis_word(data, keep, last, tdest)
            if inter_word_gap:
                await self.add_idle(inter_word_gap, tdest=tdest)
        return wait_cycles

    async def send_frame_with_gaps(
        self, frame: list[int], gaps: list[int], tdest: int = 0
    ) -> int:
        wait_cycles = 0
        words = self.frame_to_dma_words(frame)
        for idx, (data, keep, last) in enumerate(words):
            wait_cycles += await self.add_dma_axis_word(data, keep, last, tdest)
            if idx < len(words) - 1 and idx < len(gaps) and gaps[idx]:
                await self.add_idle(gaps[idx], tdest=tdest)
        return wait_cycles
