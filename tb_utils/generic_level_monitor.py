from typing import Generic, TypeVar, Type
from dataclasses import fields, is_dataclass
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.types import Logic

OutputTransaction = TypeVar("OutputTransaction")


class GenericLevelMonitor(Generic[OutputTransaction]):
    def __init__(self, dut, done_transaction: Type[OutputTransaction], level: bool):
        self.dut = dut
        self.done_transaction = done_transaction
        self.level = level

    async def BlockUntilOneHigh(self):
        done = False
        while not done:
            await RisingEdge(self.dut.clk)
            await ReadOnly()

            output_transaction = self.done_transaction()

            done = await self.recursive_receive(self.dut, output_transaction)

    async def recursive_receive(self, input_parent, transaction):
        """
        Recursively checks signals. Returns True if ANY signal matches self.level.
        """
        found_match = False

        for f in fields(transaction):
            field_name = f.name

            if hasattr(input_parent, field_name):
                signal_or_interface = getattr(input_parent, field_name)

                if is_dataclass(getattr(transaction, field_name)):
                    is_sub_match = await self.recursive_receive(
                        signal_or_interface, getattr(transaction, field_name)
                    )
                    found_match = found_match or is_sub_match

                else:
                    val = signal_or_interface.value

                    if not val.is_resolvable:
                        is_match = False
                    else:
                        is_match = val == self.level

                    found_match = found_match or is_match

            else:
                raise AttributeError(
                    f"Field '{field_name}' found in transaction "
                    f"but NOT in DUT handle '{input_parent._name}'."
                )

        return found_match
