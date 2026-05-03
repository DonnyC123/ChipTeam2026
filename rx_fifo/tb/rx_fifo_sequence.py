import random

from cocotb.types import Logic, LogicArray

from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.generic_sequence import GenericSequence


class RXFifoSequence(GenericSequence):
    DATA_IN_W = RXFifoSequenceItem.DATA_IN_W
    IN_MASK_W = RXFifoSequenceItem.IN_MASK_W

    def __init__(self, driver, *subscribers):
        super().__init__(driver, *subscribers)
        self._reset_current_item()

    def _reset_current_item(self):
        self._current_item = RXFifoSequenceItem()

    @staticmethod
    def _to_logic(value: bool | int | Logic) -> Logic:
        if isinstance(value, Logic):
            return value
        if value in (0, False):
            return Logic("0")
        if value in (1, True):
            return Logic("1")
        raise ValueError(f"Expected Logic-compatible value, got {value!r}")

    @staticmethod
    def _to_logic_array(value: int | LogicArray, width: int) -> LogicArray:
        if isinstance(value, LogicArray):
            if len(value) != width:
                raise ValueError(f"Expected LogicArray width {width}, got {len(value)}")
            return value
        if value < 0 or value >= (1 << width):
            raise ValueError(f"Value {value} does not fit in {width} bits")
        return LogicArray.from_unsigned(value, width)

    @staticmethod
    def _resolve_rng(
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> random.Random:
        if rng is not None:
            return rng
        return random.Random(seed)

    def add_data(self, value: int | LogicArray):
        self._current_item.data_i = self._to_logic_array(value, self.DATA_IN_W)

    def add_mask(self, value: int | LogicArray):
        self._current_item.mask_i = self._to_logic_array(value, self.IN_MASK_W)

    def add_valid(self, value: bool | int | Logic):
        self._current_item.valid_i = self._to_logic(value)

    def add_drop(self, value: bool | int | Logic):
        self._current_item.drop_i = self._to_logic(value)

    def add_send(self, value: bool | int | Logic):
        self._current_item.send_i = self._to_logic(value)

    async def add_valid_input(self, data: int | LogicArray, mask: int | LogicArray):
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_data(data)
            self.add_mask(mask)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(0)
            await self.send_current()
        finally:
            self._current_item = staged_item

    async def add_manual_last_in(
        self,
        data: int | LogicArray,
        mask: int | LogicArray,
    ) -> None:
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_data(data)
            self.add_mask(mask)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(1)
            await self.send_current()
        finally:
            self._current_item = staged_item

    def add_random_data(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        self.add_data(resolved_rng.randrange(1 << self.DATA_IN_W))

    def add_random_mask(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        toggle: bool | int = 1,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        if toggle in (1, True):
            random_upper_bits = resolved_rng.randrange(1 << (self.IN_MASK_W - 1))
            self.add_mask(random_upper_bits << 1)
            return
        if toggle in (0, False):
            self.add_mask(resolved_rng.randrange(1 << self.IN_MASK_W))
            return
        raise ValueError(f"Expected toggle to be 0/1 or bool, got {toggle!r}")

    def add_random_valid(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        self.add_valid(resolved_rng.randrange(2))

    def add_random_drop(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        self.add_drop(resolved_rng.randrange(2))

    def add_random_send(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        self.add_send(resolved_rng.randrange(2))

    async def add_valid_random_input(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        mask_toggle: bool | int = 1,
    ):
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_random_data(rng=rng, seed=seed)
            self.add_random_mask(rng=rng, seed=seed, toggle=mask_toggle)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(0)
            await self.send_current()
        finally:
            self._current_item = staged_item

    async def add_random_last_in(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        mask_toggle: bool | int = 1,
    ) -> None:
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_random_data(rng=rng, seed=seed)
            self.add_random_mask(rng=rng, seed=seed, toggle=mask_toggle)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(1)
            await self.send_current()
        finally:
            self._current_item = staged_item

    async def add_random_invalid_input(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        staged_item = self._current_item
        self._reset_current_item()
        try:
            invalid_mode = resolved_rng.randrange(3)

            self.add_random_data(rng=resolved_rng)
            self.add_send(0)
            # these are the three invalid cases
            if invalid_mode == 0:
                self.add_random_mask(rng=resolved_rng)
                self.add_valid(1)
                self.add_drop(1)
            elif invalid_mode == 1:
                self.add_random_mask(rng=resolved_rng)
                self.add_valid(0)
                self.add_drop(0)
            else:
                self.add_mask(0)
                self.add_valid(1)
                self.add_drop(0)

            await self.send_current()
        finally:
            self._current_item = staged_item

    async def send_current(self):
        item = self._current_item
        await self.notify_subscribers(item.to_data)
        await self.add_transaction(item)
        self._reset_current_item()

    async def drive_idle(self, count: int = 1):
        for _ in range(count):
            self.add_data(0)
            self.add_mask(0)
            self.add_valid(0)
            self.add_drop(0)
            self.add_send(0)
            await self.send_current()

    async def generate_valid_packet(
        self,
        length: int,
        rng: random.Random | None = None,
        seed: int | None = None,
        data: list[int] | None = None,
        mid_mask: int = 0xFF,
        last_mask: int | None = None,
        idle_drop_prob: float = 0.0,
        max_idle_drop: int = 2,
    ):
        if length < 1:
            raise ValueError(f"Packet length must be >= 1, got {length}")
        if data is not None and len(data) != length:
            raise ValueError(f"Expected {length} data words, got {len(data)}")

        resolved_rng = self._resolve_rng(rng, seed)
        resolved_last_mask = mid_mask if last_mask is None else last_mask

        def pick_data(idx: int) -> int:
            if data is not None:
                return data[idx]
            return resolved_rng.randrange(1 << self.DATA_IN_W)

        for beat_idx in range(length - 1):
            await self.add_valid_input(data=pick_data(beat_idx), mask=mid_mask)
            if idle_drop_prob > 0 and resolved_rng.random() < idle_drop_prob:
                await self.drive_idle(resolved_rng.randint(1, max_idle_drop))

        await self.add_manual_last_in(
            data=pick_data(length - 1),
            mask=resolved_last_mask,
        )

    async def generate_random_valid_packet(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        min_beats: int = 3,
        max_beats: int = 4,
        mid_mask: int = 0xFF,
        idle_drop_prob: float = 0.3,
    ):
        if min_beats < 1 or max_beats < min_beats:
            raise ValueError(f"Invalid beat range: min={min_beats}, max={max_beats}")
        resolved_rng = self._resolve_rng(rng, seed)
        length = resolved_rng.randint(min_beats, max_beats)
        await self.generate_valid_packet(
            length=length,
            rng=resolved_rng,
            mid_mask=mid_mask,
            idle_drop_prob=idle_drop_prob,
        )

    async def generate_invalid_packet(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        n_beats: int = 1,
    ):
        if n_beats < 1:
            raise ValueError(f"n_beats must be >= 1, got {n_beats}")
        resolved_rng = self._resolve_rng(rng, seed)
        for _ in range(n_beats):
            await self.add_random_invalid_input(rng=resolved_rng)

    async def apply_inter_packet_gap(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        min_idle: int = 2,
        max_idle: int = 4,
    ):
        if min_idle < 0 or max_idle < min_idle:
            raise ValueError(f"Invalid idle range: min={min_idle}, max={max_idle}")
        resolved_rng = self._resolve_rng(rng, seed)
        await self.drive_idle(resolved_rng.randint(min_idle, max_idle))
