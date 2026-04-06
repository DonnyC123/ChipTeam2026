import os
import glob
from cocotb_tools.runner import get_runner
from multiplier_demo.tb.fast_multiplier_sequence_item import FastMultiplierSequenceItem
from multiplier_demo.tb.fast_multiplier_out_transaction import (
    FastMultiplierOutTransaction,
)

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "multiplier_demo/rtl/multiplier_pkg.sv",
    "multiplier_demo/rtl/multiplier.sv",
    "multiplier_demo/rtl/fast_multiplier.sv",
] + rtl_utils


def test_resize_module():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "DIN_W": FastMultiplierSequenceItem.DIN_W,
        "DOUT_W": FastMultiplierOutTransaction.DOUT_W,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="fast_multiplier",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="fast_multiplier",
        test_module="multiplier_demo.tb.fast_multiplier_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
