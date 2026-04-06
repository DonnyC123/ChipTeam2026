import random

from ethernet_assembler.tb.ethernet_assembler_sequence_item import EthernetAssemblerSequenceItem
from tb_utils.generic_sequence import GenericSequence

from cocotb.types import Logic, LogicArray


class EthernetAssemblerSequence(GenericSequence):
    HEADER_W = 2
    PAYLOAD_W = 64
    BLOCK_TYPE_W = 8
    DATA_IN_W = EthernetAssemblerSequenceItem.DATA_IN_W
    CONTROL_DATA_W = PAYLOAD_W - BLOCK_TYPE_W

    DATA_SYNC_HEADER = 0b01
    CONTROL_SYNC_HEADER = 0b10
    SYNC_HEADER_BAD1 = 0b00
    SYNC_HEADER_BAD2 = 0b11

    START_BLOCKS = {
        0: 0x78,  # SOF_L0
        4: 0x33,  # SOF_L4
    }
    TERM_BLOCKS = {
        0: 0x87,  # TERM_L0
        1: 0x99,  # TERM_L1
        2: 0xAA,  # TERM_L2
        3: 0xB4,  # TERM_L3
        4: 0xCC,  # TERM_L4
        5: 0xD2,  # TERM_L5
        6: 0xE1,  # TERM_L6
        7: 0xFF,  # TERM_L7
    }
    ORDERED_SET_BLOCKS = {
        "OS_D6": 0x66,
        "OS_D5": 0x55,
        "OS_D3T": 0x4B,
        "OS_D3B": 0x2D,
    }
    IDLE_BLOCK = 0x1E

    VALID_CONTROL_BLOCK_TYPES = {
        0x1E,  # IDLE_BLK
        0x2D,  # OS_D3B
        0x33,  # SOF_L4
        0x4B,  # OS_D3T
        0x55,  # OS_D5
        0x66,  # OS_D6
        0x78,  # SOF_L0
        0x87,  # TERM_L0
        0x99,  # TERM_L1
        0xAA,  # TERM_L2
        0xB4,  # TERM_L3
        0xCC,  # TERM_L4
        0xD2,  # TERM_L5
        0xE1,  # TERM_L6
        0xFF,  # TERM_L7
    }
    RANDOM_PRIMITIVE_KINDS = (
        "data",
        "start",
        "term",
        "idle",
        "ordered_set",
        "bad_header",
        "unknown_control",
    )

    @staticmethod
    def _to_logic(value: bool) -> Logic:
        return Logic("1" if value else "0")

    @staticmethod
    def _resolve_rng(
        rng: random.Random | None = None, seed: int | None = None
    ) -> random.Random:
        if rng is not None:
            return rng
        return random.Random(seed)

    @classmethod
    def _compose_control_payload(cls, block_type: int, payload_low: int = 0) -> int:
        payload_low_mask = (1 << cls.CONTROL_DATA_W) - 1
        return ((block_type & 0xFF) << cls.CONTROL_DATA_W) | (payload_low & payload_low_mask)

    @staticmethod
    def _resolve_signal_qualifiers(
        *,
        in_valid: bool | None = None,
        locked: bool | None = None,
        cancel_frame: bool | None = None,
    ) -> dict[str, bool]:
        """Resolve optional input qualifier overrides to concrete booleans."""
        return {
            "in_valid": True if in_valid is None else bool(in_valid),
            "locked": True if locked is None else bool(locked),
            "cancel_frame": False if cancel_frame is None else bool(cancel_frame),
        }

    @classmethod
    def signal_nominal(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers()

    @classmethod
    def signal_cancel_high(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(cancel_frame=True)

    @classmethod
    def signal_cancel_low(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(cancel_frame=False)

    @classmethod
    def signal_in_valid_high(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(in_valid=True)

    @classmethod
    def signal_in_valid_low(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(in_valid=False)

    @classmethod
    def signal_locked_high(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(locked=True)

    @classmethod
    def signal_locked_low(cls) -> dict[str, bool]:
        return cls._resolve_signal_qualifiers(locked=False)

    async def add_start_block_with_signals(
        self,
        lane: int = 0,
        payload_low: int = 0,
        *,
        in_valid: bool | None = None,
        locked: bool | None = None,
        cancel_frame: bool | None = None,
    ):
        qualifiers = self._resolve_signal_qualifiers(
            in_valid=in_valid, locked=locked, cancel_frame=cancel_frame
        )
        await self.add_start_block(lane=lane, payload_low=payload_low, **qualifiers)

    async def add_data_block_with_signals(
        self,
        payload: int,
        *,
        in_valid: bool | None = None,
        locked: bool | None = None,
        cancel_frame: bool | None = None,
    ):
        qualifiers = self._resolve_signal_qualifiers(
            in_valid=in_valid, locked=locked, cancel_frame=cancel_frame
        )
        await self.add_data_block(payload=payload, **qualifiers)

    async def add_control_block_with_signals(
        self,
        payload: int,
        *,
        in_valid: bool | None = None,
        locked: bool | None = None,
        cancel_frame: bool | None = None,
    ):
        qualifiers = self._resolve_signal_qualifiers(
            in_valid=in_valid, locked=locked, cancel_frame=cancel_frame
        )
        await self.add_control_block(payload=payload, **qualifiers)

    async def add_start_block_cancel_high(
        self, lane: int = 0, payload_low: int = 0, *, in_valid: bool = True, locked: bool = True
    ):
        await self.add_start_block(
            lane=lane, payload_low=payload_low, in_valid=in_valid, locked=locked, cancel_frame=True
        )

    async def add_start_block_cancel_low(
        self, lane: int = 0, payload_low: int = 0, *, in_valid: bool = True, locked: bool = True
    ):
        await self.add_start_block(
            lane=lane, payload_low=payload_low, in_valid=in_valid, locked=locked, cancel_frame=False
        )

    async def add_start_block_in_valid_low(
        self, lane: int = 0, payload_low: int = 0, *, locked: bool = True, cancel_frame: bool = False
    ):
        await self.add_start_block(
            lane=lane,
            payload_low=payload_low,
            in_valid=False,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_start_block_in_valid_high(
        self, lane: int = 0, payload_low: int = 0, *, locked: bool = True, cancel_frame: bool = False
    ):
        await self.add_start_block(
            lane=lane,
            payload_low=payload_low,
            in_valid=True,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_start_block_locked_low(
        self, lane: int = 0, payload_low: int = 0, *, in_valid: bool = True, cancel_frame: bool = False
    ):
        await self.add_start_block(
            lane=lane,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=False,
            cancel_frame=cancel_frame,
        )

    async def add_start_block_locked_high(
        self, lane: int = 0, payload_low: int = 0, *, in_valid: bool = True, cancel_frame: bool = False
    ):
        await self.add_start_block(
            lane=lane,
            payload_low=payload_low,
            in_valid=in_valid,
            locked=True,
            cancel_frame=cancel_frame,
        )

    def build_data_primitive(
        self, payload: int | None = None, rng: random.Random | None = None
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if payload is None:
            payload = local_rng.getrandbits(self.PAYLOAD_W)
        return {"kind": "data", "payload": payload}

    def build_start_primitive(
        self,
        lane: int | None = None,
        payload_low: int | None = None,
        rng: random.Random | None = None,
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if lane is None:
            lane = local_rng.choice(tuple(self.START_BLOCKS))
        if payload_low is None:
            payload_low = local_rng.getrandbits(self.CONTROL_DATA_W)
        return {"kind": "start", "lane": lane, "payload_low": payload_low}

    def build_terminate_primitive(
        self,
        lane: int | None = None,
        payload_low: int | None = None,
        rng: random.Random | None = None,
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if lane is None:
            lane = local_rng.choice(tuple(self.TERM_BLOCKS))
        if payload_low is None:
            payload_low = local_rng.getrandbits(self.CONTROL_DATA_W)
        return {"kind": "term", "lane": lane, "payload_low": payload_low}

    def build_idle_primitive(
        self, payload_low: int | None = None, rng: random.Random | None = None
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if payload_low is None:
            payload_low = local_rng.getrandbits(self.CONTROL_DATA_W)
        return {"kind": "idle", "payload_low": payload_low}

    def build_ordered_set_primitive(
        self,
        os_kind: str | None = None,
        payload_low: int | None = None,
        rng: random.Random | None = None,
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if os_kind is None:
            os_kind = local_rng.choice(tuple(self.ORDERED_SET_BLOCKS))
        if payload_low is None:
            payload_low = local_rng.getrandbits(self.CONTROL_DATA_W)
        return {"kind": "ordered_set", "os_kind": os_kind, "payload_low": payload_low}

    def build_bad_header_primitive(
        self,
        payload: int | None = None,
        bad_header: int | None = None,
        rng: random.Random | None = None,
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if payload is None:
            payload = local_rng.getrandbits(self.PAYLOAD_W)
        if bad_header is None:
            bad_header = local_rng.choice((self.SYNC_HEADER_BAD1, self.SYNC_HEADER_BAD2))
        return {"kind": "bad_header", "payload": payload, "bad_header": bad_header}

    def build_unknown_control_primitive(
        self,
        payload: int | None = None,
        invalid_block_type: int | None = None,
        rng: random.Random | None = None,
    ) -> dict:
        local_rng = self._resolve_rng(rng)
        if payload is None:
            payload = local_rng.getrandbits(self.PAYLOAD_W)
        return {
            "kind": "unknown_control",
            "payload": payload,
            "invalid_block_type": invalid_block_type,
        }

    def build_random_primitive(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        include_corruption: bool = True,
    ) -> dict:
        local_rng = self._resolve_rng(rng, seed)
        primitive_kinds = [
            "data",
            "start",
            "term",
            "idle",
            "ordered_set",
            "bad_header",
            "unknown_control",
        ]
        if not include_corruption:
            primitive_kinds = [kind for kind in primitive_kinds if kind not in {"bad_header", "unknown_control"}]

        kind = local_rng.choice(primitive_kinds)
        if kind == "data":
            return self.build_data_primitive(rng=local_rng)
        if kind == "start":
            return self.build_start_primitive(rng=local_rng)
        if kind == "term":
            return self.build_terminate_primitive(rng=local_rng)
        if kind == "idle":
            return self.build_idle_primitive(rng=local_rng)
        if kind == "ordered_set":
            return self.build_ordered_set_primitive(rng=local_rng)
        if kind == "bad_header":
            return self.build_bad_header_primitive(rng=local_rng)
        return self.build_unknown_control_primitive(rng=local_rng)

    async def add_primitive(
        self,
        primitive: dict,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        kind = primitive.get("kind")
        if kind == "data":
            await self.add_data_block(
                payload=primitive["payload"],
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "start":
            await self.add_start_block(
                lane=primitive["lane"],
                payload_low=primitive.get("payload_low", 0),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "term":
            await self.add_terminate_block(
                lane=primitive["lane"],
                payload_low=primitive.get("payload_low", 0),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "idle":
            await self.add_idle_block(
                payload_low=primitive.get("payload_low", 0),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "ordered_set":
            await self.add_ordered_set_block(
                os_kind=primitive["os_kind"],
                payload_low=primitive.get("payload_low", 0),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "bad_header":
            await self.add_bad_header(
                payload=primitive["payload"],
                bad_header=primitive.get("bad_header"),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return
        if kind == "unknown_control":
            await self.add_unknown_control_block(
                payload=primitive.get("payload"),
                invalid_block_type=primitive.get("invalid_block_type"),
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return

        raise ValueError(
            f"Unknown primitive kind '{kind}'. Expected one of {self.RANDOM_PRIMITIVE_KINDS}"
        )

    async def add_input(
        self,
        input_data: int,
        header_bits: int | None = None,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        # Backward compatible fallback: if header_bits is omitted, allow callers
        # to pass legacy packed input_data[65:64|63:0].
        if header_bits is None:
            header_bits = (input_data >> self.DATA_IN_W) & ((1 << self.HEADER_W) - 1)

        input_data &= (1 << self.DATA_IN_W) - 1
        header_bits &= (1 << self.HEADER_W) - 1
        seq_item = EthernetAssemblerSequenceItem(
            input_data_i=LogicArray.from_unsigned(input_data, self.DATA_IN_W),
            header_bits_i=LogicArray.from_unsigned(header_bits, self.HEADER_W),
            in_valid_i=self._to_logic(in_valid),
            locked_i=self._to_logic(locked),
            cancel_frame_i=self._to_logic(cancel_frame),
        )
        await self.notify_subscribers(seq_item.to_data)
        await self.add_transaction(seq_item)

    async def add_block(
        self,
        sync_header: int,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_input(
            input_data=payload,
            header_bits=sync_header,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_data_block(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_block(
            sync_header=self.DATA_SYNC_HEADER,
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_control_block(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_block(
            sync_header=self.CONTROL_SYNC_HEADER,
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_start_block(
        self,
        lane: int = 0,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        if lane not in self.START_BLOCKS:
            raise ValueError(f"start lane must be one of {sorted(self.START_BLOCKS)}, got {lane}")

        await self.add_control_block(
            payload=self._compose_control_payload(
                block_type=self.START_BLOCKS[lane],
                payload_low=payload_low,
            ),
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_terminate_block(
        self,
        lane: int = 0,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        if lane not in self.TERM_BLOCKS:
            raise ValueError(f"terminate lane must be one of {sorted(self.TERM_BLOCKS)}, got {lane}")

        await self.add_control_block(
            payload=self._compose_control_payload(
                block_type=self.TERM_BLOCKS[lane],
                payload_low=payload_low,
            ),
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_idle_block(
        self,
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_control_block(
            payload=self._compose_control_payload(
                block_type=self.IDLE_BLOCK,
                payload_low=payload_low,
            ),
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_ordered_set_block(
        self,
        os_kind: str = "OS_D6",
        payload_low: int = 0,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        if os_kind not in self.ORDERED_SET_BLOCKS:
            raise ValueError(
                f"os_kind must be one of {sorted(self.ORDERED_SET_BLOCKS)}, got '{os_kind}'"
            )

        await self.add_control_block(
            payload=self._compose_control_payload(
                block_type=self.ORDERED_SET_BLOCKS[os_kind],
                payload_low=payload_low,
            ),
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_bad_header(
        self,
        payload: int,
        bad_header: int | None = None,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
    ):
        local_rng = self._resolve_rng(rng)
        if bad_header is None:
            bad_header = local_rng.choice((self.SYNC_HEADER_BAD1, self.SYNC_HEADER_BAD2))

        bad_header &= 0b11
        if bad_header in (self.DATA_SYNC_HEADER, self.CONTROL_SYNC_HEADER):
            raise ValueError(
                f"bad_header=0b{bad_header:02b} is a legal header; expected one of 0b00/0b11"
            )

        await self.add_block(
            sync_header=bad_header,
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_bad_sync_header(
        self,
        payload: int,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        # Backward-compatible alias.
        await self.add_bad_header(
            payload=payload,
            bad_header=None,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_unknown_control_block(
        self,
        payload: int | None = None,
        invalid_block_type: int | None = None,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
    ):
        await self.add_invalid_block_type_block(
            payload=payload,
            invalid_block_type=invalid_block_type,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )

    async def add_corrupted_block(
        self,
        payload: int | None = None,
        corruption_kind: str = "auto",
        invalid_block_type: int | None = None,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        rng = self._resolve_rng(rng, seed)
        if payload is None:
            payload = rng.getrandbits(self.PAYLOAD_W)

        kind = corruption_kind
        if kind == "auto":
            kind = rng.choice(("bad_header", "unknown_control"))

        if kind == "bad_header":
            await self.add_bad_header(
                payload=payload,
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return

        if kind == "unknown_control":
            await self.add_unknown_control_block(
                payload=payload,
                invalid_block_type=invalid_block_type,
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
            return

        raise ValueError(
            "corruption_kind must be one of {'auto', 'bad_header', 'unknown_control'}"
        )

    async def add_invalid_block_type_block(
        self,
        payload: int | None = None,
        invalid_block_type: int | None = None,
        in_valid: bool = True,
        locked: bool = True,
        cancel_frame: bool = False,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        rng = self._resolve_rng(rng, seed)
        block_data_w = self.PAYLOAD_W - self.BLOCK_TYPE_W
        block_data_mask = (1 << block_data_w) - 1

        if invalid_block_type is None:
            invalid_block_type = rng.getrandbits(self.BLOCK_TYPE_W)
            while invalid_block_type in self.VALID_CONTROL_BLOCK_TYPES:
                invalid_block_type = rng.getrandbits(self.BLOCK_TYPE_W)
        else:
            invalid_block_type &= (1 << self.BLOCK_TYPE_W) - 1
            if invalid_block_type in self.VALID_CONTROL_BLOCK_TYPES:
                raise ValueError(
                    f"invalid_block_type=0x{invalid_block_type:02X} is a valid control block type"
                )

        if payload is None:
            payload = rng.getrandbits(self.PAYLOAD_W)

        payload_with_invalid_type = (
            (invalid_block_type << block_data_w) | (payload & block_data_mask)
        )

        await self.add_control_block(
            payload=payload_with_invalid_type,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )


    async def add_random_blocks(
        self,
        num_blocks: int,
        in_valid_probability: float = 1.0,
        locked_probability: float = 1.0,
        cancel_frame_probability: float = 0.0,
        seed: int | None = None,
        rng: random.Random | None = None,
    ):
        if num_blocks < 0:
            raise ValueError("num_blocks must be >= 0")

        if not 0.0 <= in_valid_probability <= 1.0:
            raise ValueError("in_valid_probability must be in [0.0, 1.0]")

        if not 0.0 <= locked_probability <= 1.0:
            raise ValueError("locked_probability must be in [0.0, 1.0]")

        if not 0.0 <= cancel_frame_probability <= 1.0:
            raise ValueError("cancel_frame_probability must be in [0.0, 1.0]")

        rng = self._resolve_rng(rng, seed)
        payload_mask = (1 << self.PAYLOAD_W) - 1

        for _ in range(num_blocks):
            sync_header = rng.getrandbits(self.HEADER_W)
            payload = rng.getrandbits(self.PAYLOAD_W) & payload_mask
            in_valid = rng.random() < in_valid_probability
            locked = rng.random() < locked_probability
            cancel_frame = rng.random() < cancel_frame_probability
            await self.add_block(
                sync_header=sync_header,
                payload=payload,
                in_valid=in_valid,
                locked=locked,
                cancel_frame=cancel_frame,
            )
