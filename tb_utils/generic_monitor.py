from cocotb import start_soon
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.queue import Queue
from dataclasses import fields, is_dataclass
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
        await self.recursive_receive(self.dut, output_transaction)

        return output_transaction

    async def recursive_receive(self, input_parent, transaction):
        for f in fields(transaction):
            field_name = f.name
            value = getattr(transaction, field_name)

            if hasattr(input_parent, field_name):
                signal_or_interface = getattr(input_parent, field_name)
                if is_dataclass(value):
                    await self.recursive_receive(signal_or_interface, value)
                else:
                    out_value = signal_or_interface.value
                    setattr(transaction, field_name, out_value)

            else:
                raise AttributeError(
                    f"Field '{field_name}' found in sequence item "
                    f"but NOT in DUT handle '{input_parent._name}'."
                )


OutputValidTransaction = TypeVar(
    "OutputValidTransaction", bound=AbstractValidTransaction
)


class GenericValidMonitor(GenericMonitor[OutputValidTransaction]):
    async def receive_transaction(self) -> OutputValidTransaction:
        while True:
            await RisingEdge(self.dut.clk)
            await ReadOnly()

            output_transaction = self.output_transaction()

            await self.recursive_receive(self.dut, output_transaction)

            if output_transaction.valid:
                return output_transaction
