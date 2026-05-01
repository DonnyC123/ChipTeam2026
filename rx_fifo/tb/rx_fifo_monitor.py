import os
import random
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Type, TypeVar

from cocotb.triggers import ReadOnly, RisingEdge, Timer

from tb_utils.abstract_transactions import (
    AbstractTransaction,
    AbstractValidTransaction,
)
from tb_utils.generic_monitor import GenericMonitor, GenericValidMonitor as _GenericValidMonitor

OutputTransaction = TypeVar("OutputTransaction", bound=AbstractTransaction)
OutputValidTransaction = TypeVar(
    "OutputValidTransaction", bound=AbstractValidTransaction
)
STARTUP_DELAY_ENV = "RX_FIFO_MONITOR_STARTUP_DELAY_MAX_NS"
STARTUP_DELAY_MIN_TENTHS_NS = 10


class _StartupDelayMixin:
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
            "RX FIFO monitor startup delay resolved: "
            f"chosen={chosen_delay_ns:.1f}ns "
            f"max={resolved_max_ns:.1f}ns "
            f"fallback={used_fallback}"
        )
        await Timer(chosen_delay_ns, unit="ns")


class RXFifoMonitor(_StartupDelayMixin, GenericMonitor[OutputTransaction]):
    def __init__(self, dut, output_transaction: Type[OutputTransaction], clk=None):
        super().__init__(dut, output_transaction, clk=clk if clk is not None else dut.m_clk)

    async def monitor_loop(self):
        await self._wait_startup_delay()
        await super().monitor_loop()


class GenericValidMonitor(_StartupDelayMixin, _GenericValidMonitor[OutputValidTransaction]):
    def __init__(self, dut, output_transaction: Type[OutputValidTransaction], clk=None):
        super().__init__(dut, output_transaction, clk=clk if clk is not None else dut.m_clk)

    async def monitor_loop(self):
        await self._wait_startup_delay()
        await super().monitor_loop()


class RXFifoAxiStreamMonitor(_StartupDelayMixin, GenericMonitor[OutputValidTransaction]):
    """AXI-stream monitor: only captures on a valid && ready handshake.

    Without the ready check, a single asserted-but-not-yet-handshaken valid
    cycle would be captured every clock until the consumer accepts it,
    flooding the actual_queue with duplicates.
    """

    def __init__(self, dut, output_transaction: Type[OutputValidTransaction], clk=None):
        super().__init__(dut, output_transaction, clk=clk if clk is not None else dut.m_clk)

    async def receive_transaction(self) -> OutputValidTransaction:
        while True:
            await RisingEdge(self._clk)
            await ReadOnly()

            output_transaction = self.output_transaction()
            await self.recursive_receive(self.dut, output_transaction)

            try:
                ready = bool(int(self.dut.m_axi.ready.value))
            except (ValueError, AttributeError):
                ready = False

            if output_transaction.valid and ready:
                return output_transaction

    async def monitor_loop(self):
        await self._wait_startup_delay()
        await super().monitor_loop()
