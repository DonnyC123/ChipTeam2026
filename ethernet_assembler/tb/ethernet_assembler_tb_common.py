import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_clock_tasks = {}


async def initialize_tb(dut, clk_period_ns=10):
    dut_key = getattr(dut, "_name", repr(dut))
    clk_task = _clock_tasks.get(dut_key)
    if clk_task is None or clk_task.done():
        clk_gen = Clock(dut.clk, clk_period_ns, unit="ns")
        _clock_tasks[dut_key] = cocotb.start_soon(clk_gen.start())

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
