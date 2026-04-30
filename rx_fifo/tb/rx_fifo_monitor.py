import os
import random
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

from cocotb import start_soon
from cocotb.triggers import RisingEdge, ReadOnly, Timer
from cocotb.queue import Queue
from dataclasses import fields, is_dataclass
from typing import Generic, TypeVar, Type

from tb_utils.abstract_transactions import (
    AbstractTransaction,
    AbstractValidTransaction,
)

OutputTransaction = TypeVar("OutputTransaction", bound=AbstractTransaction)
STARTUP_DELAY_ENV = "RX_FIFO_MONITOR_STARTUP_DELAY_MAX_NS"
STARTUP_DELAY_MIN_TENTHS_NS = 10


class RXFifoMonitor(Generic[OutputTransaction]):
    def __init__(self, dut, output_transaction: Type[OutputTransaction]):
        self.dut = dut
        self.output_transaction: Type[OutputTransaction] = output_transaction
        self.actual_queue: Queue = Queue()
        start_soon(self.monitor_loop())

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

    async def monitor_loop(self):
        await self._wait_startup_delay()

        while True:
            output_transaction = await self.receive_transaction()
            await self.actual_queue.put(output_transaction.to_data)

    async def receive_transaction(self) -> OutputTransaction:
        await RisingEdge(self.dut.m_clk)
        await ReadOnly()

        output_transaction = self.output_transaction()
        await self.recursive_receive(self.dut, output_transaction)

        return output_transaction

    async def recursive_receive(self, input_parent, transaction):
        for f in fields(transaction):
            field_name = f.name
            value = getattr(transaction, field_name)

            if hasattr(input_parent, field_name):
                signal_or_interface = getattr(input_parent, field_name)
                if is_dataclass(value):
                    await self.recursive_receive(signal_or_interface, value)
                else:
                    out_value = signal_or_interface.value
                    setattr(transaction, field_name, out_value)

            else:
                raise AttributeError(
                    f"Field '{field_name}' found in sequence item "
                    f"but NOT in DUT handle '{input_parent._name}'."
                )


OutputValidTransaction = TypeVar(
    "OutputValidTransaction", bound=AbstractValidTransaction
)


class GenericValidMonitor(RXFifoMonitor[OutputValidTransaction]):
    async def receive_transaction(self) -> OutputValidTransaction:
        while True:
            await RisingEdge(self.dut.m_clk)
            await ReadOnly()

            output_transaction = self.output_transaction()

            await self.recursive_receive(self.dut, output_transaction)

            if output_transaction.valid:
                return output_transaction
