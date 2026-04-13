from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from tx_pcs_generator_sequence_item import TxPcsGeneratorSequenceItem


class TxPcsGeneratorSequence(GenericSequence):
    DATA_W = TxPcsGeneratorSequenceItem.DATA_W
    KEEP_W = TxPcsGeneratorSequenceItem.KEEP_W

    async def add_cycle(
        self,
        valid: bool = False,
        data: int = 0,
        keep: int = 0xFF,
        last: int = 0,
        out_ready: int = 1,
    ):
        await self.notify_subscribers(
            {
                "valid": bool(valid),
                "data": int(data),
                "keep": int(keep),
                "last": int(last),
                "out_ready": int(out_ready),
            }
        )

        await self.add_transaction(
            TxPcsGeneratorSequenceItem(
                in_data_i=LogicArray.from_unsigned(int(data) if valid else 0, self.DATA_W),
                in_keep_i=LogicArray.from_unsigned(int(keep) if valid else 0, self.KEEP_W),
                in_last_i=Logic("1" if (valid and last) else "0"),
                in_valid_i=Logic("1" if valid else "0"),
                out_ready_i=Logic("1" if out_ready else "0"),
            )
        )

    async def add_word(
        self,
        data: int,
        keep: int = 0xFF,
        last: int = 0,
        out_ready: int = 1,
    ):
        await self.add_cycle(valid=True, data=data, keep=keep, last=last, out_ready=out_ready)

    async def add_idle(self, cycles: int = 1, out_ready: int = 1):
        for _ in range(cycles):
            await self.add_cycle(valid=False, out_ready=out_ready)
