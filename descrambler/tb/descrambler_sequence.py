from itertools import count
from tb_utils.generic_sequence import GenericSequence
from descrambler.tb.descrambler_sequence_item import descramblerSequenceItem
import random

class descramblerSequence(GenericSequence):
    descrambler_STATE_W = 58
    descrambler_TAP_1   = 19
    descrambler_TAP_2   = 0

    def __init__(self, driver):
        super().__init__(driver)
        self.descrambler_state = (1 << self.descrambler_STATE_W) - 1

    def set_state(self, state: int):
        self.descrambler_state = state & ((1 << self.descrambler_STATE_W) - 1)

    def descramble_64b(self, input_word: int) -> int:
            """
            Descrambles 64 bits.
            """
            descrambled_64b = 0
            state = self.descrambler_state
            
            # Standard Ethernet Scrambling Loop
            for i in range(64):
                in_bit   = (input_word >> i) & 1
                feedback = ((state >> self.descrambler_TAP_1) ^ (state >> self.descrambler_TAP_2)) & 1
                out_bit  = in_bit ^ feedback
                descrambled_64b |= (out_bit << i)
                state    = ((state << 1) | out_bit) & ((1 << self.descrambler_STATE_W) - 1)
            
            self.descrambler_state = state
            
            return descrambled_64b

    async def send_word(self, data: int, valid: bool = True):
        """
        Send a single 64b data word to the descrambler DUT.
        """
        item = descramblerSequenceItem(
            x_64b_i       = data,
            valid_i       = valid
        )
        await self.add_transaction(item)

    async def send_words(self, data_list):
        for data in data_list:
            await self.send_word(data)

    async def send_random(self, n: int):
        for _ in range(n):
            await self.send_word(random.getrandbits(64))