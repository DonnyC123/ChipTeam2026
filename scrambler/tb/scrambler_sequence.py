from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem
from tb_utils.generic_sequence import GenericSequence

from cocotb.types import Logic, LogicArray

from PIL import Image


class MedianFilterSequence(GenericSequence):
    async def median_filter_op(self, multiplier: int, multiplicand: int):
        img = Image.open('test.png')
        img = img.convert('RGB')
        width, height = img.size
        pixels = img.load()
        await self.notify_subscribers(
            {
                "start_i": 1,
            }
        )
        await self.add_transaction(
            MedianFilterSequenceItem(
                a_operand_i=LogicArray.from_unsigned(
                    
                )
            )
        )


        for y in range(height):
            for x in range(width):
                # Extract the RGB values
                await self.add_transaction(
                    r, g, b = pixels[x, y]
                )
                # Example processing: 
                # print(f"Pixel at ({x}, {y}): Red={r}, Green={g}, Blue={b}")       
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

    async def add_random_median_op(self, multiplier: int, multiplicand: int):
        pass

