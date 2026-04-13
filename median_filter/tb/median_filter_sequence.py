import random

from .pixel_interface_transaction import PixelInterfaceTransaction, PixelStruct, PIXEL_W
from .median_filter_sequence_item import MedianFilterSequenceItem
from tb_utils.generic_sequence import GenericSequence
from cocotb.types import Logic, LogicArray, Range


class MedianFilterSequence(GenericSequence):
    async def add_image(self, img, percent_idle):
        await self.notify_subscribers(img)

        pixel_data = list(img.getdata())

        start_seq = MedianFilterSequenceItem.invalid_seq_item()
        start_seq.start_i = Logic(1)
        await self.add_transaction(start_seq)

        for pixel in pixel_data:
            await self.add_idles_with_transaction(pixel, percent_idle)

    async def add_idles_with_transaction(self, pixel, percent_idle):
        while not (random.random() >= percent_idle):
            await self.add_transaction(MedianFilterSequenceItem.invalid_seq_item())

        await self.add_transaction(
            MedianFilterSequenceItem(
                start_i=Logic(0),
                pixel_valid_if_i=PixelInterfaceTransaction(
                    pixel=PixelStruct(
                        red=LogicArray(pixel[0], Range(PIXEL_W - 1, "downto", 0)),
                        green=LogicArray(pixel[1], Range(PIXEL_W - 1, "downto", 0)),
                        blue=LogicArray(pixel[2], Range(PIXEL_W - 1, "downto", 0)),
                    ),
                    valid=Logic(1),
                ),
            )
        )
