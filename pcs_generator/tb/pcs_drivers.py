from cocotb import start_soon
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge
from typing import Generic, TypeVar

from tb_utils.abstract_transactions import AbstractTransaction


PCSSequenceItemT = TypeVar("PCSSequenceItemT", bound=AbstractTransaction)


class PCSDriver(Generic[PCSSequenceItemT]):
    def __init__(self, dut, seq_item_type: PCSSequenceItemT):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.seq_item_queue: Queue[PCSSequenceItemT] = Queue()

        start_soon(self.driver_loop())

    async def send(self, transaction: PCSSequenceItemT):
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

    async def drive_transaction(self, sequence_item: PCSSequenceItemT):
        # Only drive DUT inputs that pcs_generator consumes directly.
        self.dut.axis_slave_if.tdata.value = sequence_item.tdata
        self.dut.axis_slave_if.tkeep.value = sequence_item.tkeep
        self.dut.axis_slave_if.tvalid.value = sequence_item.tvalid
        self.dut.axis_slave_if.tlast.value = sequence_item.tlast
        self.dut.out_ready_i.value = sequence_item.out_ready_i

    async def wait_until_idle(self):
        while not self.seq_item_queue.empty():
            await RisingEdge(self.dut.clk)


GenericDriver = PCSDriver
