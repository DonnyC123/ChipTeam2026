import random

from cocotb.types import Logic, LogicArray

from ethernet_assembler.tb.ethernet_assembler_sequence_item import EthernetAssemblerSequenceItem
from tb_utils.generic_sequence import GenericSequence


class EthernetAssemblerSequence(GenericSequence):
    HEADER_W = 2
    BLOCK_TYPE_W = 8
    DATA_IN_W = EthernetAssemblerSequenceItem.DATA_IN_W
    PAYLOAD_W = EthernetAssemblerSequenceItem.PAYLOAD_W
    CONTROL_DATA_W = PAYLOAD_W - BLOCK_TYPE_W

    DATA_HDR = 0b01
    CTRL_HDR = 0b10
    BAD_HDR_00 = 0b00
    BAD_HDR_11 = 0b11

    IDLE_BLK = 0x1E
    SOF_L0 = 0x78
    SOF_L4 = 0x33
    TERM_L0 = 0x87
    TERM_L1 = 0x99
    TERM_L2 = 0xAA
    TERM_L3 = 0xB4
    TERM_L4 = 0xCC
    TERM_L5 = 0xD2
    TERM_L6 = 0xE1
    TERM_L7 = 0xFF
    OS_D6 = 0x66
    OS_D5 = 0x55
    OS_D3T = 0x4B
    OS_D3B = 0x2D

    @staticmethod
    def _to_logic(value: bool) -> Logic:
        return Logic("1" if value else "0")

    @staticmethod
    def _resolve_rng(
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> random.Random:
        if rng is not None:
            return rng
        return random.Random(seed)

    @classmethod
    def _compose_control_payload(cls, block_type: int, payload_low: int = 0) -> int:
        payload_low_mask = (1 << cls.CONTROL_DATA_W) - 1
        return ((block_type & 0xFF) << cls.CONTROL_DATA_W) | (payload_low & payload_low_mask)

    async def _add_input(
        self,
        *,
        input_data: int,
        header_bits: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        input_data &= (1 << self.DATA_IN_W) - 1
        header_bits &= (1 << self.HEADER_W) - 1

        seq_item = EthernetAssemblerSequenceItem(
            input_data_i=LogicArray.from_unsigned(input_data, self.DATA_IN_W),
            header_bits_i=LogicArray.from_unsigned(header_bits, self.HEADER_W),
            in_valid_i=self._to_logic(in_valid),
            locked_i=self._to_logic(locked),
            cancel_frame_i=self._to_logic(cancel_frame),
            no_valid_data=self._to_logic(False),
            drop_frame=self._to_logic(False),
        )
        await self.notify_subscribers(seq_item.to_data)
        await self.add_transaction(seq_item)

    async def _add_control_block_type(
        self,
        *,
        block_type: int,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        payload = self._compose_control_payload(block_type=block_type, payload_low=payload_low)
        await self.add_control_header(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_data_header(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_input(
            input_data=payload,
            header_bits=self.DATA_HDR,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_control_header(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_input(
            input_data=payload,
            header_bits=self.CTRL_HDR,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_bad_header(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        bad_header = local_rng.choice((self.BAD_HDR_00, self.BAD_HDR_11))

        await self._add_input(
            input_data=payload,
            header_bits=bad_header,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_idle_blk(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.IDLE_BLK,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_sof_l0(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.SOF_L0,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_sof_l4(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.SOF_L4,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l0(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L0,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l1(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L1,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l2(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L2,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l3(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L3,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l4(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L4,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l5(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L5,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l6(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L6,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_term_l7(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.TERM_L7,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_os_d6(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.OS_D6,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_os_d5(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.OS_D5,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_os_d3t(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.OS_D3T,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_os_d3b(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self._add_control_block_type(
            block_type=self.OS_D3B,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_manual_data(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_data_header(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_random_data(
        self,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        payload = local_rng.getrandbits(self.PAYLOAD_W)

        await self.add_data_header(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_manual_start(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        start_func = local_rng.choice((self.add_sof_l0, self.add_sof_l4))

        await start_func(
            payload_low=0,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        await self.add_manual_data(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_random_start(
        self,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        start_func = local_rng.choice((self.add_sof_l0, self.add_sof_l4))

        await start_func(
            payload_low=0,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        await self.add_random_data(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
            rng=local_rng,
        )

    async def start_and_cancel_frame(
        self,
        len: int,
        in_valid: bool = True,
        locked: bool = True,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> None:
        local_rng = self._resolve_rng(rng=rng, seed=seed)

        if len < 0:
            raise ValueError("len must be non-negative")

        if len == 0:
            await self.add_random_start(
                in_valid=in_valid,
                locked=locked,
                cancel_frame=True,
                rng=local_rng,
            )
            return

        await self.add_random_start(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=local_rng,
        )

        for index in range(len):
            await self.add_random_data(
                in_valid=in_valid,
                locked=locked,
                cancel_frame=(index == (len - 1)),
                rng=local_rng,
            )

    async def add_manual_end(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        term_func = local_rng.choice(
            (
                self.add_term_l0,
                self.add_term_l1,
                self.add_term_l2,
                self.add_term_l3,
                self.add_term_l4,
                self.add_term_l5,
                self.add_term_l6,
                self.add_term_l7,
            )
        )

        await term_func(
            payload_low=0,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        await self.add_manual_data(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_random_end(
        self,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        local_rng = self._resolve_rng(rng=rng, seed=seed)
        term_func = local_rng.choice(
            (
                self.add_term_l0,
                self.add_term_l1,
                self.add_term_l2,
                self.add_term_l3,
                self.add_term_l4,
                self.add_term_l5,
                self.add_term_l6,
                self.add_term_l7,
            )
        )

        await term_func(
            payload_low=0,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        await self.add_random_data(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
            rng=local_rng,
        )
