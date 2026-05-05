from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from alignment_finder.tb.alignment_finder_sequence_item import AlignmentFinderSequenceItem

DATA_W = 66 

class AlignmentFinderSequence(GenericSequence):
    async def add_word(self, word: int, *, valid: bool = True):
        item = AlignmentFinderSequenceItem()
        item.data_valid_i = Logic(1 if valid else 0)
        item.data_i = LogicArray.from_unsigned(int(word), DATA_W)

        await self.add_transaction(item)  

        await self.notify_subscribers({ 
            "event": "cycle",
            "data_valid": 1 if valid else 0,
            "data": int(word),
        })

    async def add_bubble(self, cycles: int = 1):
        for _ in range(cycles):
            await self.notify_subscribers({
                "event": "bubble", 
                "data_valid": 0,
                "data": 0,
            })

            item = AlignmentFinderSequenceItem.invalid_seq_item()
            item.data_i = LogicArray.from_unsigned(0, DATA_W)
            await self.add_transaction(item)

    async def add_reset(self, cycles: int = 1):
        for _ in range(cycles):
            await self.notify_subscribers({"event": "reset"})
            await self.add_bubble(1)

    @staticmethod
    def make_66b_block(header2: int, payload64: int) -> int:
        header2 &= 0b11
        payload64 &= (1 << 64) - 1
        return (payload64 << 2) | header2

    async def add_control_idle_stream(self, blocks: int, *, valid: bool = True):
        for _ in range(blocks):
            w = self.make_66b_block(0b10, 0)
            await self.add_word(w, valid=valid)

    async def add_prbs_words(self, blocks: int, seed: int = 0xACE1, *, valid: bool = True):
        lfsr = seed & 0xFFFF
        for _ in range(blocks):
            word = 0
            for i in range(DATA_W):
                bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
                lfsr = ((lfsr >> 1) | (bit << 15)) & 0xFFFF
                word |= (lfsr & 1) << i
            await self.add_word(word, valid=valid)

    async def add_misaligned_then_lock(self, pre_bits: int = 5, lock_blocks: int = 64):
        await self.add_prbs_words(pre_bits, valid=True)
        await self.add_control_idle_stream(lock_blocks, valid=True)

    async def add_bad_header_stream(self, blocks: int, *, valid: bool = True):
        bad_headers = (0b00, 0b11)

        for i in range(blocks):
            hdr = bad_headers[i % 2] 
            payload = 0  
            w = self.make_66b_block(hdr, payload)
            await self.add_word(w, valid=valid)
