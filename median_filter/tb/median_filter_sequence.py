from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem


class MedianFilterSequence(GenericSequence):
    async def add_pixel(self, r: int, g: int, b: int):
        await self.notify_subscribers({"event": "pixel", "r": r, "g": g, "b": b})
        await self.add_transaction(
            MedianFilterSequenceItem(
                start_i=Logic(0),
                valid_i=Logic(1),
                red_i=LogicArray.from_unsigned(r, MedianFilterSequenceItem.PIXEL_W),
                green_i=LogicArray.from_unsigned(g, MedianFilterSequenceItem.PIXEL_W),
                blue_i=LogicArray.from_unsigned(b, MedianFilterSequenceItem.PIXEL_W),
            )
        )

    async def add_start_pulse(self):
        await self.add_transaction(
            MedianFilterSequenceItem(
                start_i=Logic(1),
                valid_i=Logic(0),
                red_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
                green_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
                blue_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
            )
        )

    async def add_bubble(self, cycles=1):
        for _ in range(cycles):
            await self.add_transaction(
                MedianFilterSequenceItem(
                    start_i=Logic(0),
                    valid_i=Logic(0),
                    red_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
                    green_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
                    blue_i=LogicArray("0"*MedianFilterSequenceItem.PIXEL_W),
                )
            )

    async def add_image_raster(self, image):
        await self.notify_subscribers({"event": "image_begin"})
        for row in image:
            for (r, g, b) in row:
                await self.add_pixel(r, g, b)
        await self.notify_subscribers({"event": "image_end"})