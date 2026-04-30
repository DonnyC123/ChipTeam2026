import os
import random
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

from cocotb import start_soon
from cocotb.triggers import RisingEdge, Timer
from cocotb.queue import Queue
from typing import Generic, TypeVar
from dataclasses import fields, is_dataclass

from tb_utils.abstract_transactions import (
    AbstractTransaction,
)

GenericSequenceItem = TypeVar("GenericSequenceItem", bound=AbstractTransaction)
STARTUP_DELAY_ENV = "RX_FIFO_DRIVER_STARTUP_DELAY_MAX_NS"
STARTUP_DELAY_MIN_TENTHS_NS = 10


class RXFifoDriver(Generic[GenericSequenceItem]):
    def __init__(self, dut, seq_item_type: GenericSequenceItem):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.seq_item_queue: Queue[GenericSequenceItem] = Queue()

        start_soon(self.driver_loop())

    async def send(self, transaction: GenericSequenceItem):
        await self.seq_item_queue.put(transaction)

    @staticmethod
    def _resolve_startup_delay_max_tenths_ns() -> tuple[int, bool]:
        raw_value = os.getenv(STARTUP_DELAY_ENV)

        try:
            parsed_value = Decimal(raw_value)
        except (InvalidOperation, TypeError):
            return STARTUP_DELAY_MIN_TENTHS_NS, True

        if parsed_value < Decimal("1.0"):
            return STARTUP_DELAY_MIN_TENTHS_NS, True

        resolved_tenths = int(
            (parsed_value * 10).to_integral_value(rounding=ROUND_FLOOR)
        )
        return max(resolved_tenths, STARTUP_DELAY_MIN_TENTHS_NS), False

    async def _wait_startup_delay(self):
        max_tenths_ns, used_fallback = self._resolve_startup_delay_max_tenths_ns()
        chosen_tenths_ns = random.randint(STARTUP_DELAY_MIN_TENTHS_NS, max_tenths_ns)
        chosen_delay_ns = chosen_tenths_ns / 10
        resolved_max_ns = max_tenths_ns / 10

        self.dut._log.info(
            "RX FIFO driver startup delay resolved: "
            f"chosen={chosen_delay_ns:.1f}ns "
            f"max={resolved_max_ns:.1f}ns "
            f"fallback={used_fallback}"
        )
        await Timer(chosen_delay_ns, unit="ns")

    async def driver_loop(self):
        await self._wait_startup_delay()

        while True:
            if not self.seq_item_queue.empty():
                seq_item = await self.seq_item_queue.get()
            else:
                seq_item = self.seq_item_type.invalid_seq_item()

            await self.drive_transaction(seq_item)
            await RisingEdge(self.dut.s_clk)

    async def busy(self):
        return not self.seq_item_queue.empty()

    async def drive_transaction(self, sequenece_item: GenericSequenceItem):
        await self.recursive_drive(self.dut, sequenece_item)

    async def recursive_drive(self, input_parent, item):
        for f in fields(item):
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

    async def wait_until_idle(self):
        while not self.seq_item_queue.empty():
            await RisingEdge(self.dut.s_clk)
