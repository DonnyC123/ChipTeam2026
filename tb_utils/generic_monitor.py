from cocotb import start_soon
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.queue import Queue
from dataclasses import fields
from typing import Generic, TypeVar, Type

from tb_utils.abstract_transactions import (
    AbstractTransaction,
    AbstractValidTransaction,
)

OutputTransaction = TypeVar("OutputTransaction", bound=AbstractTransaction)


class GenericMonitor(Generic[OutputTransaction]):
    def __init__(self, dut, output_transaction: Type[OutputTransaction]):
        self.dut = dut
        self.output_transaction: Type[OutputTransaction] = output_transaction
        self.actual_queue: Queue = Queue()
        start_soon(self.monitor_loop())

    async def monitor_loop(self):
        while True:
            output_transaction = await self.receive_transaction()
            await self.actual_queue.put(output_transaction.to_data)

    async def receive_transaction(self) -> OutputTransaction:
        await RisingEdge(self.dut.clk)
        await ReadOnly()

        output_transaction = self.output_transaction()
        for field in fields(output_transaction):
            if hasattr(self.dut, field.name):
                value = getattr(self.dut, field.name).value
                setattr(output_transaction, field.name, value)
            else:
                raise AttributeError(f"DUT has no signal named '{field.name}'")
        return output_transaction


OutputValidTransaction = TypeVar(
    "OutputValidTransaction", bound=AbstractValidTransaction
)


class GenericValidMonitor(GenericMonitor[OutputValidTransaction]):
    async def receive_transaction(self) -> OutputValidTransaction:
        while True:
            await RisingEdge(self.dut.clk)
            await ReadOnly()

            output_transaction = self.output_transaction()
            for field in fields(output_transaction):
                if hasattr(self.dut, field.name):
                    value = getattr(self.dut, field.name).value
                    setattr(output_transaction, field.name, value)
                else:
                    raise AttributeError(f"DUT has no signal named '{field.name}'")
            if output_transaction.valid:
                return output_transaction
