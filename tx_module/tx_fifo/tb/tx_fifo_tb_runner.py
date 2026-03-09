import os
import glob
from cocotb_tools.runner import get_runner

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "tx_fifo/rtl/tx_fifo_pkg.sv",
    "tx_fifo/rtl/tx_fifo.sv",
] + rtl_utils

DEPTH = 64


def test_tx_fifo():
    base_dir = os.getcwd()
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "DEPTH": DEPTH,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="tx_fifo",
        build_dir="tx_fifo/sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    sim.test(
        hdl_toplevel="tx_fifo",
        test_module="tx_fifo.tb.tx_fifo_test",
        waves=waves,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_tx_fifo()
