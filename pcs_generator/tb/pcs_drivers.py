from typing import Any, Generic, TypeVar

from cocotb import start_soon
from cocotb.queue import Queue
from cocotb.triggers import ReadOnly, RisingEdge

from tb_utils.abstract_transactions import AbstractTransaction


PCSSequenceItemT = TypeVar("PCSSequenceItemT", bound=AbstractTransaction)


class PCSDriver(Generic[PCSSequenceItemT]):
    def __init__(self, dut, seq_item_type: PCSSequenceItemT):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.seq_item_queue: Queue[PCSSequenceItemT] = Queue()
        self.transaction_subscribers: list[Any] = []
        self._active_transaction: PCSSequenceItemT | None = None

        start_soon(self.driver_loop())

    def add_subscriber(self, *subscribers):
        self.transaction_subscribers.extend(
            subscriber for subscriber in subscribers if hasattr(subscriber, "notify")
        )

    async def send(self, transaction: PCSSequenceItemT):
        await self.seq_item_queue.put(transaction)

    async def notify_subscribers(self, transaction: PCSSequenceItemT):
        for subscriber in self.transaction_subscribers:
            if hasattr(subscriber, "notify"):
                await subscriber.notify(transaction)
            else:
                print(f"Warning: Don't know how to notify {subscriber}")

    def _axis_handshake_will_complete_this_cycle(
        self, transaction: PCSSequenceItemT
    ) -> bool:
        if not bool(transaction.tvalid):
            return False
        return bool(int(self.dut.axis_slave_if.tready.value))

    async def driver_loop(self):
        while True:
            if self._active_transaction is None:
                if not self.seq_item_queue.empty():
                    self._active_transaction = await self.seq_item_queue.get()
                else:
                    self._active_transaction = self.seq_item_type.invalid_seq_item()

            await self.drive_transaction(self._active_transaction)
            await ReadOnly()
            handshake_will_complete = self._axis_handshake_will_complete_this_cycle(
                self._active_transaction
            )
            await RisingEdge(self.dut.clk)

            if handshake_will_complete:
                await self.notify_subscribers(self._active_transaction)
                self._active_transaction = None
            elif not bool(self._active_transaction.tvalid):
                self._active_transaction = None

    async def busy(self):
        return (not self.seq_item_queue.empty()) or (
            self._active_transaction is not None and bool(self._active_transaction.tvalid)
        )

    async def drive_transaction(self, sequence_item: PCSSequenceItemT):
        # Only drive DUT inputs that pcs_generator consumes directly.
        self.dut.axis_slave_if.tdata.value = sequence_item.tdata
        self.dut.axis_slave_if.tkeep.value = sequence_item.tkeep
        self.dut.axis_slave_if.tvalid.value = sequence_item.tvalid
        self.dut.axis_slave_if.tlast.value = sequence_item.tlast
        self.dut.out_ready_i.value = sequence_item.out_ready_i

    async def wait_until_idle(self):
        while await self.busy():
            await RisingEdge(self.dut.clk)


GenericDriver = PCSDriver
