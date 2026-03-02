import os
import glob
from cocotb_tools.runner import get_runner

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "tx_scheduling/rtl/tx_scheduling_pkg.sv",
    "tx_scheduling/rtl/tx_scheduling.sv",
] + rtl_utils


def test_tx_scheduling():
    base_dir = os.getcwd()
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="tx_scheduling",
        build_dir="tx_scheduling/sim_build",
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    sim.test(
        hdl_toplevel="tx_scheduling",
        test_module="tx_scheduling.tb.tx_scheduling_test",
        waves=waves,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_tx_scheduling()
