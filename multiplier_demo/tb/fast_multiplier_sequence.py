from multiplier_demo.tb.fast_multiplier_sequence_item import FastMultiplierSequenceItem
from tb_utils.generic_sequence import GenericSequence

from cocotb.types import Logic, LogicArray


class FastMultiplierSequence(GenericSequence):
    async def add_multiplication_op(self, multiplier: int, multiplicand: int):
        await self.notify_subscribers(
            {
                "multiplier": multiplier,
                "multiplicand": multiplicand,
            }
        )
        await self.add_transaction(
            FastMultiplierSequenceItem(
                a_operand_i=LogicArray.from_unsigned(
                    multiplier, (FastMultiplierSequenceItem.DIN_W)
                ),
                b_operand_i=LogicArray.from_unsigned(
                    multiplicand, (FastMultiplierSequenceItem.DIN_W)
                ),
                operands_valid_i=Logic("1"),
            )
        )

    async def add_random_mult_op(self, multiplier: int, multiplicand: int):
        pass

