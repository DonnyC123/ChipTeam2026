from scrambler.tb.scrambler_sequence_item import ScramblerSequenceItem
from tb_utils.generic_sequence import GenericSequence

from cocotb.types import Logic, LogicArray

from PIL import Image


class ScramblerSequence(GenericSequence):
    async def median_filter_op(self, multiplier: int, multiplicand: int):
        with open('data_in.txt', 'r') as file:
            data_in = file.read().splitlines()
        await self.notify_subscribers(
            {
                "start_i": 1,
            }
        )
        for i in data_in:
            await self.add_transaction(
                bit_stream = i
            )
         await self.add_transaction(
            ScramblerSequenceItem(
                a_operand_i=LogicArray.from_unsigned(
                    multiplier, (FastMultiplierSequenceItem.DIN_W)
                ),
                operands_valid_i=Logic("1"),
            )
        )

    async def add_random_median_op(self, multiplier: int, multiplicand: int):
        pass

