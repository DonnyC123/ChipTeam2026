import random

from cocotb import start_soon
from cocotb.triggers import RisingEdge
from cocotb.types import Logic


class RXFifoReadyDriver:
    def __init__(self, dut, probability: float = 0.7, seed: int | None = None):
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"probability must be in [0, 1], got {probability}")
        self.dut = dut
        self.probability = probability
        self._rng = random.Random(seed)
        start_soon(self._loop())

    async def _loop(self):
        while True:
            ready = 1 if self._rng.random() < self.probability else 0
            self.dut.m_axi.ready.value = Logic(ready)
            await RisingEdge(self.dut.m_clk)
