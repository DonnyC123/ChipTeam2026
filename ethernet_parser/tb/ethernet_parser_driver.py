from dataclasses import fields, is_dataclass
from typing import TypeVar

from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_drivers import GenericDriver

GenericSequenceItem = TypeVar("GenericSequenceItem", bound=AbstractTransaction)


class EthernetParserDriver(GenericDriver[GenericSequenceItem]):
    def __init__(self, dut, seq_item_type: GenericSequenceItem):
        super().__init__(dut, seq_item_type, clk=dut.clk)

    async def recursive_drive(self, input_parent, item):
        for f in fields(item):
            if f.metadata.get("model_only", False):
                continue

            field_name = f.name
            value = getattr(item, field_name)

            if hasattr(input_parent, field_name):
                signal_or_interface = getattr(input_parent, field_name)
                if is_dataclass(value):
                    await self.recursive_drive(signal_or_interface, value)
                else:
                    signal_or_interface.value = value
            else:
                raise AttributeError(
                    f"Field '{field_name}' found in sequence item "
                    f"but NOT in DUT handle '{input_parent._name}'."
                )
