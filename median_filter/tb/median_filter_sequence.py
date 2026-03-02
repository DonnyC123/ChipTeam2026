from cocotb.types import Logic, LogicArray

from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem
from median_filter.tb.pixel_interface_transaction import (
    PIXEL_W,
    PixelInterfaceTransaction,
    PixelStruct,
)
from tb_utils.generic_sequence import GenericSequence


class MedianFilterSequence(GenericSequence):
    async def add_start(self):
        """Send one cycle with start_i=1, valid=0."""
        await self.add_transaction(
            MedianFilterSequenceItem(
                start_i=Logic("1"),
                pixel_valid_if_i=PixelInterfaceTransaction(valid=Logic("0")),
            )
        )

    async def add_pixel(self, r: int, g: int, b: int):
        """Send one pixel and notify model for scoreboard."""
        await self.notify_subscribers({"pixel": (r, g, b)})
        await self.add_transaction(
            MedianFilterSequenceItem(
                start_i=Logic("0"),
                pixel_valid_if_i=PixelInterfaceTransaction(
                    pixel=PixelStruct(
                        red=LogicArray(r, PIXEL_W),
                        green=LogicArray(g, PIXEL_W),
                        blue=LogicArray(b, PIXEL_W),
                    ),
                    valid=Logic("1"),
                ),
            )
        )

    async def add_image_frame(self, image_len: int, image_height: int, pixels):
        """
        Send start then stream pixels row by row.
        pixels: iterable of (r, g, b) of length image_len * image_height.
        """
        await self.add_start()
        for (r, g, b) in pixels:
            await self.add_pixel(r, g, b)
