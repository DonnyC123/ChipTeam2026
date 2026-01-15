from cocotb import start_soon
from cocotb.triggers import RisingEdge
from cocotb.queue import Queue
from dataclasses import fields
from typing import Generic, TypeVar

from tb_utils.abstract_transactions import (
    AbstractTransaction,
    # AbstractValidSequenceItem,
)

GenericSequenceItem = TypeVar("GenericSequenceItem", bound=AbstractTransaction)


class GenericDriver(Generic[GenericSequenceItem]):
    def __init__(self, dut, seq_item_type: GenericSequenceItem):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.seq_item_queue: Queue[GenericSequenceItem] = Queue()

        start_soon(self.driver_loop())

    async def send(self, transaction: GenericSequenceItem):
        await self.seq_item_queue.put(transaction)

    async def driver_loop(self):
        while True:
            if not self.seq_item_queue.empty():
                seq_item = await self.seq_item_queue.get()
            else:
                seq_item = self.seq_item_type.invalid_seq_item()

            await self.drive_transaction(seq_item)
            await RisingEdge(self.dut.clk)

    async def busy(self):
        return not self.seq_item_queue.empty()

    async def drive_transaction(self, sequenece_item: GenericSequenceItem):
        for field in fields(sequenece_item):
            value = getattr(sequenece_item, field.name)
            if hasattr(self.dut, field.name):
                getattr(self.dut, field.name).value = value
            else:
                raise AttributeError(f"DUT has no signal named '{field.name}'")

    async def wait_until_idle(self):
        while not self.seq_item_queue.empty():
            await RisingEdge(self.dut.clk)

    # GenericValidSequenceItem = TypeVar(
    #    "GenericValidSequenceItem", bound=AbstractValidSequenceItem
    # )
    #
    # class GenericValidDriver(GenericDriver[GenericValidSequenceItem]):
    #    async def drive_invalid_transation(self):
    #        invalid_stimulus = self.seq_item_type()
    #        self.valid = False
    #        for field in fields(invalid_stimulus):
    #            value = getattr(invalid_stimulus, field.name)
    #            if hasattr(self.dut, field.name):
    #                getattr(self.dut, field.name).value = value
    #            else:
    #                raise AttributeError(f"DUT has no signal named '{field.name}'")
    #
    #    async def driver_loop(self):
    #        while True:
    #            if not self.seq_item_queue.empty():
    #                stimulus = await self.seq_item_queue.get()
    #                await self.drive_transaction(rising_stimulus)
    #                await RisingEdge(self.dut.clk)
    #
    #            else:
    #                stimulus = self.input_invalid_stimulus
    #            await self.drive_transaction(rising_stimulus)
    #                await RisingEdge(self.dut.clk)
