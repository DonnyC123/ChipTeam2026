from itertools import count
from tb_utils.generic_sequence import GenericSequence
from scrambler.tb.scrambler_sequence_item import ScramblerSequenceItem
import random

class ScramblerSequence(GenericSequence):
    SCRAMBLER_STATE_W = 58
    SCRAMBLER_TAP_1   = 19
    SCRAMBLER_TAP_2   = 0

    def __init__(self, driver):
        super().__init__(driver)
        self.scrambler_state = (1 << self.SCRAMBLER_STATE_W) - 1

    def set_state(self, state: int):
        self.scrambler_state = state & ((1 << self.SCRAMBLER_STATE_W) - 1)

    def scramble_66b(self, input_word: int, header: int = 0b01) -> int:
            """
            Scrambles 64 bits and prepends the 2-bit header to form a 66-bit word.
            """
            scrambled_64b = 0
            state = self.scrambler_state
            
            # Standard Ethernet Scrambling Loop
            for i in range(64):
                in_bit   = (input_word >> i) & 1
                feedback = ((state >> self.SCRAMBLER_TAP_1) ^ (state >> self.SCRAMBLER_TAP_2)) & 1
                out_bit  = in_bit ^ feedback
                scrambled_64b |= (out_bit << i)
                state    = ((state << 1) | out_bit) & ((1 << self.SCRAMBLER_STATE_W) - 1)
            
            self.scrambler_state = state
            
            full_word_66b = (header << 64) | scrambled_64b
            return full_word_66b

    async def send_word(self, data: int, header: int = 0b01, valid: bool = True):
        """
        Send a single 64b data word and 2b header to the scrambler DUT.
        """
        item = ScramblerSequenceItem(
            x_64b_i       = data,
            valid_i       = valid,
            x_2b_header_i = header
        )
        item.header = header
        await self.add_transaction(item)

    async def send_words(self, data_list, header: int = 0b01):
        for data in data_list:
            await self.send_word(data, header=header)

    async def send_random(self, n: int, header: int = 0b01):
        for _ in range(n):
            await self.send_word(random.getrandbits(64), header=header)