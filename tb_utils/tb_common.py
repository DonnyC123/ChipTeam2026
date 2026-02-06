import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


async def initialize_tb(dut, clk_period_ns=10):
    clk_gen = Clock(dut.clk, clk_period_ns, unit="ns")
    cocotb.start_soon(clk_gen.start())

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

