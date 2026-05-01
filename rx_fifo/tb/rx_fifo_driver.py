import os
import random
from dataclasses import replace
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import TypeVar

from cocotb.triggers import RisingEdge, Timer
from cocotb.types import Logic

from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_drivers import GenericDriver

GenericSequenceItem = TypeVar("GenericSequenceItem", bound=AbstractTransaction)
STARTUP_DELAY_ENV = "RX_FIFO_DRIVER_STARTUP_DELAY_MAX_NS"
STARTUP_DELAY_MIN_TENTHS_NS = 10


class RXFifoDriver(GenericDriver[GenericSequenceItem]):
    def __init__(self, dut, seq_item_type: GenericSequenceItem):
        self._dropping = False
        super().__init__(dut, seq_item_type, clk=dut.s_clk)

    async def notify(self, notification):
        if notification.get("cancel"):
            self._dropping = True

    @staticmethod
    def _is_packet_terminator(item) -> bool:
        try:
            return bool(int(item.send_i)) or bool(int(item.drop_i))
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _suppress_packet_signals(item):
        return replace(
            item,
            valid_i=Logic("0"),
            send_i=Logic("0"),
            drop_i=Logic("0"),
        )

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

            ends_packet = self._is_packet_terminator(seq_item)

            if self._dropping:
                seq_item = self._suppress_packet_signals(seq_item)

            await self.drive_transaction(seq_item)
            await RisingEdge(self._clk)

            if self._dropping and ends_packet:
                self._dropping = False
