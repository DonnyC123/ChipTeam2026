import random

from cocotb.types import Logic, LogicArray

from rx_fifo.tb.rx_fifo_sequence_item import (
    AXIStreamReadyTransaction,
    RXFifoSequenceItem,
)
from tb_utils.generic_sequence import GenericSequence

class RXFifoSequence(GenericSequence):
    DATA_IN_W = RXFifoSequenceItem.DATA_IN_W
    IN_MASK_W = RXFifoSequenceItem.IN_MASK_W

    def __init__(self, driver, *subscribers):
        super().__init__(driver, *subscribers)
        self._reset_current_item()

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
                raise ValueError(
                    f"Expected LogicArray width {width}, got {len(value)}"
                )
            return value
        if not isinstance(value, int):
            raise TypeError(f"Expected int or LogicArray, got {type(value).__name__}")
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

    async def reset_dut(self):
        reset_item = RXFifoSequenceItem(rst=Logic("1"))
        await self.notify_subscribers(reset_item.to_data)
        await self.add_transaction(reset_item)

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

    def add_ready(self, value: bool | int | Logic):
        self._current_item.m_axi.ready = self._to_logic(value)

    async def add_valid_input(self, data: int | LogicArray, mask: int | LogicArray):
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_data(data)
            self.add_mask(mask)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(0)
            self.add_ready(1)
            await self.send_current()
        finally:
            self._current_item = staged_item

    async def add_manual_last_in(
        self,
        data: int | LogicArray,
        mask: int | LogicArray,
        ready: bool | int | Logic = 1,
    ) -> None:
        staged_item = self._current_item
        self._reset_current_item()
        try:
            self.add_data(data)
            self.add_mask(mask)
            self.add_valid(1)
            self.add_drop(0)
            self.add_send(1)
            self.add_ready(ready)
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

    def add_random_ready(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
    ):
        resolved_rng = self._resolve_rng(rng, seed)
        self.add_ready(resolved_rng.randrange(2))

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
            self.add_ready(1)
            await self.send_current()
        finally:
            self._current_item = staged_item

    async def add_random_last_in(
        self,
        rng: random.Random | None = None,
        seed: int | None = None,
        ready: bool | int | Logic = 1,
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
            self.add_ready(ready)
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
            self.add_ready(1)
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
