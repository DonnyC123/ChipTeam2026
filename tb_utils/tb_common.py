import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_CLOCK_TASK = None


async def initialize_tb(dut, clk_period_ns=10):
    global _CLOCK_TASK
    if _CLOCK_TASK is not None and not _CLOCK_TASK.done():
        _CLOCK_TASK.kill()

    clk_gen = Clock(dut.clk, clk_period_ns, unit="ns")
    _CLOCK_TASK = cocotb.start_soon(clk_gen.start())

    await reset_dut(dut, 2 * clk_period_ns)


async def reset_dut(dut, duration_ns=20):
    if hasattr(dut, "rst"):
        dut.rst.value = 1
        await Timer(duration_ns, unit="ns")
        await RisingEdge(dut.clk)
        await RisingEdge(dut.clk)
        dut.rst.value = 0
    elif hasattr(dut, "rst_n"):
        dut.rst_n.value = 1
        await Timer(duration_ns, unit="ns")
        await RisingEdge(dut.clk)
        await RisingEdge(dut.clk)
        dut.rst_n.value = 0
    else:
        raise RuntimeError("DUT does not have 'rst' or 'rst_n' signal!")

