from ethernet_assembler.tb.ethernet_assembler_sequence_item import EthernetAssemblerSequenceItem
from tb_utils.generic_sequence import GenericSequence

from cocotb.types import Logic, LogicArray


class EthernetAssemblerSequence(GenericSequence):
    HEADER_W = 2
    PAYLOAD_W = 64
    DATA_IN_W = EthernetAssemblerSequenceItem.DATA_IN_W

    DATA_SYNC_HEADER = 0b01
    CONTROL_SYNC_HEADER = 0b10

    @staticmethod
    def _to_logic(value: bool) -> Logic:
        return Logic("1" if value else "0")

    async def add_input(self, input_data: int, in_valid: bool = True, locked: bool = True):
        input_data &= (1 << self.DATA_IN_W) - 1
        seq_item = EthernetAssemblerSequenceItem(
            input_data_i=LogicArray.from_unsigned(input_data, self.DATA_IN_W),
            in_valid_i=self._to_logic(in_valid),
            locked_i=self._to_logic(locked),
        )
        await self.notify_subscribers(seq_item.to_data)
        await self.add_transaction(seq_item)

    async def add_block(
        self, sync_header: int, payload: int, in_valid: bool = True, locked: bool = True
    ):
        input_data = ((sync_header & 0b11) << self.PAYLOAD_W) | (
            payload & ((1 << self.PAYLOAD_W) - 1)
        )
        await self.add_input(input_data=input_data, in_valid=in_valid, locked=locked)

    async def add_data_block(self, payload: int, in_valid: bool = True, locked: bool = True):
        await self.add_block(
            sync_header=self.DATA_SYNC_HEADER,
            payload=payload,
            in_valid=in_valid,
            locked=locked,
        )

    async def add_control_block(
        self, payload: int, in_valid: bool = True, locked: bool = True
    ):
        await self.add_block(
            sync_header=self.CONTROL_SYNC_HEADER,
            payload=payload,
            in_valid=in_valid,
            locked=locked,
        )
