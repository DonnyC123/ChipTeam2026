from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem

PIXEL_W = 8  # should match PixelStruct PIXEL_W in pixel_interface_transaction.py


class MedianFilterSequence(GenericSequence):
    async def add_start_pulse(self):
        # Drive DUT start pulse for 1 cycle, no valid pixel
        item = MedianFilterSequenceItem()
        item.start_i = Logic(1)
        item.pixel_valid_if_i.valid = Logic(0)

        # drive zeros (optional but nice)
        item.pixel_valid_if_i.pixel.red   = LogicArray.from_unsigned(0, PIXEL_W)
        item.pixel_valid_if_i.pixel.green = LogicArray.from_unsigned(0, PIXEL_W)
        item.pixel_valid_if_i.pixel.blue  = LogicArray.from_unsigned(0, PIXEL_W)

        await self.add_transaction(item)

        # Notify the model to reset its internal row/col
        await self.notify_subscribers({"event": "start"})

    async def add_pixel(self, r: int, g: int, b: int):
        # Notify the model that one pixel-time has elapsed
        await self.notify_subscribers({"event": "pixel"})

        item = MedianFilterSequenceItem()
        item.start_i = Logic(0)
        item.pixel_valid_if_i.valid = Logic(1)
        item.pixel_valid_if_i.pixel.red   = LogicArray.from_unsigned(r, PIXEL_W)
        item.pixel_valid_if_i.pixel.green = LogicArray.from_unsigned(g, PIXEL_W)
        item.pixel_valid_if_i.pixel.blue  = LogicArray.from_unsigned(b, PIXEL_W)

        await self.add_transaction(item)

    async def add_bubble(self, cycles: int = 1):
        for _ in range(cycles):
            item = MedianFilterSequenceItem.invalid_seq_item()

            # optionally drive zeros instead of X for cleanliness
            item.pixel_valid_if_i.pixel.red   = LogicArray.from_unsigned(0, PIXEL_W)
            item.pixel_valid_if_i.pixel.green = LogicArray.from_unsigned(0, PIXEL_W)
            item.pixel_valid_if_i.pixel.blue  = LogicArray.from_unsigned(0, PIXEL_W)

            await self.add_transaction(item)

    async def add_image_raster(self, image):
        # Start-of-frame
        await self.add_start_pulse()

        # Stream pixels raster order
        for row in image:
            for (r, g, b) in row:
                await self.add_pixel(r, g, b)
